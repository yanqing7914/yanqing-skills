# Routing cases

Machine-readable source: `skill_contract.json` → `sections.routing`.

| id | kind | prompt | expected |
| --- | --- | --- | --- |
| pos-flowchart | positive | 在 Obsidian 里用 Excalidraw 画一张发布流程图 | use (layout) |
| pos-spec-to-drawing | positive | 把 spec 画成 .excalidraw.md | use (layout) |
| pos-fix-arrows | positive | 修一下这张 Excalidraw 图的连线 | use (decode/edit/encode) |
| nsp-crooked-arrows | nonstandard_positive | obsidian 里那张白板图箭头歪了 | use |
| nsp-add-node | nonstandard_positive | 给 .excalidraw.md 加个节点 | use |
| neg-plain-note | negative | 在 Obsidian 里整理普通读书笔记 | obsidian-vault |
| neg-mermaid | negative | 在聊天里画 Mermaid 时序图 | visualize |
| adj-lark-whiteboard | adjacent | 在飞书文档画板里画架构图 | lark-whiteboard |
| adj-vault-manager | adjacent | 整理 vault 目录和双链 | obsidian-vault-manager |
