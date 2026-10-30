"""Parse and format the YAML subset used by service.yaml, jobs.yaml, and mapping.yaml.

Supports nested mappings, block and inline lists, inline mappings, booleans,
integers, null, and quoted strings containing commas or colons (such as cron
expressions).
"""

from __future__ import annotations

import re

_INT_RE = re.compile(r"^-?[0-9]+$")
_FLOAT_RE = re.compile(r"^-?[0-9]+\.[0-9]+$")


def _strip_comment(raw: str) -> str:
    in_single = False
    in_double = False
    for idx, ch in enumerate(raw):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if idx == 0 or raw[idx - 1].isspace():
                return raw[:idx]
    return raw


def _split_top_level(text: str, sep: str = ",") -> list[str]:
    items: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    depth = 0
    for ch in text:
        if ch == "'" and not in_double:
            in_single = not in_single
            buf.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
        elif not in_single and not in_double:
            if ch in "[{":
                depth += 1
                buf.append(ch)
            elif ch in "]}":
                depth = max(0, depth - 1)
                buf.append(ch)
            elif ch == sep and depth == 0:
                items.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        items.append(tail)
    return items


def _parse_scalar(text: str):
    val = text.strip()
    if val == "":
        return ""
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    if val == "[]":
        return []
    if val == "{}":
        return {}
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in _split_top_level(inner, ",")]
    if val.startswith("{") and val.endswith("}"):
        inner = val[1:-1].strip()
        if not inner:
            return {}
        out = {}
        for part in _split_top_level(inner, ","):
            key, _, rest = part.partition(":")
            out[key.strip().strip("\"'")] = _parse_scalar(rest)
        return out
    low = val.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"null", "~"}:
        return None
    if _INT_RE.fullmatch(val):
        return int(val)
    if _FLOAT_RE.fullmatch(val):
        return float(val)
    return val


def parse(text: str):
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        cleaned = _strip_comment(raw).rstrip()
        if not cleaned.strip():
            continue
        indent = len(cleaned) - len(cleaned.lstrip(" "))
        lines.append((indent, cleaned.strip()))
    value, _ = _parse_block(lines, 0, 0)
    return value


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int):
    if index >= len(lines):
        return {}, index
    if lines[index][1].startswith("- ") or lines[index][1] == "-":
        return _parse_list(lines, index, indent)
    return _parse_dict(lines, index, indent)


def _partition_key_value(text: str) -> tuple[str, str, str]:
    in_single = False
    in_double = False
    for idx, ch in enumerate(text):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ":" and not in_single and not in_double:
            if idx + 1 == len(text) or text[idx + 1].isspace():
                return text[:idx], ":", text[idx + 1 :]
    return text, "", ""


def _parse_dict(lines: list[tuple[int, str]], index: int, indent: int):
    result = {}
    while index < len(lines):
        level, text = lines[index]
        if level < indent or text.startswith("- ") or text == "-":
            break
        if level > indent:
            raise SystemExit(f"unexpected indent: {text}")
        key, sep, rest = _partition_key_value(text)
        if not sep:
            raise SystemExit(f"expected key: value, got: {text}")
        key = key.strip().strip("\"'")
        rest = rest.strip()
        index += 1
        if rest in {"|", "|-", ">", ">-"}:
            block_lines: list[str] = []
            block_indent: int | None = None
            while index < len(lines) and lines[index][0] > level:
                b_indent, b_text = lines[index]
                if block_indent is None:
                    block_indent = b_indent
                pad = " " * max(0, b_indent - (block_indent or b_indent))
                block_lines.append(pad + b_text)
                index += 1
            joiner = "\n" if rest.startswith("|") else " "
            joined = joiner.join(block_lines)
            if not rest.endswith("-") and joined:
                joined += "\n"
            result[key] = joined
        elif rest == "":
            if index < len(lines) and lines[index][0] > level:
                child, index = _parse_block(lines, index, lines[index][0])
                result[key] = child
            else:
                result[key] = ""
        else:
            result[key] = _parse_scalar(rest)
    return result, index


def _parse_list(lines: list[tuple[int, str]], index: int, indent: int):
    result = []
    while index < len(lines):
        level, text = lines[index]
        if level < indent or not (text.startswith("- ") or text == "-"):
            break
        item = text[2:].strip() if text.startswith("- ") else ""
        index += 1
        if item == "":
            if index < len(lines) and lines[index][0] > level:
                child, index = _parse_block(lines, index, lines[index][0])
                result.append(child)
            else:
                result.append("")
            continue
        key, sep, rest = _partition_key_value(item)
        if sep:
            k = key.strip().strip("\"'")
            r = rest.strip()
            node = {}
            if r == "":
                if index < len(lines) and lines[index][0] > level and (
                    lines[index][1].startswith("- ") or lines[index][0] > level + 2
                ):
                    child, index = _parse_block(lines, index, lines[index][0])
                    node[k] = child
                else:
                    node[k] = ""
            else:
                node[k] = _parse_scalar(r)
            while index < len(lines) and lines[index][0] > level and not (
                lines[index][1].startswith("- ") or lines[index][1] == "-"
            ):
                child, index = _parse_dict(lines, index, lines[index][0])
                node.update(child)
            result.append(node)
        else:
            result.append(_parse_scalar(item))
    return result, index


def _format_scalar(value) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if (
        text == ""
        or any(ch in text for ch in (":", "#", ",", "[", "]", "{", "}", "*", "&", "!"))
        or text.lower() in {"true", "false", "null", "~"}
        or _INT_RE.fullmatch(text)
    ):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def dump(data, indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                if not value:
                    lines.append(f"{prefix}{key}: {{}}")
                else:
                    lines.append(f"{prefix}{key}:")
                    lines.append(dump(value, indent + 2).rstrip("\n"))
            elif isinstance(value, list):
                if not value:
                    lines.append(f"{prefix}{key}: []")
                elif all(not isinstance(item, (dict, list)) for item in value):
                    inline = ", ".join(_format_scalar(item) for item in value)
                    lines.append(f"{prefix}{key}: [{inline}]")
                else:
                    lines.append(f"{prefix}{key}:")
                    lines.append(dump(value, indent + 2).rstrip("\n"))
            else:
                lines.append(f"{prefix}{key}: {_format_scalar(value)}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                items = list(item.items())
                if not items:
                    lines.append(f"{prefix}- {{}}")
                    continue
                first_k, first_v = items[0]
                if isinstance(first_v, (dict, list)) and first_v:
                    lines.append(f"{prefix}- {first_k}:")
                    lines.append(dump(first_v, indent + 4).rstrip("\n"))
                elif isinstance(first_v, list) and not first_v:
                    lines.append(f"{prefix}- {first_k}: []")
                elif isinstance(first_v, dict) and not first_v:
                    lines.append(f"{prefix}- {first_k}: {{}}")
                else:
                    lines.append(f"{prefix}- {first_k}: {_format_scalar(first_v)}")
                for k, v in items[1:]:
                    lines.append(dump({k: v}, indent + 2).rstrip("\n"))
            else:
                lines.append(f"{prefix}- {_format_scalar(item)}")
    return "\n".join(lines) + "\n"
