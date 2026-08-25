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

这些 Skill 会先在实际项目中使用和验证，再整理到这里。每个 Skill 都是一个 Agent 可以直接加载的结构化指令集，遵循 [Agent Skills](https://agentskills.io) 的 `SKILL.md` 标准。

---

## 📋 目录

| 名字 | 一句话 | 入口 |
|---|---|---|
| 🛠️ [**skill-creator**](#️-skill-creator) | 创建、审计、标准化、测试和发布 Codex Skill | [`SKILL.md`](./skill-creator/SKILL.md) |

---

## 📦 安装方式

在 Claude Code、Codex、Cursor 等支持 Agent Skills 的工具里，直接告诉 Agent：

```text
帮我安装这个 Skill：
https://github.com/yanqing7914/yanqing-skills/tree/main/<skill-name>
```

例如安装 `skill-creator`：

```text
帮我安装这个 Skill：
https://github.com/yanqing7914/yanqing-skills/tree/main/skill-creator
```

Agent 会读取目标目录中的 `SKILL.md`，并根据当前工具的约定完成安装。也可以直接下载目标目录，把它放入对应的 Agent Skills 目录。

---

## ✨ Skills

<a id="-skills"></a>

### 🛠️ skill-creator

`skill-creator` 用于创建、审计、标准化、测试和发布 Codex Skills。

它包含：

- `SKILL.md`：Skill 的触发边界和工程工作流
- `scripts/`：静态校验、初始化、元数据生成、评估拆分和 gate 流程
- `references/`：Skill 工程细节和 SkillOpt 协议说明
- `tests/`：路由、行为、完成度和回归证据

推荐先从 `SKILL.md` 中的只读盘点流程开始。对于已经完成的 Skill，再运行其中记录的静态、契约、Git 和工程校验命令。评估脚手架是可选的；没有独立评估器和来源绑定的产物，不代表已经得出优化结论。

→ [打开 skill-creator](./skill-creator) · [查看 SKILL.md](./skill-creator/SKILL.md)

---

## 📤 上传已有 Skill

如果你已经在别处写好了一个 Skill，不需要手动研究仓库结构。把 Skill 文件夹交给 Agent，并说：

```text
把这个 Skill 上传到 yanqing-skills：
<本地 Skill 路径或 Skill 内容>
```

Agent 会按照 [`AGENT.md`](./AGENT.md) 自动完成：

1. 识别 Skill 名称并检查 `SKILL.md`。
2. 将它放到仓库根目录的 `<skill-name>/`。
3. 保留 `references/`、`scripts/`、`assets/` 等依赖资源。
4. 补充或更新 `README.md`、`CHANGELOG.md` 和本页目录。
5. 运行校验和 Git diff 检查。
6. 创建以 Skill 名称开头的 commit 并推送到 `main`。
7. 在用户要求发布版本时创建 `<skill-name>-v<version>` tag。

仓库地址：<https://github.com/yanqing7914/yanqing-skills>

---

## 🗂️ 目录结构

每个一级目录就是一个 Skill，最少包含：

```text
<skill-name>/
└── SKILL.md
```

复杂 Skill 可以按需包含：

```text
<skill-name>/
├── SKILL.md
├── README.md
├── CHANGELOG.md
├── references/
├── scripts/
├── tests/
└── assets/
```

Skill 名称使用小写字母、数字和短横线，例如 `code-review`、`web-research`。不需要的资源目录不要创建空目录。

## 🏷️ 版本和历史

所有 Skill 共用 `main` 分支，但各自独立使用版本 tag：

```text
<skill-name>-vMAJOR.MINOR.PATCH
```

例如：

```text
skill-creator-v0.1.0
skill-creator-v1.0.0
skill-creator-v1.0.1
```

查看某个 Skill 的历史和版本：

```bash
git log -- skill-creator
git log --follow -- skill-creator/SKILL.md
git tag --list 'skill-creator-v*'
```

## 🧪 本地校验

```bash
git clone https://github.com/yanqing7914/yanqing-skills.git
cd yanqing-skills
node tools/validate-skills.js
git diff --check
```

## License

MIT License，详见 [`LICENSE`](./LICENSE)。
