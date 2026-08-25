# My Skills

个人维护的 AI Skills 集合。所有 Skill 放在同一个 Git 仓库中，但通过目录、commit、CHANGELOG 和带前缀的 Git tag 独立管理。

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
