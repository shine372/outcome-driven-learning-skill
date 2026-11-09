# 成果倒逼学习 Skill

`outcome-driven-learning` 是一个 Codex Skill，用来把“我想尽快学会某件事”转换成一份以可展示作品为核心的学习路线。

它不会罗列一整套课程，而是先让用户通过能力等级表选择目标，再围绕一个完整项目安排任务。短课只在遇到具体缺口时插入，每一项任务都必须说明观看范围、跟练产出和验收标准。

## 它解决什么问题

- 不确定某项工具对目标岗位到底需要学到什么程度。
- 收藏了很多教程，却不知道先看什么、看到哪里、何时停止。
- 学完零散功能后无法形成可演示作品。
- 时间有限，需要明确哪些内容应该主动放弃。
- 需要一份能直接执行、能被验收，也能用于复盘的表格计划。

## 输出内容

1. 3–5 级能力表：`等级、能力标准、用途`，并标出最低可用和推荐目标。
2. 目标等级及推荐理由。
3. 可展示作品的范围、最终演示和明确不做内容。
4. 两天或多天学习路线，固定使用 11 列：

   `顺序、安排、阶段、学习任务、预计时长、教程与链接、观看范围、跟练产出、验收标准、备注、完成`

5. 教程核验状态与关键假设。

默认交付 Markdown。只有用户明确要求时，才同步到飞书多维表格。

## 从 GitHub 安装

本项目可直接使用 Codex 的 `skill-installer` 安装：

```bash
python /path/to/skill-installer/scripts/install-skill-from-github.py \
  --repo shine372/outcome-driven-learning-skill \
  --path skills/outcome-driven-learning
```

也可以传入 `tree/main` 地址：

```text
https://github.com/shine372/outcome-driven-learning-skill/tree/main/skills/outcome-driven-learning
```

安装后，在下一轮对话中可显式调用：

```text
$outcome-driven-learning 我想在三天内用直播数据看板学会 SQL，目标是能独立做一份面试作品。
```

当请求同时包含明确能力目标、可展示成果或时间限制时，Skill 也可以自动触发。

## 使用方式

Skill 会先询问缺失的总时长或每日投入，然后给出能力表。目标等级确认后，再生成作品范围和学习任务。

如果用户明确要求直接继续，Skill 会根据岗位和时间预算推荐一个目标等级，并在计划中标记这是假设。

## 严格教程核验

教程来源按以下顺序选择：

1. 用户已有项目和课程。
2. 当前工作区中的原型、设计稿或代码。
3. 联网找到的官方教程和完整项目。
4. 无法确认的候选资源。

无法确认的链接、时长或章节必须标记为“未核验”。无法核验时不会生成精确时间点，也不会根据标题猜测观看范围。

## 结构化计划与渲染

Skill 使用 JSON 作为中间格式，再通过脚本统一校验和渲染：

```bash
python skills/outcome-driven-learning/scripts/render_plan.py \
  skills/outcome-driven-learning/assets/figma-two-day-plan.json \
  --output examples/figma-two-day-plan.md
```

校验器会检查：

- 能力表是否包含 3–5 个等级。
- 目标等级是否存在于能力表。
- 是否覆盖四类阶段并包含最终交付任务。
- 每个任务是否有产出和可观察验收标准。
- 单日任务是否超过可用时长。
- 教程链接、核验状态和观看范围是否一致。

计划模型见 [plan-model.md](skills/outcome-driven-learning/references/plan-model.md)，完整 JSON Schema 位于 `skills/outcome-driven-learning/assets/learning-plan.schema.json`。

## 飞书同步

飞书同步是显式可选能力，默认不会写入云端。

- 新建时使用与 11 列一致的表结构。
- 写入已有 Base 前先检查目标、字段和记录范围。
- 不覆盖或删除无关内容。
- 写入后回读并报告结果。

## 本地开发

运行单元测试：

```bash
python -m unittest discover -s tests -v
```

生成黄金示例：

```bash
python skills/outcome-driven-learning/scripts/render_plan.py \
  skills/outcome-driven-learning/assets/figma-two-day-plan.json \
  --output examples/figma-two-day-plan.md
```

校验 Skill 目录：

```bash
python /path/to/skill-creator/scripts/quick_validate.py \
  skills/outcome-driven-learning
```

`quick_validate.py` 当前依赖 PyYAML；建议在隔离虚拟环境中安装，不修改全局 Python。计划渲染器和单元测试只使用 Python 标准库，不依赖 PyYAML。

## 目录

```text
skills/outcome-driven-learning/
|-- SKILL.md
|-- agents/openai.yaml
|-- assets/
|   |-- figma-two-day-plan.json
|   `-- learning-plan.schema.json
|-- references/
|   |-- plan-model.md
|   `-- research-and-validation.md
`-- scripts/render_plan.py

tests/test_render_plan.py
examples/figma-two-day-plan.md
```

## 许可证

MIT
