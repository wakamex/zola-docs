#!/usr/bin/env python3

import json
import tomllib
from pathlib import Path
from typing import Any


MAX_NAVIGATION_DEPTH = 20
GROUP_KEYS = {"id", "title", "path", "url", "items"}
NODE_KEYS = {"id", "title", "path", "url", "children", "sidebar_children"}


class NavigationError(ValueError):
    pass


def load_navigation(path: Path) -> Any:
    if path.suffix == ".json":
        return json.loads(path.read_text())
    if path.suffix == ".toml":
        return tomllib.loads(path.read_text())
    raise NavigationError("navigation file must use a .json or .toml extension")


def normalize_navigation(data: Any) -> dict[str, list[dict[str, Any]]]:
    if isinstance(data, list):
        groups = data
    elif isinstance(data, dict) and set(data) == {"groups"}:
        groups = data["groups"]
    else:
        raise NavigationError("navigation root must be an array or an object containing only 'groups'")
    if not isinstance(groups, list) or not groups:
        raise NavigationError("navigation groups must be a non-empty array")
    return {"groups": groups}


def _nonempty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NavigationError(f"{location} must be a non-empty string")
    return value


def _string(value: Any, location: str) -> str:
    if not isinstance(value, str):
        raise NavigationError(f"{location} must be a string")
    return value


def _validate_destination(item: dict[str, Any], location: str, allow_missing: bool) -> None:
    has_path = "path" in item
    has_url = "url" in item
    if has_path and has_url:
        raise NavigationError(f"{location} cannot contain both 'path' and 'url'")
    if not allow_missing and not has_path and not has_url:
        raise NavigationError(f"{location} requires 'path' or 'url'")
    if has_path:
        path = _string(item["path"], f"{location}.path")
        if path.startswith("/"):
            raise NavigationError(f"{location}.path must not start with '/'; use 'url' for absolute URLs")
    if has_url:
        _nonempty_string(item["url"], f"{location}.url")


def _validate_nodes(
    nodes: Any,
    location: str,
    depth: int,
    identities: set[str],
) -> int:
    if not isinstance(nodes, list) or not nodes:
        raise NavigationError(f"{location} must be a non-empty array")
    if depth > MAX_NAVIGATION_DEPTH:
        raise NavigationError(
            f"{location} exceeds the supported navigation depth of {MAX_NAVIGATION_DEPTH}"
        )
    count = 0
    for index, node in enumerate(nodes):
        node_location = f"{location}[{index}]"
        if not isinstance(node, dict):
            raise NavigationError(f"{node_location} must be an object")
        unknown = set(node) - NODE_KEYS
        if unknown:
            raise NavigationError(f"{node_location} contains unknown keys: {', '.join(sorted(unknown))}")
        _nonempty_string(node.get("title"), f"{node_location}.title")
        children = node.get("children")
        _validate_destination(node, node_location, allow_missing=children is not None)
        if "id" in node:
            _nonempty_string(node["id"], f"{node_location}.id")
        if "sidebar_children" in node and not isinstance(node["sidebar_children"], bool):
            raise NavigationError(f"{node_location}.sidebar_children must be a boolean")
        if "sidebar_children" in node and children is None:
            raise NavigationError(f"{node_location}.sidebar_children requires 'children'")

        identity = node.get("id") or node.get("path") or node.get("url")
        if identity:
            if identity in identities:
                raise NavigationError(f"{node_location} duplicates navigation identity {identity!r}")
            identities.add(identity)

        count += 1
        if children is not None:
            count += _validate_nodes(children, f"{node_location}.children", depth + 1, identities)
    return count


def validate_navigation(data: Any) -> tuple[dict[str, list[dict[str, Any]]], int]:
    normalized = normalize_navigation(data)
    group_ids: set[str] = set()
    node_count = 0
    for index, group in enumerate(normalized["groups"]):
        location = f"groups[{index}]"
        if not isinstance(group, dict):
            raise NavigationError(f"{location} must be an object")
        unknown = set(group) - GROUP_KEYS
        if unknown:
            raise NavigationError(f"{location} contains unknown keys: {', '.join(sorted(unknown))}")
        group_id = _nonempty_string(group.get("id"), f"{location}.id")
        if group_id in group_ids:
            raise NavigationError(f"{location}.id duplicates {group_id!r}")
        group_ids.add(group_id)
        _nonempty_string(group.get("title"), f"{location}.title")
        _validate_destination(group, location, allow_missing=True)
        node_count += _validate_nodes(group.get("items"), f"{location}.items", 1, set())
    return normalized, node_count


def write_navigation(data: Any, path: Path) -> None:
    normalized, _ = validate_navigation(data)
    path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n")
