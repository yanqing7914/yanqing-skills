# Obsidian Excalidraw

在 Obsidian 仓库里创建、编辑、校验 Excalidraw 图（`.excalidraw.md`）。

Obsidian 的 Excalidraw 文件把整个画布压进一个 `compressed-json` 代码块（`LZString.compressToBase64` 之后的 JSON）。手写或者用正则改这个块，结果一定是坏图：箭头脱离图形、`## Text Elements` 段过期、Obsidian 打开直接报错。这个 skill 用一个确定性的 CLI 包住整条链路，所有读写都走 `scripts/excalidraw.mjs`。

## 安装

一次性安装依赖（固定 `lz-string@1.5.0`）：

```bash
cd scripts && npm ci --no-bin-links
```

`--no-bin-links` 是必需的：默认安装会在 `node_modules/.bin` 下建符号链接，而 skill 校验不允许目录里出现 symlink。

需要 Node >= 18。

## 用法

```bash
X="node <skill 目录>/scripts/excalidraw.mjs"
```

四个子命令：

```bash
# 从 layout spec 生成新图
$X layout spec.json out.excalidraw.md --tags excalidraw,flow

# 解出场景 JSON 以便修改
$X decode in.excalidraw.md > scene.json

# 改完再编回去，沿用原文件的 frontmatter / banner
$X encode scene.json out.excalidraw.md --header-from in.excalidraw.md

# 校验
$X validate out.excalidraw.md
$X validate out.excalidraw.md --strict
```

退出码：`0` 通过，`1` 校验失败，`2` 用法或 IO 错误（包括拒绝覆盖已存在的文件）。

### layout spec

画新流程图时不要手搓元素，写一份 spec 交给 `layout`：

```json
{
  "title": "发布流程",
  "nodes": [
    {"id": "req", "label": "需求", "kind": "process"},
    {"id": "gate", "label": "需要发布?", "kind": "decision"},
    {"id": "done", "label": "完成", "kind": "terminal"}
  ],
  "edges": [
    {"from": "req", "to": "gate"},
    {"from": "gate", "to": "done", "label": "否"},
    {"from": "gate", "to": "req", "label": "返工", "style": "rework"}
  ]
}
```

- `kind`：`process`（默认矩形）、`decision`（菱形）、`terminal`、`blocked`，各自有配套配色。
- `style`：`normal`、`rework`（紫色虚线）、`blocked`（红色虚线）。指回靠前节点的边会自动按 `rework` 处理并走右侧通道。
- 节点顺序决定分层，`label` 支持 `\n` 换行。
- 元素 id 是确定性的，同一份 spec 加同样的 `--tags` 产出字节一致的文件。

## 校验会抓什么

`validate` 报错（exit 1）的典型情况：元素 id 重复、缺 `version` / `versionNonce` / `updated`、`boundElements` 指向不存在的元素、文字与容器不匹配、箭头单向绑定、`points[0]` 不是 `[0,0]`、箭头端点离目标超过 40px、`## Text Elements` 段缺失或过期。

WARN（默认 exit 0，`--strict` 下升级为失败）：箭头端点落在目标框内部、两条箭头交叉。用 `layout` 生成的图应该跑 `--strict`；手工改过的图要么修掉 WARN，要么在交付时逐条说明。

## 安全规则

- 输出写新文件。覆盖已有图需要用户明确同意，只有那时才传 `--force`。
- 编辑走「decode 到副本 → 改 JSON → encode 到新文件 → validate 通过」，原文件留着。
- 源文档里没有的步骤、分支、标签不要自己编，先问。
- 文件由用户在 Obsidian 的 Excalidraw 视图里打开；如果插件缓存了旧版本，提醒他们重新打开。

## 常见坑

`references/gotchas.md` 记了 7 条已知失败模式和对应的处理规则，包括箭头脱离绑定、`## Text Elements` 过期、`points` 用了绝对坐标、箭头头部藏进图形里，以及 `node_modules/.bin` 的 symlink 导致校验失败。任何手工改 JSON 之前先读它。

## 测试

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

依赖没装时相关用例会跳过，并提示先跑 `npm ci --no-bin-links`。

## 文档

- [`SKILL.md`](./SKILL.md)：路由边界与工作流。
- [`references/format.md`](./references/format.md)：文件格式、元素与绑定规则、layout spec schema、校验规则。
- [`references/gotchas.md`](./references/gotchas.md)：已知坑与替代做法。
