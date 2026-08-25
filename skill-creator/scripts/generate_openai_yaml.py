#!/usr/bin/env python3
"""
OpenAI YAML Generator - Creates agents/openai.yaml for a skill folder.

Usage:
    generate_openai_yaml.py <skill_dir> [--name <skill_name>] [--interface key=value]
"""

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

ACRONYMS = {
    "GH",
    "MCP",
    "API",
    "CI",
    "CLI",
    "LLM",
    "PDF",
    "PR",
    "UI",
    "URL",
    "SQL",
}

BRANDS = {
    "openai": "OpenAI",
    "openapi": "OpenAPI",
    "github": "GitHub",
    "pagerduty": "PagerDuty",
    "datadog": "DataDog",
    "sqlite": "SQLite",
    "fastapi": "FastAPI",
}

SMALL_WORDS = {"and", "or", "to", "up", "with"}

ALLOWED_INTERFACE_KEYS = {
    "display_name",
    "short_description",
    "icon_small",
    "icon_large",
    "brand_color",
    "default_prompt",
}


def yaml_quote(value):
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def format_display_name(skill_name):
    words = [word for word in skill_name.split("-") if word]
    formatted = []
    for index, word in enumerate(words):
        lower = word.lower()
        upper = word.upper()
        if upper in ACRONYMS:
            formatted.append(upper)
            continue
        if lower in BRANDS:
            formatted.append(BRANDS[lower])
            continue
        if index > 0 and lower in SMALL_WORDS:
            formatted.append(lower)
            continue
        formatted.append(word.capitalize())
    return " ".join(formatted)


def generate_short_description(display_name):
    description = f"Help with {display_name} tasks"

    if len(description) < 25:
        description = f"Help with {display_name} tasks and workflows"
    if len(description) < 25:
        description = f"Help with {display_name} tasks with guidance"

    if len(description) > 64:
        description = f"Help with {display_name}"
    if len(description) > 64:
        description = f"{display_name} helper"
    if len(description) > 64:
        description = f"{display_name} tools"
    if len(description) > 64:
        suffix = " helper"
        max_name_length = 64 - len(suffix)
        trimmed = display_name[:max_name_length].rstrip()
        description = f"{trimmed}{suffix}"
    if len(description) > 64:
        description = description[:64].rstrip()

    if len(description) < 25:
        description = f"{description} workflows"
        if len(description) > 64:
            description = description[:64].rstrip()

    return description


def read_frontmatter_name(skill_dir):
    skill_md = Path(skill_dir) / "SKILL.md"
    if not skill_md.exists():
        print(f"[ERROR] SKILL.md not found in {skill_dir}")
        return None
    content = skill_md.read_text(encoding="utf-8").lstrip("\ufeff").replace("\r\n", "\n")
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        print("[ERROR] Invalid SKILL.md frontmatter format.")
        return None
    frontmatter_text = match.group(1)

    try:
        try:
            import yaml
            frontmatter = yaml.safe_load(frontmatter_text)
        except ModuleNotFoundError:
            frontmatter = _parse_simple_frontmatter(frontmatter_text)
    except (ValueError, Exception) as exc:
        print(f"[ERROR] Invalid YAML frontmatter: {exc}")
        return None
    if not isinstance(frontmatter, dict):
        print("[ERROR] Frontmatter must be a YAML dictionary.")
        return None
    name = frontmatter.get("name", "")
    if not isinstance(name, str) or not name.strip():
        print("[ERROR] Frontmatter 'name' is missing or invalid.")
        return None
    return name.strip()


def _parse_simple_frontmatter(text):
    def strip_comment(value):
        quote = None
        index = 0
        while index < len(value):
            char = value[index]
            if quote:
                if quote == "'" and char == "'" and index + 1 < len(value) and value[index + 1] == "'":
                    index += 2
                    continue
                if char == quote:
                    quote = None
                index += 1
                continue
            if char in "'\"":
                quote = char
            elif char == "#" and (index == 0 or value[index - 1].isspace()):
                return value[:index].rstrip()
            index += 1
        if quote:
            raise ValueError("fallback parser found an unclosed quoted scalar")
        return value.strip()

    result = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError("fallback parser accepts scalar fields")
        if line[0].isspace():
            continue
        key, value = line.split(":", 1)
        value = strip_comment(value.strip())
        if not value:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            if value.startswith("'"):
                value = value[1:-1].replace("''", "'")
            else:
                value = value[1:-1]
        result[key.strip()] = value
    return result


def _read_existing_interface(path):
    """Read scalar interface fields without dropping user-provided metadata."""
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[ERROR] Cannot read existing {path}: {exc}")
        return None
    try:
        try:
            import yaml
        except ModuleNotFoundError:
            yaml = None
        if yaml is not None:
            document = yaml.safe_load(text)
            interface = document.get("interface", {}) if isinstance(document, dict) else {}
            if not isinstance(interface, dict):
                raise ValueError("interface must be a mapping")
            return {
                key: value
                for key, value in interface.items()
                if key in ALLOWED_INTERFACE_KEYS and isinstance(value, str)
            }

        interface = {}
        interface_seen = False
        in_interface = False
        child_indent = None

        def strip_comment(value):
            quote = None
            for index, char in enumerate(value):
                if quote:
                    if char == quote:
                        quote = None
                    continue
                if char in "'\"":
                    quote = char
                elif char == "#" and (index == 0 or value[index - 1].isspace()):
                    return value[:index].rstrip()
            return value.strip()

        def parse_scalar(value, line_number):
            value = strip_comment(value.strip())
            if not value or value[0] in "[{" or value.startswith(("- ", "? ", "|", ">", "&", "*", "!")):
                raise ValueError(f"unsupported interface value at line {line_number}")
            if value[0] in "'\"":
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError(f"unclosed interface value at line {line_number}")
                value = value[1:-1]
            return value

        for line_number, line in enumerate(text.replace("\r\n", "\n").splitlines(), 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indentation = len(line) - len(line.lstrip(" "))
            stripped = line.strip()
            if indentation == 0 and re.match(r"^interface\s*:", stripped):
                interface_seen = True
                inline = strip_comment(stripped.split(":", 1)[1].strip())
                if inline and inline not in ("{}",):
                    raise ValueError("interface must be a mapping")
                in_interface = True
                child_indent = None
                continue
            if indentation == 0:
                in_interface = False
                child_indent = None
                continue
            if not in_interface:
                continue
            if ":" not in line:
                # Nested list/mapping data belongs to an optional extension;
                # only scalar interface fields are needed for regeneration.
                continue
            if child_indent is None:
                child_indent = indentation
            if indentation != child_indent:
                continue
            key, value = line.strip().split(":", 1)
            if key not in ALLOWED_INTERFACE_KEYS:
                continue
            interface[key] = parse_scalar(value, line_number)
        if interface_seen:
            return interface
        return {}
    except Exception as exc:
        print(f"[ERROR] Invalid existing {path}: {exc}")
    return None


def _merge_interface_block(existing_text, interface_lines):
    """Replace only the interface mapping, preserving extra YAML sections."""
    normalized = existing_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if not line[:1].isspace() and re.fullmatch(r"interface\s*:\s*(?:#.*)?", line.strip())
        ),
        None,
    )
    if start is None:
        return "\n".join(interface_lines + ([""] if lines else []) + lines) + "\n"
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line.startswith((" ", "\t")):
            break
        end += 1
    merged = lines[:start] + interface_lines + lines[end:]
    return "\n".join(merged) + "\n"


def parse_interface_overrides(raw_overrides):
    overrides = {}
    optional_order = []
    for item in raw_overrides:
        if "=" not in item:
            print(f"[ERROR] Invalid interface override '{item}'. Use key=value.")
            return None, None
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            print(f"[ERROR] Invalid interface override '{item}'. Key is empty.")
            return None, None
        if key not in ALLOWED_INTERFACE_KEYS:
            allowed = ", ".join(sorted(ALLOWED_INTERFACE_KEYS))
            print(f"[ERROR] Unknown interface field '{key}'. Allowed: {allowed}")
            return None, None
        overrides[key] = value
        if key not in ("display_name", "short_description") and key not in optional_order:
            optional_order.append(key)
    return overrides, optional_order


def write_openai_yaml(skill_dir, skill_name, raw_overrides):
    overrides, optional_order = parse_interface_overrides(raw_overrides)
    if overrides is None:
        return None

    raw_skill_dir = Path(skill_dir)
    if raw_skill_dir.is_symlink() or not raw_skill_dir.is_dir():
        print("[ERROR] Skill directory must be a real directory")
        return None
    skill_dir = raw_skill_dir.resolve()
    agents_dir = skill_dir / "agents"
    if agents_dir.is_symlink():
        print("[ERROR] agents directory must not be a symlink")
        return None
    if agents_dir.exists() and not agents_dir.is_dir():
        print("[ERROR] agents must be a directory")
        return None
    output_path = agents_dir / "openai.yaml"
    if output_path.is_symlink():
        print("[ERROR] agents/openai.yaml must not be a symlink")
        return None
    existing = _read_existing_interface(output_path)
    if existing is None:
        return None

    display_name = overrides.get("display_name") or existing.get("display_name") or format_display_name(skill_name)
    short_description = overrides.get("short_description") or existing.get("short_description") or generate_short_description(display_name)
    default_prompt = (
        overrides.get("default_prompt")
        or existing.get("default_prompt")
        or f"Use ${skill_name} to complete related Skill tasks."
    )

    if not (25 <= len(short_description) <= 64):
        print(
            "[ERROR] short_description must be 25-64 characters "
            f"(got {len(short_description)})."
        )
        return None
    if not isinstance(default_prompt, str) or not default_prompt.strip():
        print("[ERROR] default_prompt must be a non-empty string.")
        return None

    interface_lines = [
        "interface:",
        f"  display_name: {yaml_quote(display_name)}",
        f"  short_description: {yaml_quote(short_description)}",
        f"  default_prompt: {yaml_quote(default_prompt)}",
    ]

    # Keep existing optional fields (icons/brand color) unless explicitly
    # replaced.  Regenerating UI metadata must not silently erase them.
    optional_keys = ["icon_small", "icon_large", "brand_color"]
    optional_keys.extend(
        key for key in optional_order if key not in optional_keys and key != "default_prompt"
    )
    for key in optional_keys:
        value = overrides.get(key, existing.get(key))
        if value is not None and value != "":
            interface_lines.append(f"  {key}: {yaml_quote(value)}")

    agents_dir.mkdir(parents=True, exist_ok=True)
    existing_mode = (output_path.stat().st_mode & 0o777) if output_path.is_file() else 0o644
    if output_path.is_file():
        original = output_path.read_text(encoding="utf-8")
        content = _merge_interface_block(original, interface_lines)
    else:
        content = "\n".join(interface_lines) + "\n"
    # Replace the destination atomically so a later path swap cannot redirect
    # the write through a symlink outside the Skill.
    descriptor, temporary = tempfile.mkstemp(prefix=".openai.yaml.", dir=agents_dir)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            os.chmod(handle.fileno(), existing_mode)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output_path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    print(f"[OK] Created agents/openai.yaml")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Create agents/openai.yaml for a skill directory.",
    )
    parser.add_argument("skill_dir", help="Path to the skill directory")
    parser.add_argument(
        "--name",
        help="Skill name override (defaults to SKILL.md frontmatter)",
    )
    parser.add_argument(
        "--interface",
        action="append",
        default=[],
        help="Interface override in key=value format (repeatable)",
    )
    args = parser.parse_args()

    raw_skill_dir = Path(args.skill_dir)
    if raw_skill_dir.is_symlink():
        print(f"[ERROR] Skill directory must not be a symlink: {raw_skill_dir}")
        sys.exit(1)
    skill_dir = raw_skill_dir.resolve()
    if not skill_dir.exists():
        print(f"[ERROR] Skill directory not found: {skill_dir}")
        sys.exit(1)
    if not skill_dir.is_dir():
        print(f"[ERROR] Path is not a directory: {skill_dir}")
        sys.exit(1)

    skill_name = args.name or read_frontmatter_name(skill_dir)
    if not skill_name:
        sys.exit(1)

    result = write_openai_yaml(skill_dir, skill_name, args.interface)
    if result:
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
