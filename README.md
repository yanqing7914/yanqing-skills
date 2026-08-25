<div align="center">

# yanqing-skills

**个人维护的 Agent Skills 集合**

将已经验证可用的 Skill 集中开源，遵循 `SKILL.md` 结构，让支持 Agent Skills 的 Claude Code、Codex、Cursor 等工具可以按目录直接加载。

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-1-10B981?style=for-the-badge)](#skills)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-SKILL.md-8B5CF6?style=for-the-badge)](https://agentskills.io)

</div>

## 这个仓库是什么

这里的每个一级目录就是一个独立 Skill：

```text
yanqing-skills/
├── code-review/
│   └── SKILL.md
├── meeting-summary/
│   └── SKILL.md
└── web-research/
    └── SKILL.md
```

所有 Skill 共用一个 GitHub 仓库和 `main` 分支，但通过以下方式独立管理：

- 目录：区分不同 Skill
- commit：记录具体修改，提交主题以 Skill 名称开头
- CHANGELOG：记录该 Skill 的版本变化
- tag：使用 `<skill-name>-v<version>` 发布单个 Skill

## Skills

| Skill | 说明 | 目录 |
|---|---|---|
| `skill-creator` | 创建、评估和优化 Agent Skill | [`skill-creator`](./skill-creator) |

## 安装单个 Skill

在支持 Agent Skills 的工具中，直接把目标目录 URL 交给 Agent：

```text
请安装这个 Skill：
https://github.com/yanqing7914/yanqing-skills/tree/main/<skill-name>
```

将 `<skill-name>` 替换为实际目录名，例如：

```text
https://github.com/yanqing7914/yanqing-skills/tree/main/code-review
```

也可以只下载目标目录中的 `SKILL.md`，放入对应 Agent 的 Skills 目录。每个 Skill 的具体说明和依赖以该目录内的 `README.md` 为准。

## 上传已有 Skill

如果你已经写好了一个 Skill，只需要把 Skill 文件夹交给 Agent，并说明：

```text
把这个 Skill 上传到 yanqing-skills
```

Agent 会按照 [`AGENT.md`](AGENT.md) 自动完成识别目录、校验 `SKILL.md`、补充说明、提交 commit、推送到 GitHub 和创建版本 tag。仓库地址：<https://github.com/yanqing7914/yanqing-skills>。

## 版本和历史

版本 tag 使用以下格式：

```text
<skill-name>-vMAJOR.MINOR.PATCH
```

例如：

```text
code-review-v0.1.0
code-review-v1.0.0
code-review-v1.0.1
```

查看某个 Skill 的历史和版本：

```bash
git log -- <skill-name>
git log --follow -- <skill-name>/SKILL.md
git tag --list '<skill-name>-v*'
```

## 本地开发

```bash
git clone https://github.com/yanqing7914/yanqing-skills.git
cd yanqing-skills
node tools/validate-skills.js
git diff --check
```

完整的新增、更新、版本判断和上传规范见 [`AGENT.md`](AGENT.md)。

## 目录约定

每个 Skill 至少包含：

```text
<skill-name>/
└── SKILL.md
```

复杂 Skill 可以按需添加：

```text
<skill-name>/
├── SKILL.md
├── README.md
├── CHANGELOG.md
├── references/
├── scripts/
├── examples/
└── assets/
```

不要为不需要的资源创建空目录。Skill 名称使用小写字母、数字和短横线，例如 `code-review`、`web-research`。

## License

MIT License，详见 [`LICENSE`](LICENSE)。
