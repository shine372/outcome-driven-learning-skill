from __future__ import annotations

import copy
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "outcome-driven-learning"
SCRIPT_PATH = SKILL_ROOT / "scripts" / "render_plan.py"
GOLDEN_PATH = SKILL_ROOT / "assets" / "figma-two-day-plan.json"

spec = importlib.util.spec_from_file_location("render_plan", SCRIPT_PATH)
assert spec and spec.loader
render_plan_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_plan_module)


def load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


class ValidatePlanTests(unittest.TestCase):
    def test_golden_plan_is_valid(self) -> None:
        self.assertEqual(render_plan_module.validate_plan(load_golden()), [])

    def test_capability_ladder_requires_three_to_five_levels(self) -> None:
        plan = load_golden()
        plan["capability_ladder"] = plan["capability_ladder"][:2]
        plan["target_level"] = "L2"

        errors = render_plan_module.validate_plan(plan)

        self.assertTrue(
            any("capability_ladder 必须包含 3–5 个等级" in item for item in errors)
        )

    def test_target_level_must_exist(self) -> None:
        plan = load_golden()
        plan["target_level"] = "L9"

        errors = render_plan_module.validate_plan(plan)

        self.assertIn("target_level 必须存在于 capability_ladder。", errors)

    def test_daily_budget_is_enforced(self) -> None:
        plan = load_golden()
        plan["budget"]["schedule"][0]["available_minutes"] = 10

        errors = render_plan_module.validate_plan(plan)

        self.assertTrue(any("Day 1 的任务总时长" in item for item in errors))

    def test_acceptance_is_required(self) -> None:
        plan = load_golden()
        plan["tasks"][0]["acceptance"] = []

        errors = render_plan_module.validate_plan(plan)

        self.assertTrue(any("acceptance 至少需要一项" in item for item in errors))

    def test_sequence_must_be_unique(self) -> None:
        plan = load_golden()
        plan["tasks"][1]["sequence"] = plan["tasks"][0]["sequence"]

        errors = render_plan_module.validate_plan(plan)

        self.assertTrue(any("任务顺序" in item and "重复" in item for item in errors))

    def test_stage_must_be_known(self) -> None:
        plan = load_golden()
        plan["tasks"][0]["stage"] = "random"

        errors = render_plan_module.validate_plan(plan)

        self.assertTrue(any("tasks[1].stage" in item for item in errors))

    def test_unverified_tutorial_cannot_have_precise_range(self) -> None:
        plan = load_golden()
        plan["tasks"][0]["tutorial"]["verification"] = "unverified"

        errors = render_plan_module.validate_plan(plan)

        self.assertTrue(any("教程未核验" in item for item in errors))

    def test_last_task_must_be_delivery(self) -> None:
        plan = load_golden()
        plan["tasks"][-1]["stage"] = "just_in_time"

        errors = render_plan_module.validate_plan(plan)

        self.assertIn(
            "按 sequence 排序后的最后一个任务必须是 delivery。",
            errors,
        )

    def test_precise_range_cannot_exceed_duration(self) -> None:
        plan = load_golden()
        plan["tasks"][0]["tutorial"]["duration_seconds"] = 120

        errors = render_plan_module.validate_plan(plan)

        self.assertTrue(any("观看范围超过教程总时长" in item for item in errors))

    def test_all_four_stages_are_required(self) -> None:
        plan = load_golden()
        for task in plan["tasks"]:
            if task["stage"] == "just_in_time":
                task["stage"] = "main_project"

        errors = render_plan_module.validate_plan(plan)

        self.assertTrue(any("缺少：按需插播" in item for item in errors))


class RenderPlanTests(unittest.TestCase):
    def test_render_contains_capability_and_eleven_column_tables(self) -> None:
        markdown = render_plan_module.render_plan(load_golden())

        self.assertIn("| 等级 | 能力标准 | 用途 |", markdown)
        self.assertIn("推荐目标等级：L3｜产品原型交付（推荐目标）", markdown)
        self.assertIn(
            "| 顺序 | 安排 | 阶段 | 学习任务 | 预计时长 | 教程与链接 | "
            "观看范围 | 跟练产出 | 验收标准 | 备注 | 完成 |",
            markdown,
        )
        self.assertIn("| 2 | Day 1 | 长项目主线 |", markdown)
        self.assertIn("| 11 | Day 2 | 交付验收 |", markdown)

    def test_cli_writes_markdown_for_valid_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "plan.md"
            exit_code = render_plan_module.main(
                [str(GOLDEN_PATH), "--output", str(output)]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output.exists())
            self.assertIn("# 两天内用可展示作品", output.read_text(encoding="utf-8"))

    def test_cli_rejects_invalid_plan(self) -> None:
        plan = load_golden()
        plan["tasks"][0]["acceptance"] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "invalid.json"
            output_path = Path(temp_dir) / "invalid.md"
            input_path.write_text(
                json.dumps(plan, ensure_ascii=False),
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = render_plan_module.main(
                    [str(input_path), "--output", str(output_path)]
                )

            self.assertEqual(exit_code, 1)
            self.assertFalse(output_path.exists())
            self.assertIn("计划校验失败", stderr.getvalue())

    def test_plan_is_not_mutated_during_validation(self) -> None:
        plan = load_golden()
        original = copy.deepcopy(plan)

        render_plan_module.validate_plan(plan)
        render_plan_module.render_plan(plan)

        self.assertEqual(plan, original)


class RepositoryContractTests(unittest.TestCase):
    def test_skill_frontmatter_has_no_scaffold_placeholder(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertTrue(content.startswith("---\nname: outcome-driven-learning\n"))
        self.assertNotIn("[TODO:", content)
        self.assertNotIn("TODO", content)

    def test_openai_metadata_has_expected_invocation_policy(self) -> None:
        content = (
            SKILL_ROOT / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")

        self.assertIn('display_name: "成果倒逼学习规划器"', content)
        self.assertIn("allow_implicit_invocation: true", content)
        self.assertIn("$outcome-driven-learning", content)

    def test_schema_and_golden_plan_are_valid_json(self) -> None:
        json.loads(
            (SKILL_ROOT / "assets" / "learning-plan.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(load_golden()["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
