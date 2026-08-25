#!/usr/bin/env python3

import argparse
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import yaml

from navigation import write_navigation


MDBOOK_LINK = re.compile(r"^(?P<indent>[ \t]*)(?:-\s+)?\[(?P<title>[^]]+)]\((?P<target>[^)]+)\)\s*$")
MDBOOK_PART = re.compile(r"^#\s+(?P<title>.+?)\s*$")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "documentation"


def title_from_target(target: str) -> str:
    stem = PurePosixPath(target.split("#", 1)[0]).stem
    if stem.lower() in {"index", "readme", "_index"}:
        parent = PurePosixPath(target).parent.name
        stem = parent or "Home"
    return stem.replace("-", " ").replace("_", " ").strip().title()


def destination(target: str) -> dict[str, str]:
    target = target.strip()
    parsed = urlsplit(target)
    if parsed.scheme or target.startswith(("/", "#")):
        return {"url": target}

    source, marker, fragment = target.partition("#")
    source = source.removeprefix("./")
    path = PurePosixPath(source)
    if path.suffix.lower() in {".md", ".markdown"}:
        if path.stem.lower() in {"index", "readme", "_index"}:
            route = "" if str(path.parent) == "." else f"{path.parent.as_posix().strip('/')}/"
        else:
            route = f"{path.with_suffix('').as_posix().strip('/')}/"
        if marker:
            route += f"#{fragment}"
        return {"path": route}
    return {"url": target}


def convert_mkdocs_entry(entry: Any) -> dict[str, Any]:
    if isinstance(entry, str):
        return {"title": title_from_target(entry), **destination(entry)}
    if not isinstance(entry, dict) or len(entry) != 1:
        raise ValueError("each MkDocs nav entry must be a path or a one-key title mapping")
    title, value = next(iter(entry.items()))
    if not isinstance(title, str) or not title.strip():
        raise ValueError("MkDocs nav titles must be non-empty strings")
    if isinstance(value, str):
        return {"title": title, **destination(value)}
    if isinstance(value, list) and value:
        return {
            "id": slugify(title),
            "title": title,
            "children": [convert_mkdocs_entry(child) for child in value],
        }
    raise ValueError(f"MkDocs nav entry {title!r} must contain a path or non-empty list")


def convert_mkdocs(path: Path, group_title: str | None, group_id: str | None) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text())
    if not isinstance(document, dict) or not isinstance(document.get("nav"), list) or not document["nav"]:
        raise ValueError("MkDocs configuration must contain a non-empty 'nav' list")
    title = group_title or document.get("site_name") or "Documentation"
    if not isinstance(title, str):
        raise ValueError("MkDocs site_name must be a string")
    return {
        "groups": [
            {
                "id": group_id or slugify(title),
                "title": title,
                "items": [convert_mkdocs_entry(entry) for entry in document["nav"]],
            }
        ]
    }


def _new_group(title: str, group_id: str | None, index: int) -> dict[str, Any]:
    identifier = group_id or slugify(title)
    if index and group_id is None:
        identifier = f"{identifier}-{index + 1}"
    return {"id": identifier, "title": title, "items": []}


def convert_mdbook(path: Path, group_title: str | None, group_id: str | None) -> dict[str, Any]:
    default_title = group_title or "Documentation"
    groups: list[dict[str, Any]] = []
    current = _new_group(default_title, group_id, 0)
    stack: list[tuple[int, dict[str, Any]]] = []

    for number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("<!--") or line.strip() == "---":
            continue
        part = MDBOOK_PART.match(line)
        if part:
            title = part.group("title")
            if title.lower() == "summary":
                continue
            if current["items"]:
                groups.append(current)
            current = _new_group(title, group_id if not groups else None, len(groups))
            stack.clear()
            continue
        link = MDBOOK_LINK.match(line)
        if not link:
            raise ValueError(f"Unsupported mdBook SUMMARY syntax on line {number}: {line}")

        indent_text = link.group("indent").replace("\t", "    ")
        indent = len(indent_text)
        node = {"title": link.group("title"), **destination(link.group("target"))}
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            stack[-1][1].setdefault("children", []).append(node)
        else:
            current["items"].append(node)
        stack.append((indent, node))

    if current["items"]:
        groups.append(current)
    if not groups:
        raise ValueError("mdBook SUMMARY does not contain any linked pages")
    return {"groups": groups}


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert existing documentation navigation to Zola Docs JSON")
    parser.add_argument("format", choices=("mkdocs", "mdbook"))
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--group-title")
    parser.add_argument("--group-id")
    args = parser.parse_args()

    try:
        if args.format == "mkdocs":
            navigation = convert_mkdocs(args.input, args.group_title, args.group_id)
        else:
            navigation = convert_mdbook(args.input, args.group_title, args.group_id)
        write_navigation(navigation, args.output)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
