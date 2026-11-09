# 计划模型

计划使用 JSON 保存，再由 `scripts/render_plan.py` 校验和渲染。JSON 字段使用英文，面向用户的输出使用中文。

## 顶层结构

```json
{
  "schema_version": 1,
  "goal": "两天内用完整作品学会 Figma 产品原型交付",
  "audience_role": "产品助理",
  "target_level": "L3",
  "target_level_rationale": "产品助理要能独立交付中保真原型，并能与设计、研发协作。",
  "capability_ladder": [],
  "portfolio": {},
  "budget": {},
  "tasks": [],
  "assumptions": []
}
```

### `capability_ladder`

必须包含 3–5 项。程序不预设统一等级名称，而是根据领域和岗位生成。

```json
{
  "level": "L3",
  "name": "产品原型交付",
  "standard": "能独立搭建中保真页面、组件、状态和主要交互，并完成分享交付。",
  "use_case": "足以支撑产品助理面试作品和日常原型沟通。",
  "recommendation": "recommended"
}
```

`recommendation` 使用：

- `minimum`：最低可用
- `recommended`：推荐目标
- `optional`：可选
- `not_needed`：通常不需要
- `none`：未特别标记

`target_level` 必须存在于能力表中。渲染后的能力表固定只有 `等级、能力标准、用途` 三列，建议标记写入用途列。

### `portfolio`

```json
{
  "name": "小宇宙收听管理改版",
  "scope": ["6 个主页", "3 个关键状态", "主要任务链路可点击"],
  "out_of_scope": ["完整品牌视觉还原", "复杂动效参数", "插件开发"],
  "final_demo": "完成发现、收听、播放器、播放列表和返回的完整演示。"
}
```

`scope` 和 `out_of_scope` 都不能为空；`final_demo` 必须是可以实际演示的结果。

### `budget`

```json
{
  "total_minutes": 240,
  "schedule": [
    {"day": "Day 1", "available_minutes": 90},
    {"day": "Day 2", "available_minutes": 150}
  ]
}
```

所有任务按 `day` 汇总后的分钟数不能超过该日可用分钟数。各日可用分钟数之和不能超过总预算。

### `tasks`

```json
{
  "sequence": 1,
  "day": "Day 1",
  "stage": "warmup",
  "task": "认识界面、Frame、基础元素和网格",
  "estimated_minutes": 12,
  "tutorial": {
    "title": "Figma 新手教程",
    "url": "https://example.com/video",
    "viewing_range": "00:00–11:41",
    "duration_seconds": 701,
    "verification": "verified"
  },
  "output": "搭出 390×844 的收听页 Frame 骨架",
  "acceptance": ["Frame 尺寸正确", "页面层级结构清楚"],
  "notes": "只建立共同语言，不继续学习组件和原型。",
  "completed": false
}
```

任务规则：

- `sequence` 为正整数且不可重复。
- `day` 必须存在于 `budget.schedule`。
- `stage` 只能是 `warmup`、`main_project`、`just_in_time`、`delivery`。
- `estimated_minutes` 为正整数。
- `output` 不能为空；`acceptance` 至少有一项可观察标准。
- 至少有一个 `main_project` 和一个 `delivery`；按顺序最后一项必须是 `delivery`。
- 没有教程时将标题、URL 和观看范围写为 `—`。
- `verification` 只能是 `verified`、`partially_verified`、`unverified`。
- 未经核验的精确观看范围会被校验器拒绝。无法核验时把范围写为 `—` 或 `未核验`。
- 提供 `duration_seconds` 时，精确时间范围不得超出视频时长。

## 渲染约定

- 能力表在任务表之前，便于先选择目标再执行。
- 学习任务表固定使用 11 列。
- 教程核验状态在任务表后单独列出。
- 脚本只输出校验通过的 Markdown，避免交付半成品计划。
