<div align="center">

# 🧰 yanqing-skills

#### 我自己维护和使用的一些 Agent Skills

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-1-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![Cursor](https://img.shields.io/badge/Cursor-Skill-3B82F6?style=flat-square)

</div>

这些 Skill 遵循 [Agent Skills](https://agentskills.io) 的 `SKILL.md` 标准，可以直接加载到支持该标准的 Agent 工具中。

---

## 📋 目录

| 名字 | 一句话 | 入口 |
|---|---|---|
| 🛠️ [**skill-creator**](#️-skill-creator) | 创建、审计、标准化、测试和发布 Codex Skill | [`SKILL.md`](./skill-creator/SKILL.md) |

---

## 📦 安装方式

在 Claude Code、Codex、Cursor 等支持 Agent Skills 的工具里，直接说：

```text
帮我安装这个 Skill：
https://github.com/yanqing7914/yanqing-skills/tree/main/<skill-name>
```

把 `<skill-name>` 换成你想安装的 Skill。也可以直接下载对应目录中的 `SKILL.md`，让 Agent 按照其中的指令执行。

---

## ✨ Skills

<a id="-skills"></a>

### 🛠️ skill-creator

> 别再把 Skill 当成一段 Prompt 了。

很多 Skill 初看能用，但实际会遇到触发边界不清、和其他 Skill 冲突、改完没有回归测试、资源链接失效、版本无法追踪等问题。`skill-creator` 是一套面向 Agent 的工程化工作流，帮助你把 Skill 从“能跑”升级成真正可验证、可测试、可追溯、可持续迭代的标准。

**它能做什么**

- 定义清晰的触发范围和排除条件
- 检查 Skill 结构、契约、路由和行为
- 设计回归测试，验证修改是否真的有效
- 规范拆分脚本、参考资料和其他资源
- 校验本地链接、元数据、权限和安全边界
- 通过 Git provenance 追踪当前版本的来源
- 提供 SkillOpt 风格的 `train / selection / holdout` 流程
- 让候选版本先评测、再暂存，审核后才 adopt
- 不伪造分数，不把“命令执行成功”冒充成“Skill 已经优化完成”

**适合什么时候用**

- 创建新的 Agent Skill
- 整理和标准化已有 Skill
- 排查 Skill 不触发或误触发
- 处理多个 Skill 之间的冲突
- 为 Skill 增加脚本、参考资料和测试
- 评估一次 Skill 优化是否真的带来改进

**怎么触发**

```text
帮我创建一个 Skill
审计一下这个 Skill
检查这个 Skill 的触发边界和路由
给这个 Skill 补充回归测试
评估这次 Skill 优化是否真的有效
```

→ [打开 Skill 目录](./skill-creator) · [查看 SKILL.md](./skill-creator/SKILL.md)

---

## License

MIT License，详见 [`LICENSE`](./LICENSE)。
