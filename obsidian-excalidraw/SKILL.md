---
name: obsidian-excalidraw
description: 在 Obsidian 仓库里创建、编辑、校验 Excalidraw 图（`.excalidraw.md`，parsed 格式、LZString 压缩的 JSON），包括流程图、架构图、泳道/门禁图，以及"把文档/spec 画成 Excalidraw"。适用于："用 excalidraw 画个流程图放到 obsidian"、"把这个 spec 画成图"、"检查这张 excalidraw 的连线"、"给图加一个不需要发布的分支"。不适用于：普通 Obsidian 笔记整理（用 obsidian-vault / obsidian-vault-manager）、飞书画板（用 lark-whiteboard）、Mermaid 或内联图表（用 visualize）、excalidraw.com 在线编辑。
compatibility: Requires node>=18. Run `npm ci --no-bin-links` in scripts/ once before use.
---

# Obsidian Excalidraw

Create and edit Obsidian Excalidraw drawings through `scripts/excalidraw.mjs`. Never hand-write the compressed-json block, and never edit it with regex or string replacement.

## Setup

```bash
SKILL=<this skill dir>          # e.g. ~/.agents/skills/obsidian-excalidraw
(cd "$SKILL/scripts" && npm ci --no-bin-links) # once; pinned lz-string@1.5.0, no symlinks
X="node $SKILL/scripts/excalidraw.mjs"
```

Exit codes: `0` OK, `1` validation FAIL, `2` usage/IO error (includes refused overwrite).

## Workflow

1. Find the vault and target path. Read the source doc/spec first; every node and edge must trace to it.
2. Pick a mode:
   - New flow diagram: write a layout spec (see [format.md](references/format.md#layout-spec)) and run `$X layout spec.json "<out>.excalidraw.md" --tags excalidraw,<topic>`.
   - Edit an existing drawing: `$X decode in.md > scene.json`, edit elements in JSON (keep bindings mutual, bump `version`/`versionNonce`/`updated`), then `$X encode scene.json out.md --header-from in.md`.
3. Validate: `$X validate out.md` must print `OK`. Use `--strict` for drawings produced by `layout`; for hand-edited drawings, fix or explicitly report each `WARN`.
4. Report the file path, element/arrow counts, and remaining warnings.

## Safety rules

- Write new output to a new file. Overwriting an existing drawing needs explicit user approval, and only then pass `--force`.
- When editing, work on a decoded copy and keep the original until the new file validates.
- Do not invent flow steps, branches, or labels that the source does not contain; ask instead.
- The user opens the file in Obsidian's Excalidraw view; tell them to reopen it if the plugin had it cached.

## Completion checks

- `validate` exits 0 and the `OK` line is quoted in the handoff.
- Every node/edge maps to the source document; missing branches are named, not silently dropped.
- No existing drawing was overwritten without approval.

## References

- [format.md](references/format.md): file format, element and binding rules, layout spec schema.
- [gotchas.md](references/gotchas.md): known failure modes and their replacement rules. Read before any manual JSON edit.
