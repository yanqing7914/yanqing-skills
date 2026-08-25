# yanqing-skills

个人维护的 AI Skills 集合。所有 Skill 放在同一个 Git 仓库中，但通过独立目录、commit、CHANGELOG 和带前缀的 Git tag 分别管理。

- 远端仓库：<https://github.com/yanqing7914/yanqing-skills>
- 默认分支：`main`
- 操作规范：[`AGENT.md`](AGENT.md)

## 目录

```text
skills/
  <skill-name>/
    SKILL.md       # 必需：AI 执行指令
    README.md      # 推荐：面向人的说明
    CHANGELOG.md   # 推荐：该 Skill 的版本记录
    examples/      # 可选
    references/    # 可选
    scripts/       # 可选
```

## 当前 Skills

目前还没有正式 Skill。新增 Skill 请先阅读 [`AGENT.md`](AGENT.md) 的完整流程。

## 日常管理流程

### 首次在新电脑使用

```bash
git clone https://github.com/yanqing7914/yanqing-skills.git
cd yanqing-skills
```

### 开始修改前

```bash
git switch main
git pull --ff-only
```

确认工作区状态，避免覆盖尚未提交的内容：

```bash
git status
```

### 新增一个 Skill

以 `code-review` 为例：

```bash
mkdir -p skills/code-review
cp templates/basic-skill/SKILL.md skills/code-review/SKILL.md
```

编辑 `skills/code-review/SKILL.md`，确保目录名和 front matter 中的 `name` 都是 `code-review`。推荐同时添加：

```text
skills/code-review/
  SKILL.md
  README.md
  CHANGELOG.md
```

### 校验、提交和上传

```bash
node tools/validate-skills.js
git diff --check
git diff -- skills/code-review
git add skills/code-review
git commit -m "code-review: add initial skill"
git push
```

一个 commit 尽量只处理一个 Skill，commit subject 使用 `<skill-name>: <change>` 格式。

### 发布单个 Skill 版本

```bash
git tag -a code-review-v0.1.0 -m "code-review v0.1.0"
git push origin code-review-v0.1.0
```

发布前应更新该 Skill 的 `CHANGELOG.md`。更完整的新增、更新和发布规则见 [`AGENT.md`](AGENT.md)。

## 版本约定

本仓库使用带 Skill 名称前缀的 tag：

```text
<skill-name>-vMAJOR.MINOR.PATCH
```

例如：`code-review-v1.0.0`、`meeting-summary-v0.2.0`。

- `MAJOR`：不兼容的行为或结构变化
- `MINOR`：向后兼容的新能力
- `PATCH`：向后兼容的修复或文字调整

查看某个 Skill 的历史：

```bash
git log -- skills/<skill-name>
git log --follow -- skills/<skill-name>/SKILL.md
git tag --list '<skill-name>-v*'
```

## 校验

```bash
node tools/validate-skills.js
```

## 许可

见 [`LICENSE`](LICENSE)。
