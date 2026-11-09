#!/usr/bin/env python3
"""Validate and render an outcome-driven learning plan."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


STAGES = {
    "warmup": "短课热身",
    "main_project": "长项目主线",
    "just_in_time": "按需插播",
    "delivery": "交付验收",
}

RECOMMENDATIONS = {
    "minimum": "最低可用",
    "recommended": "推荐目标",
    "optional": "可选",
    "not_needed": "通常不需要",
    "none": "",
}

VERIFICATIONS = {
    "verified": "已核验",
    "partially_verified": "部分核验",
    "unverified": "未核验",
}

EMPTY_RANGES = {"", "-", "—", "–", "未核验"}
TIME_RANGE_RE = re.compile(
    r"^(?P<start>\d{1,3}:\d{2}(?::\d{2})?)\s*[–—-]\s*"
    r"(?P<end>\d{1,3}:\d{2}(?::\d{2})?)$"
)


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_text_list(value: Any, *, allow_empty: bool = False) -> bool:
    if not isinstance(value, list):
        return False
    if not allow_empty and not value:
        return False
    return all(_is_nonempty_text(item) for item in value)


def _parse_timestamp(value: str) -> int:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


def validate_plan(plan: Any) -> list[str]:
    """Return all validation errors. An empty list means the plan is valid."""
    errors: list[str] = []

    if not isinstance(plan, dict):
        return ["根节点必须是 JSON 对象。"]

    if plan.get("schema_version") != 1:
        errors.append("schema_version 必须是 1。")

    for field in ("goal", "audience_role", "target_level", "target_level_rationale"):
        if not _is_nonempty_text(plan.get(field)):
            errors.append(f"{field} 不能为空。")

    assumptions = plan.get("assumptions", [])
    if not _is_text_list(assumptions, allow_empty=True):
        errors.append("assumptions 必须是字符串数组，可以为空。")

    ladder = plan.get("capability_ladder")
    ladder_levels: set[str] = set()
    recommendations: list[str] = []
    if not isinstance(ladder, list):
        errors.append("capability_ladder 必须是数组。")
    elif not 3 <= len(ladder) <= 5:
        errors.append("capability_ladder 必须包含 3–5 个等级。")
    else:
        for index, item in enumerate(ladder, start=1):
            prefix = f"capability_ladder[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} 必须是对象。")
                continue
            for field in ("level", "name", "standard", "use_case"):
                if not _is_nonempty_text(item.get(field)):
                    errors.append(f"{prefix}.{field} 不能为空。")
            level = item.get("level")
            if _is_nonempty_text(level):
                if level in ladder_levels:
                    errors.append(f"能力等级 {level} 重复。")
                ladder_levels.add(level)
            recommendation = item.get("recommendation")
            if recommendation not in RECOMMENDATIONS:
                errors.append(
                    f"{prefix}.recommendation 必须是 "
                    f"{', '.join(RECOMMENDATIONS)} 之一。"
                )
            else:
                recommendations.append(recommendation)

        target_level = plan.get("target_level")
        if _is_nonempty_text(target_level) and target_level not in ladder_levels:
            errors.append("target_level 必须存在于 capability_ladder。")
        if "recommended" not in recommendations:
            errors.append("capability_ladder 至少需要一个 recommended 等级。")

    portfolio = plan.get("portfolio")
    if not isinstance(portfolio, dict):
        errors.append("portfolio 必须是对象。")
    else:
        if not _is_nonempty_text(portfolio.get("name")):
            errors.append("portfolio.name 不能为空。")
        if not _is_text_list(portfolio.get("scope")):
            errors.append("portfolio.scope 必须是非空字符串数组。")
        if not _is_text_list(portfolio.get("out_of_scope")):
            errors.append("portfolio.out_of_scope 必须是非空字符串数组。")
        if not _is_nonempty_text(portfolio.get("final_demo")):
            errors.append("portfolio.final_demo 不能为空。")

    schedule_days: dict[str, int] = {}
    total_available = 0
    budget = plan.get("budget")
    if not isinstance(budget, dict):
        errors.append("budget 必须是对象。")
    else:
        total_budget = budget.get("total_minutes")
        if not _is_positive_int(total_budget):
            errors.append("budget.total_minutes 必须是正整数。")
        schedule = budget.get("schedule")
        if not isinstance(schedule, list) or not schedule:
            errors.append("budget.schedule 必须是非空数组。")
        else:
            for index, day in enumerate(schedule, start=1):
                prefix = f"budget.schedule[{index}]"
                if not isinstance(day, dict):
                    errors.append(f"{prefix} 必须是对象。")
                    continue
                label = day.get("day")
                available = day.get("available_minutes")
                if not _is_nonempty_text(label):
                    errors.append(f"{prefix}.day 不能为空。")
                    continue
                if label in schedule_days:
                    errors.append(f"budget.schedule 中的 {label} 重复。")
                    continue
                if not _is_positive_int(available):
                    errors.append(f"{prefix}.available_minutes 必须是正整数。")
                    continue
                schedule_days[label] = available
                total_available += available
            if _is_positive_int(total_budget) and total_available > total_budget:
                errors.append("每日可用时间之和不能超过 budget.total_minutes。")

    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks 必须是非空数组。")
        return errors

    sequences: set[int] = set()
    used_minutes = {day: 0 for day in schedule_days}
    stages: set[str] = set()
    last_sequence: int | None = None
    last_stage: str | None = None

    for index, task in enumerate(tasks, start=1):
        prefix = f"tasks[{index}]"
        if not isinstance(task, dict):
            errors.append(f"{prefix} 必须是对象。")
            continue

        sequence = task.get("sequence")
        if not _is_positive_int(sequence):
            errors.append(f"{prefix}.sequence 必须是正整数。")
        elif sequence in sequences:
            errors.append(f"任务顺序 {sequence} 重复。")
        else:
            sequences.add(sequence)
            if last_sequence is None or sequence > last_sequence:
                last_sequence = sequence
                last_stage = task.get("stage") if isinstance(task.get("stage"), str) else None

        day = task.get("day")
        if not _is_nonempty_text(day) or day not in schedule_days:
            errors.append(f"{prefix}.day 必须存在于 budget.schedule。")

        stage = task.get("stage")
        if stage not in STAGES:
            errors.append(f"{prefix}.stage 必须是 {', '.join(STAGES)} 之一。")
        else:
            stages.add(stage)

        if not _is_nonempty_text(task.get("task")):
            errors.append(f"{prefix}.task 不能为空。")

        minutes = task.get("estimated_minutes")
        if not _is_positive_int(minutes):
            errors.append(f"{prefix}.estimated_minutes 必须是正整数。")
        elif _is_nonempty_text(day) and day in schedule_days:
            used_minutes[day] += minutes

        if not _is_nonempty_text(task.get("output")):
            errors.append(f"{prefix}.output 不能为空。")
        if not _is_text_list(task.get("acceptance")):
            errors.append(f"{prefix}.acceptance 至少需要一项可观察标准。")

        if "completed" in task and not isinstance(task["completed"], bool):
            errors.append(f"{prefix}.completed 必须是布尔值。")

        tutorial = task.get("tutorial")
        if not isinstance(tutorial, dict):
            errors.append(f"{prefix}.tutorial 必须是对象。")
            continue

        title = tutorial.get("title")
        url = tutorial.get("url")
        viewing_range = tutorial.get("viewing_range")
        verification = tutorial.get("verification")
        duration = tutorial.get("duration_seconds")

        if not isinstance(title, str):
            errors.append(f"{prefix}.tutorial.title 必须是字符串。")
        if not isinstance(url, str):
            errors.append(f"{prefix}.tutorial.url 必须是字符串。")
        if not isinstance(viewing_range, str):
            errors.append(f"{prefix}.tutorial.viewing_range 必须是字符串。")
        if verification not in VERIFICATIONS:
            errors.append(
                f"{prefix}.tutorial.verification 必须是 "
                f"{', '.join(VERIFICATIONS)} 之一。"
            )
        if "duration_seconds" in tutorial and not _is_positive_int(duration):
            errors.append(f"{prefix}.tutorial.duration_seconds 必须是正整数。")

        if isinstance(url, str) and url.strip() not in EMPTY_RANGES:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"{prefix}.tutorial.url 必须是有效的 http(s) URL 或 —。")

        range_text = viewing_range.strip() if isinstance(viewing_range, str) else ""
        if verification == "unverified" and range_text not in EMPTY_RANGES:
            errors.append(
                f"{prefix} 的教程未核验时，viewing_range 只能写 — 或 未核验。"
            )

        range_match = TIME_RANGE_RE.match(range_text)
        if range_match:
            start = _parse_timestamp(range_match.group("start"))
            end = _parse_timestamp(range_match.group("end"))
            if start >= end:
                errors.append(f"{prefix} 的观看范围开始时间必须早于结束时间。")
            if _is_positive_int(duration) and end > duration:
                errors.append(f"{prefix} 的观看范围超过教程总时长。")

    for day, used in used_minutes.items():
        if day in schedule_days and used > schedule_days[day]:
            errors.append(
                f"{day} 的任务总时长 {used} 分钟超过可用时间 "
                f"{schedule_days[day]} 分钟。"
            )

    missing_stages = [stage for stage in STAGES if stage not in stages]
    if missing_stages:
        errors.append(
            "tasks 必须覆盖所有阶段，缺少："
            + "、".join(STAGES[stage] for stage in missing_stages)
        )

    if last_stage != "delivery":
        errors.append("按 sequence 排序后的最后一个任务必须是 delivery。")

    return errors


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", r"\|").replace("\r", "").replace("\n", "<br>")


def _tutorial_cell(tutorial: dict[str, Any]) -> str:
    title = tutorial.get("title") or "—"
    url = tutorial.get("url") or "—"
    if url != "—":
        return f"[{_cell(title)}]({url})"
    return _cell(title)


def render_plan(plan: dict[str, Any]) -> str:
    """Render an already validated plan as Markdown."""
    capability_by_level = {
        item["level"]: item for item in plan["capability_ladder"]
    }
    target = capability_by_level[plan["target_level"]]
    recommendation = RECOMMENDATIONS.get(target.get("recommendation", "none"), "")
    target_suffix = f"（{recommendation}）" if recommendation else ""

    lines = [
        f"# {plan['goal']}",
        "",
        "## 目标选择",
        "",
        f"- 目标岗位或场景：{plan['audience_role']}",
        f"- 推荐目标等级：{plan['target_level']}｜{target['name']}{target_suffix}",
        f"- 推荐理由：{plan['target_level_rationale']}",
        f"- 最终演示：{plan['portfolio']['final_demo']}",
        "",
        "## 能力等级",
        "",
        "| 等级 | 能力标准 | 用途 |",
        "| --- | --- | --- |",
    ]

    for item in plan["capability_ladder"]:
        label = RECOMMENDATIONS.get(item.get("recommendation", "none"), "")
        use_case = item["use_case"]
        if label:
            use_case = f"{use_case}（{label}）"
        level = f"{item['level']}｜{item['name']}"
        lines.append(
            f"| {_cell(level)} | {_cell(item['standard'])} | {_cell(use_case)} |"
        )

    scope = "；".join(plan["portfolio"]["scope"])
    out_of_scope = "；".join(plan["portfolio"]["out_of_scope"])
    schedule = "；".join(
        f"{item['day']} {item['available_minutes']} 分钟"
        for item in plan["budget"]["schedule"]
    )

    lines.extend(
        [
            "",
            "## 作品范围",
            "",
            f"- 作品：{plan['portfolio']['name']}",
            f"- 必须包含：{scope}",
            f"- 明确不做：{out_of_scope}",
            f"- 时间预算：{schedule}，合计上限 {plan['budget']['total_minutes']} 分钟",
            "",
            "## 学习路线",
            "",
            "| 顺序 | 安排 | 阶段 | 学习任务 | 预计时长 | 教程与链接 | "
            "观看范围 | 跟练产出 | 验收标准 | 备注 | 完成 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    ordered_tasks = sorted(plan["tasks"], key=lambda item: item["sequence"])
    for task in ordered_tasks:
        acceptance = "；".join(task["acceptance"])
        completed = "x" if task.get("completed", False) else " "
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(task["sequence"]),
                    _cell(task["day"]),
                    _cell(STAGES[task["stage"]]),
                    _cell(task["task"]),
                    _cell(f"{task['estimated_minutes']} 分钟"),
                    _tutorial_cell(task["tutorial"]),
                    _cell(task["tutorial"].get("viewing_range", "—")),
                    _cell(task["output"]),
                    _cell(acceptance),
                    _cell(task.get("notes", "—")),
                    f"[{completed}]",
                ]
            )
            + " |"
        )

    lines.extend(["", "## 教程核验", ""])
    for task in ordered_tasks:
        tutorial = task["tutorial"]
        status = VERIFICATIONS[tutorial["verification"]]
        title = tutorial.get("title") or "—"
        lines.append(f"- 顺序 {task['sequence']}：{title}，{status}")

    lines.extend(
        [
            "",
            "## 完成条件",
            "",
            f"- 完成最终演示：{plan['portfolio']['final_demo']}",
            "- 只有上述演示和最后一行验收通过后，才把目标能力写入简历或作品集。",
            "",
            "## 假设",
            "",
        ]
    )
    if plan.get("assumptions"):
        lines.extend(f"- {item}" for item in plan["assumptions"])
    else:
        lines.append("- 无额外假设。")

    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校验并渲染成果倒逼学习计划。"
    )
    parser.add_argument("plan", type=Path, help="计划 JSON 文件")
    parser.add_argument(
        "--output",
        type=Path,
        help="Markdown 输出文件；省略时写到标准输出",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"找不到计划文件：{args.plan}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(
            f"JSON 解析失败：第 {exc.lineno} 行，第 {exc.colno} 列：{exc.msg}",
            file=sys.stderr,
        )
        return 2

    errors = validate_plan(plan)
    if errors:
        print("计划校验失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    markdown = render_plan(plan)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.buffer.write(markdown.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
