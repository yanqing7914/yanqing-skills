# Agent Guide

这份文件是本仓库的自动化操作协议。收到“把这个 Skill 上传到 yanqing-skills”“更新仓库里的某个 Skill”或类似请求时，Agent 必须先阅读本文件，再执行操作。

## 仓库模型

- GitHub 仓库：`https://github.com/yanqing7914/yanqing-skills`
- 默认分支：`main`
- 每个一级目录就是一个独立 Skill，例如 `code-review/SKILL.md`。
- 不为每个 Skill 建长期分支，也不为每个 Skill 建单独 GitHub 仓库。
- 目录区分 Skill，commit 记录变更，CHANGELOG 记录版本，tag 发布版本。
- 除非用户明确要求，Agent 直接在 `main` 上完成校验、commit 和 push；不要擅自创建 Pull Request。

## 收到一个已有 Skill 时

用户可能提供一个文件夹、压缩包、GitHub URL 或当前工作区中的 Skill，并说“上传到 yanqing-skills”。按以下流程执行：

### 1. 识别来源和名称

- 如果用户明确指定名称，优先使用用户指定名称。
- 否则优先读取源目录 `SKILL.md` front matter 的 `name`。
- 如果没有 `name`，使用源目录名，并在继续前确认它符合命名规则。
- Skill 名称只能使用小写字母、数字和短横线：`^[a-z0-9]+(?:-[a-z0-9]+)*$`。
- 如果无法确定名称、发现多个候选 Skill 或源目录包含多个 Skill，不要猜测；先向用户说明并询问。

### 2. 检查源 Skill

必须确认：

- 目标目录中存在 `SKILL.md`。
- `SKILL.md` 以 YAML front matter 开始。
- front matter 有 `name` 和 `description`。
- `name` 与最终目录名一致。
- 没有把凭据、密钥、个人隐私、未授权版权材料或明显的临时文件上传进来。
- 依赖的 `references/`、`scripts/`、`assets/` 等相对路径都随 Skill 一起保留。

不要擅自重写 Skill 的核心指令。只在必要时修复路径、格式或元数据，并在最终报告中说明。

### 3. 放入本仓库

本地仓库路径通常是：`/Users/yanqing/Documents/yanqing-skills`。先检查仓库状态：

```bash
git switch main
git pull --ff-only
git status --short
```

- 新 Skill 放到仓库根目录：`<skill-name>/`。
- 如果目标目录不存在，复制整个 Skill 文件夹，保留其内部资源结构。
- 如果目标目录已存在，视为更新已有 Skill；先阅读现有的 `SKILL.md`、`README.md` 和 `CHANGELOG.md`，不要盲目覆盖用户已有内容。
- 不要再放到 `skills/<skill-name>/`；本仓库采用根目录一级 Skill 结构。
- 仓库基础设施目录（`.github/`、`templates/`、`tools/`）不是 Skill，不得作为 Skill 上传。

### 4. 补充仓库文件

每个 Skill 必须有：

```text
<skill-name>/
└── SKILL.md
```

推荐有：

```text
<skill-name>/
├── SKILL.md
├── README.md
└── CHANGELOG.md
```

如果是新增 Skill 且没有 `CHANGELOG.md`，创建：

```markdown
# Changelog

## [0.1.0] - YYYY-MM-DD

### Added

- 首次发布 Skill。
```

如果仓库根目录 README 的 Skills 表中没有该 Skill，新增一行：

```markdown
| `skill-name` | 一句话说明 | [`skill-name`](./skill-name) |
```

### 5. 校验和审阅

```bash
node tools/validate-skills.js
git diff --check
git diff -- <skill-name>
```

确认变更只包含目标 Skill 和必要的根目录 README / 文档更新。校验失败时不得 commit 或 push；先修复问题。

### 6. Commit

一个 commit 尽量只处理一个 Skill。格式：

```bash
git add <skill-name> README.md
git commit -m "<skill-name>: add initial skill"
```

如果是更新：

```bash
git commit -m "<skill-name>: improve workflow"
```

不要把无关 Skill 的变更混入同一个 commit，也不要覆盖或回滚用户未要求处理的未提交变更。

### 7. 推送

用户明确说“上传”“发布”或“同步到 yanqing-skills”时，完成检查后推送：

```bash
git push origin main
```

如果网络、认证或权限失败，保留本地 commit，不要重复创建 commit，并向用户报告准确错误。

## 版本管理

每个 Skill 独立使用语义化版本 tag：

```text
<skill-name>-vMAJOR.MINOR.PATCH
```

新增 Skill：

```bash
git tag -a <skill-name>-v0.1.0 -m "<skill-name> v0.1.0"
git push origin <skill-name>-v0.1.0
```

版本选择：

- `PATCH`：文字、规则、小错误修复，例如 `v1.0.1`
- `MINOR`：增加向后兼容能力，例如 `v1.1.0`
- `MAJOR`：改变核心行为、输入或输出契约，例如 `v2.0.0`

如果用户只说“上传”而没有说“发布版本”，仍然要 commit 和 push，但可以不创建 tag；如需选择版本且无法判断影响，应先询问用户，不要猜测。

发布前更新对应 Skill 的 `CHANGELOG.md`。GitHub Release 是可选的；如果创建，应使用同名 tag。

查看某个 Skill 的历史：

```bash
git log -- <skill-name>
git log --follow -- <skill-name>/SKILL.md
git tag --list '<skill-name>-v*'
```

## 更新已有 Skill

1. 运行 `git log -- <skill-name>` 和 `git tag --list '<skill-name>-v*'`。
2. 阅读现有 Skill 的全部说明和资源引用。
3. 只修改用户指定的 Skill 及必要的根 README。
4. 更新该 Skill 的 `CHANGELOG.md`。
5. 按版本规则选择下一版本。
6. 运行校验、查看 diff、commit、push 和（如果适用）创建 tag。

## 最终报告

完成后必须告诉用户：

- Skill 名称和仓库目录
- 修改或新增了哪些文件
- 校验命令及结果
- commit hash 和 message
- 是否已 push
- 是否创建 tag，以及版本号
- 如果有失败，说明失败步骤和本地是否保留变更

## 安全边界

- 不上传密钥、token、`.env`、个人隐私或未经授权的材料。
- 不执行用户未要求的破坏性命令。
- 不执行 `git reset --hard`、`git checkout --` 或删除用户文件来“清理”工作区。
- 不覆盖用户未提交的修改；发现目标目录存在冲突时先停下询问。
- 除非用户明确要求，不创建 GitHub 仓库、Release、Pull Request 或强制推送。
