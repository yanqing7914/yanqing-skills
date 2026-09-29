# Obsidian Excalidraw format

## Contents

- [File layout](#file-layout)
- [Scene JSON](#scene-json)
- [Element rules](#element-rules)
- [Arrow rules](#arrow-rules)
- [Layout spec](#layout-spec)
- [Validation rules](#validation-rules)

## File layout

A `.excalidraw.md` file in "parsed" mode has four parts. The blank line after the opening `---` is what the plugin writes; keep it.

````
---

excalidraw-plugin: parsed
tags: [excalidraw, <topic>]

---
==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠==

# Excalidraw Data

## Text Elements
<text> ^<element-id>

%%
## Drawing
```compressed-json
<base64, split into 256-char lines separated by blank lines>
```
%%
````

- The drawing block is `LZString.compressToBase64(JSON.stringify(scene))`. Some older files use an uncompressed ```` ```json ```` block; `decode` reads both, `encode` always writes compressed-json.
- `## Text Elements` mirrors every live text element as `<text> ^<id>`. The plugin uses it for search and links; it must match the scene exactly.
- `encode --header-from <original>` keeps the original frontmatter and banner byte-for-byte.

## Scene JSON

```json
{"type":"excalidraw","version":2,"source":"...","elements":[...],"appState":{"gridSize":null,"viewBackgroundColor":"#ffffff"},"files":{}}
```

`decode` prints this object; `encode` requires an `elements` array.

## Element rules

- Every element needs a unique `id` and numeric `version`, `versionNonce`, `updated`. On every edit, increment `version`, set a new `versionNonce`, and update `updated`, or the plugin may keep its cached copy.
- Deleted elements (`isDeleted: true`) are ignored by validation and Text Elements.
- Text inside a shape: text has `containerId: <shapeId>`, and the shape's `boundElements` contains `{"type":"text","id":<textId>}`. Both sides are required.
- Colors used by this skill: process `#1e1e1e`/`#e7f5ff`, decision `#e67700`/`#fff3bf`, terminal `#2b8a3e`/`#d3f9d8`, blocked `#c92a2a`/`#ffe3e3`.

## Arrow rules

- `x`,`y` are the absolute start point. `points` are relative to `x`,`y`, so `points[0]` is always `[0,0]`. `width`/`height` equal the bounding box of `points`.
- Bindings: `startBinding`/`endBinding` = `{"mode":"orbit","elementId":<shapeId>,"fixedPoint":[fx,fy]}`, where `fixedPoint` is the endpoint position as a fraction of the target box. The target's `boundElements` must contain `{"type":"arrow","id":<arrowId>}`.
- Put endpoints 4–8px outside the target border. Inside the box renders wrong; more than 40px away is treated as detached.
- Arrow labels are text elements with `containerId: <arrowId>`, listed in the arrow's `boundElements` as `{"type":"text"}`.
- Use `roundness: {"type":2}`. Rework/back edges: dashed `#6741d9`. Blocked edges: dashed `#c92a2a`.

## Layout spec

Input for `excalidraw.mjs layout spec.json out.excalidraw.md [--tags a,b] [--force]`:

```json
{
  "title": "Optional title",
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

- `kind`: `process` (default), `decision` (diamond), `terminal`, `blocked`.
- `style`: `normal`, `rework`, `blocked`. An edge pointing to an earlier node in `nodes` order is a back edge; it defaults to `rework` and routes through a lane on the right.
- Node order defines layering (longest path over forward edges); list nodes in flow order.
- `label` may contain `\n` for multi-line text.
- Ids are deterministic: node text `<id>-t`, arrows `e<i>-<from>-<to>`, arrow labels `<arrowId>-t`. Same spec and tags produce the same bytes.

## Validation rules

`validate` errors (exit 1): duplicate ids; missing version fields; `boundElements` pointing at missing elements; text/container mismatch; one-way arrow binding; `points[0]` not `[0,0]`; endpoint more than 40px from its target; Text Elements section missing, stale, missing an entry, or holding an orphan.

Warnings (exit 0, exit 1 with `--strict`): an endpoint inside its target box; two arrows crossing.
