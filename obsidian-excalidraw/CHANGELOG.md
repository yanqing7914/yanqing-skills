# Changelog

## [1.0.0] - 2026-09-22

### Added

- Initial `obsidian-excalidraw` Skill: create, edit, and validate Obsidian
  Excalidraw drawings (`.excalidraw.md`, parsed format with an LZString
  compressed-json block) through `scripts/excalidraw.mjs`.
- CLI subcommands `layout`, `decode`, `encode --header-from`, and
  `validate [--strict]`, with exit codes `0` OK, `1` validation FAIL, and
  `2` usage/IO error.
- Deterministic layout generation from a node/edge spec, including decision,
  terminal, and blocked node kinds plus rework and blocked edge styles.
- `references/format.md` and `references/gotchas.md` covering the file format,
  binding rules, validation rules, and known failure modes.
- Contract tests under `tests/` for routing, behavior, and completion checks.
