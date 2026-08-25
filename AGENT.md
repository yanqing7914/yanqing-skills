# Agent Guide

这份文件说明下次如何在本仓库中新增或更新一个 Skill。任何自动化 Agent 在修改仓库前都应先阅读本文件。

## 仓库原则

- 所有 Skill 放在 `skills/<skill-name>/` 下。
- 每个 Skill 至少有一个 `SKILL.md`。
- `<skill-name>` 使用小写字母、数字和短横线，且必须与 `SKILL.md` 元数据中的 `name` 一致。
- 不要把多个 Skill 合并到同一个目录或同一个 `SKILL.md`。
- 一个 commit 尽量只服务于一个 Skill；commit subject 必须以 `<skill-name>:` 开头。
- Skill 版本使用独立前缀 tag，不使用没有前缀的 `v1.0.0`。

## 新增 Skill 流程

### 1. 创建目录

```bash
mkdir -p skills/<skill-name>
cp templates/basic-skill/SKILL.md skills/<skill-name>/SKILL.md
```

复杂 Skill 可以按需创建 `examples/`、`references/` 和 `scripts/`，不要创建无内容的目录。

### 2. 编写 SKILL.md

文件必须以 YAML front matter 开始，并包含 `name` 和 `description`：

```markdown
---
name: <skill-name>
description: 简短说明 Skill 的用途和触发场景。
---

# Skill Name

## 适用场景

## 工作流程

## 输出要求
```

`name` 必须与目录名完全一致，`description` 应说明做什么以及什么时候使用。指令应具体、可执行，避免只写宽泛目标。

### 3. 添加说明和示例

推荐添加 `skills/<skill-name>/README.md`，说明用途、适用场景、使用示例和文件结构。需要时添加真实且脱敏的 `examples/` 或 `references/`。

### 4. 添加初始变更记录

创建 `skills/<skill-name>/CHANGELOG.md`：

```markdown
# Changelog

## [0.1.0] - YYYY-MM-DD

### Added

- 首次创建 Skill。
```

### 5. 校验

```bash
node tools/validate-skills.js
```

校验通过后检查：

```bash
git diff --check
git status
```

### 6. 提交

```bash
git add skills/<skill-name>
git commit -m "<skill-name>: add initial skill"
```

不要在没有明确要求时提交其他 Skill 的文件，也不要修改用户已有的未提交变更。

### 7. 发布版本

初始可用版本创建 tag：

```bash
git tag -a <skill-name>-v0.1.0 -m "<skill-name> v0.1.0"
git push origin main
 git push origin <skill-name>-v0.1.0
```

稳定版本通常从 `v1.0.0` 开始。发布前同步更新该 Skill 的 `CHANGELOG.md`，并在 GitHub Releases 中使用同名 tag（可选）。

## 更新已有 Skill

1. 先运行 `git log -- skills/<skill-name>` 了解历史。
2. 只修改该 Skill 需要的文件。
3. 更新 `CHANGELOG.md`，记录新增、修改和修复。
4. 运行校验和 `git diff --check`。
5. 使用 `<skill-name>:` 开头的 commit，例如：

```bash
git add skills/code-review
git commit -m "code-review: improve security checklist"
```

6. 创建下一个递增 tag，例如 `code-review-v1.1.0`。

## 版本选择速查

- 新增兼容能力：Minor，例如 `v1.1.0`
- 修正文案、规则或小错误：Patch，例如 `v1.0.1`
- 改变核心行为、输入格式或输出契约：Major，例如 `v2.0.0`

## Agent 工作要求

- 修改前先阅读目标 Skill 的 `SKILL.md`、`README.md` 和 `CHANGELOG.md`（如果存在）。
- 不要覆盖或回滚用户未要求处理的变更。
- 完成后报告修改的文件、校验命令和是否创建了 commit/tag。
- 除非用户明确要求，Agent 不要自动执行 `git push`、创建 GitHub 仓库或发布 Release。
