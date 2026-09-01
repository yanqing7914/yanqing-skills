<div align="center">

**中文**

# 🧰 yanqing-skills

#### 我自己使用和维护的一些 Agent Skills

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-2-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)
![Cursor](https://img.shields.io/badge/Cursor-Skill-3B82F6?style=flat-square)

</div>

这些 Skill 会先在实际项目中使用和验证，再整理到这里。每个 Skill 都是 Agent 可以直接加载的结构化指令集，遵循 [Agent Skills](https://agentskills.io) 的 `SKILL.md` 标准。

---

## 📋 目录

| 名字 | 一句话 | 入口 |
|---|---|---|
| 🛠️ [**skill-creator**](#️-skill-creator) | 创建、审计、标准化、测试和发布 Codex Skill | [`SKILL.md`](./skill-creator/SKILL.md) |
| 💽 [**storage-analyzer**](#-storage-analyzer) | 分析 Mac / Windows 磁盘占用，生成分级清理报告 | [`SKILL.md`](./storage-analyzer/SKILL.md) |

---

## 📦 安装方式

在 Claude Code、Codex、Cursor 等支持 Agent Skills 的工具里，直接说：

```text
帮我安装这个 Skill：
https://github.com/yanqing7914/yanqing-skills/tree/main/<skill-name>
```

把 `<skill-name>` 换成想安装的 Skill。比如：

```text
帮我安装这个 Skill：
https://github.com/yanqing7914/yanqing-skills/tree/main/storage-analyzer
```

Agent 会读取目标目录中的 `SKILL.md`，并按当前工具的约定完成安装。也可以直接下载对应目录，让 Agent 按照其中的指令执行。

---

## ✨ Skills

<a id="-skills"></a>

<table>
<tr><td>

### 🛠️ skill-creator

> 别再把 Skill 当成一段 Prompt 了。

很多 Skill 初看能用，但实际会遇到触发边界不清、和其他 Skill 冲突、改完没有回归测试、资源链接失效、版本无法追踪等问题。

`skill-creator` 是一套面向 Agent 的工程化工作流，帮助你把 Skill 从“能跑”升级成真正可验证、可测试、可追溯、可持续迭代的工程资产。

**它能做什么**

- 定义清晰的触发范围和排除条件
- 检查 Skill 的结构、契约、路由和行为
- 补充回归测试，验证修改是否真的有效
- 规范拆分脚本、参考资料和其他资源
- 校验本地链接、元数据、权限和安全边界
- 通过 Git provenance 追踪当前版本的来源
- 提供 SkillOpt 风格的 `train / selection / holdout` 流程
- 候选版本先评测、再暂存，经过审核后才 adopt
- 不伪造分数，不把“命令执行成功”冒充成“Skill 已经优化完成”

**怎么触发**

```text
帮我创建一个 Skill
审计一下这个 Skill
检查这个 Skill 的触发边界和路由
给这个 Skill 补充回归测试
评估这次 Skill 优化是否真的有效
```

→ [SKILL.md](./skill-creator/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 💽 storage-analyzer

> 磁盘空间不够时，先弄清楚究竟是什么占了空间，再决定怎么处理。

一句话扫描 macOS / Windows 磁盘占用，找出空间大户，按清理风险分成 🟢、🟡、🔴 三级，并生成排版清晰、可折叠、命令可复制的交互式 HTML 报告。

**它能做什么**

- 扫描整机磁盘并展示容量概览
- 找出占用空间最多的目录和文件
- 识别缓存、临时文件、用户数据和应用数据
- 通过绿灯、黄灯、红灯区分清理风险
- 给出具体路径、影响说明和可执行处置建议
- 生成交互式 HTML 报告，支持查看清理命令
- macOS 和 Windows 自动识别

**安全边界**

- 扫描阶段全程只读
- 默认不擅自删除文件
- 清理建议会明确标注风险和影响
- 系统文件、应用核心数据和不确定内容不会建议直接删除

**怎么触发**

```text
帮我看看存储
磁盘满了
C 盘满了
清理一下磁盘
哪些东西占空间
看下电脑存储
```

→ [SKILL.md](./storage-analyzer/SKILL.md)

</td></tr>
</table>

---

## 🌟 关于

这里存放的是我自己维护的 Agent Skills。它们以独立目录组织，可以单独安装、使用和迭代。

如果对你有帮助，欢迎点个 ⭐，也欢迎通过 Issues 提出问题或建议。

---

<div align="center">

[MIT License](./LICENSE) · 自由使用 / 修改 / 再分发

Made by [@yanqing7914](https://github.com/yanqing7914)

</div>
