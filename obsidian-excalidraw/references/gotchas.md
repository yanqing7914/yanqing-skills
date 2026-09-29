# Gotchas

Each entry: symptom, tempting shortcut, root cause, replacement rule, regression assertion.

## 1. Drawing block not found

- Symptom: decode reports no drawing, or finds an empty scene.
- Tempting shortcut: match only ```` ```json ````, or grab the text between `%%` markers.
- Root cause: parsed-mode files use ```` ```compressed-json ```` with base64 split over blank lines.
- Replacement rule: always read through `excalidraw.mjs decode`; it matches both fence types and strips whitespace before decompressing.
- Regression assertion: `test_decode_encode_roundtrip` decodes the real fixture and gets the same JSON after re-encoding.

## 2. Arrow detaches when a box moves

- Symptom: in Obsidian, moving a box leaves the arrow behind.
- Tempting shortcut: set only the arrow's `startBinding`/`endBinding`.
- Root cause: Excalidraw binds both ways; the shape must list the arrow in `boundElements`.
- Replacement rule: whenever you add or retarget a binding, update the target shape's `boundElements` in the same edit.
- Regression assertion: `test_broken_binding_fails` removes the shape-side entry and expects `FAIL` with "one-way".

## 3. Text Elements section out of sync

- Symptom: search/links show old labels, or the plugin rewrites the file on open.
- Tempting shortcut: edit the JSON text only, or patch the markdown section by hand.
- Root cause: the `## Text Elements` list is a mirror of the scene and must match every live text element.
- Replacement rule: never hand-edit the section; `encode` regenerates it from the scene.
- Regression assertion: `test_stale_text_section_fails` edits one label in the section and expects `FAIL` with "stale".

## 4. Arrow renders far from where it should

- Symptom: arrows shoot off-canvas or start in the wrong place.
- Tempting shortcut: write absolute coordinates into `points`.
- Root cause: `points` are relative to the arrow's `x`,`y`; `points[0]` must be `[0,0]`.
- Replacement rule: set `x`,`y` to the absolute start, subtract it from every point, and recompute `width`/`height`.
- Regression assertion: validate rejects `points[0]` other than `[0,0]` (`test_absolute_points_fail`).

## 5. Arrowhead hidden inside a box

- Symptom: the arrowhead is covered by the box fill, or the line appears to start mid-box.
- Tempting shortcut: point the endpoint at the box center.
- Root cause: endpoints inside the target's bounds render under the shape.
- Replacement rule: place endpoints 4–8px outside the border and set `fixedPoint` accordingly.
- Regression assertion: `layout` output passes `validate --strict` (`test_layout_strict_valid`); the fixture's inside endpoints surface as `WARN`.

## 6. Existing drawing overwritten

- Symptom: the user's hand-tuned drawing is replaced by a generated one.
- Tempting shortcut: write straight to the existing path.
- Root cause: the file is the only copy of manual layout work, and Obsidian has no default version history.
- Replacement rule: write to a new file; pass `--force` only after the user explicitly approves overwriting that path.
- Regression assertion: `test_layout_refuses_overwrite` expects exit 2 without `--force`.

## 7. Skill validation fails on `node_modules/.bin` symlink

- Symptom: `quick_validate.py` reports `Skill must not contain symlinks: scripts/node_modules/.bin/lz-string`.
- Tempting shortcut: delete `.bin` by hand after every install.
- Root cause: plain `npm ci` creates bin symlinks; skills must be symlink-free so they copy cleanly across agents.
- Replacement rule: always install with `npm ci --no-bin-links`.
- Regression assertion: `test_creator_require_contract` runs `quick_validate.py --require-contract` and expects success.
