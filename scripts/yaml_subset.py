"""Parse the small YAML subset used by service.yaml and mapping.yaml."""

from __future__ import annotations


def parse(text: str):
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))
    value, _ = _parse_block(lines, 0, 0)
    return value


def _parse_block(lines, index, indent):
    if index >= len(lines):
        return {}, index
    if lines[index][1].startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_dict(lines, index, indent)


def _parse_dict(lines, index, indent):
    result = {}
    while index < len(lines):
        level, text = lines[index]
        if level < indent or text.startswith("- "):
            break
        if level > indent:
            raise SystemExit(f"unexpected indent: {text}")
        key, _, rest = text.partition(":")
        key = key.strip()
        rest = rest.strip()
        index += 1
        if rest == "":
            if index < len(lines) and lines[index][0] > level:
                child, index = _parse_block(lines, index, lines[index][0])
                result[key] = child
            else:
                result[key] = ""
        elif rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            result[key] = [] if not inner else [item.strip() for item in inner.split(",")]
        else:
            result[key] = rest.strip("\"'")
    return result, index


def _parse_list(lines, index, indent):
    result = []
    while index < len(lines):
        level, text = lines[index]
        if level < indent or not text.startswith("- "):
            break
        item = text[2:].strip()
        index += 1
        if item == "":
            child, index = _parse_block(lines, index, lines[index][0])
            result.append(child)
            continue
        if ":" in item:
            key, _, rest = item.partition(":")
            node = {key.strip(): rest.strip().strip("\"'")}
            if rest.strip() == "" and index < len(lines) and lines[index][0] > level:
                child, index = _parse_block(lines, index, lines[index][0])
                node[key.strip()] = child
            elif rest.strip().startswith("[") and rest.strip().endswith("]"):
                inner = rest.strip()[1:-1].strip()
                node[key.strip()] = [] if not inner else [part.strip() for part in inner.split(",")]
            while index < len(lines) and lines[index][0] > level and not lines[index][1].startswith("- "):
                child, index = _parse_dict(lines, index, lines[index][0])
                node.update(child)
            result.append(node)
        else:
            result.append(item.strip("\"'"))
    return result, index
