# skill-creator

别再把 Skill 当成一段 Prompt 了。

很多 Skill 初看能用，但实际使用一段时间后，往往会遇到这些问题：

- 触发边界不清，用户一句话可能触发错误的 Skill；
- 和其他 Skill 发生冲突，路由行为不可预测；
- 修改后没有回归测试，不知道是否破坏了原有能力；
- `references/`、`scripts/` 或其他资源链接悄悄失效；
- 元数据、权限和安全边界没有经过检查；
- 版本无法追踪，不知道当前内容来自哪个 commit；
- 不知道一次优化是真的变好了，还是只是“看起来更完整”。

`skill-creator` 是一套面向 Agent 的 Skill 工程化工作流，帮助你把 Skill 从“能跑”升级成一套真正可验证、可测试、可追溯、可持续迭代的工程资产。

## 它解决什么问题

它帮助你为 Skill 建立完整的工程基础：

- **清晰的触发边界**：明确什么时候应该触发，以及什么时候必须排除；
- **结构化的工程组织**：合理拆分 `SKILL.md`、脚本、参考资料、测试和其他资源；
- **可执行的质量检查**：检查结构、契约、路由、行为和完成条件；
- **资源与安全校验**：检查本地链接、元数据、权限要求和安全边界；
- **Git provenance**：记录当前版本来自哪里，确保变更可以追溯；
- **可重复的优化流程**：提供 SkillOpt 风格的 train / selection / holdout 流程；
- **受控的版本采用**：候选版本先评测，再暂存，经过明确审核后才 adopt，不会悄悄覆盖线上 Skill；
- **诚实的评估结果**：不伪造分数，也不把“命令执行成功”冒充成“Skill 已经优化完成”。

## 适合什么时候使用

如果你正在做以下事情，可以使用 `skill-creator`：

- 创建一个新的 Agent Skill；
- 整理和标准化已有 Skill；
- 排查 Skill 为什么没有按预期触发；
- 处理多个 Skill 之间的路由冲突；
- 为 Skill 增加脚本、参考资料或测试；
- 检查资源链接、元数据和安全边界；
- 评估一次 Skill 优化是否真的有效；
- 为 Skill 建立可追踪、可回归的版本发布流程。

## 核心工作流

```text
盘点现状
  ↓
定义触发边界和排除条件
  ↓
建立结构与契约
  ↓
补充路由、行为和回归测试
  ↓
执行静态检查与工程校验
  ↓
训练候选版本
  ↓
使用 selection / holdout 进行评测
  ↓
暂存候选版本
  ↓
明确审核后 adopt
```

候选版本不会因为“生成成功”或“命令返回 0”就自动覆盖当前版本。评估结果必须有可复现的输入、输出、版本和来源证据。

## 目录结构

```text
skill-creator/
├── SKILL.md
├── README.md
├── scripts/
│   ├── init_skill.py
│   ├── quick_validate.py
│   ├── generate_openai_yaml.py
│   ├── split_skill_cases.py
│   └── skill_gate.py
├── references/
│   ├── openai_yaml.md
│   ├── skill_engineering_details.md
│   └── skillopt_evaluation.md
├── tests/
│   ├── routing_cases.md
│   ├── skill_contract.json
│   └── test_skill_creator.py
└── assets/
```

## 使用方式

先阅读 [`SKILL.md`](./SKILL.md) 中的只读盘点流程，再根据 Skill 当前状态选择合适的检查、测试和优化步骤。

对于已完成的 Skill，运行 `SKILL.md` 中记录的静态、契约、Git 和工程校验命令。评估脚手架是可选的；没有独立评估器和来源绑定的产物，不代表已经得出优化结论。

## 重要原则

- 先定义问题和验收标准，再修改 Skill；
- 触发条件和排除条件同样重要；
- 测试结果必须能够复现；
- 候选版本和线上版本必须明确区分；
- 不用完整度、文件数量或命令成功率替代真实质量；
- 不把未经验证的优化结果写成事实；
- 每次变更都应保留清晰的 Git provenance。

## 文件说明

- [`SKILL.md`](./SKILL.md)：Skill 的完整执行指令和工程工作流；
- [`scripts/`](./scripts)：初始化、校验、评估拆分和候选版本 gate 工具；
- [`references/`](./references)：工程细节、元数据和评估流程参考资料；
- [`tests/`](./tests)：路由、契约、行为和回归测试证据；
- [`assets/`](./assets)：Skill 需要随包分发的资源。
