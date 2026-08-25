#!/usr/bin/env python3

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from navigation import (  # noqa: E402
    MAX_NAVIGATION_DEPTH,
    NavigationError,
    load_navigation,
    validate_navigation,
)


def expect_invalid(data: object, message: str) -> None:
    try:
        validate_navigation(data)
    except NavigationError as error:
        if message not in str(error):
            raise AssertionError(f"Expected {message!r} in {str(error)!r}") from error
    else:
        raise AssertionError("Expected invalid navigation")


valid = {
    "groups": [
        {
            "id": "guides",
            "title": "Guides",
            "items": [
                {
                    "title": "Start",
                    "path": "start/",
                    "children": [
                        {
                            "id": "concepts",
                            "title": "Concepts",
                            "children": [{"title": "Model", "path": "start/model/"}],
                        }
                    ],
                },
                {"title": "External", "url": "https://example.com/"},
            ],
        }
    ]
}
normalized, count = validate_navigation(valid)
assert normalized == valid
assert count == 4
legacy, _ = validate_navigation(valid["groups"])
assert legacy == valid

expect_invalid({"groups": []}, "non-empty array")
expect_invalid(
    {"groups": [{"id": "guides", "title": "Guides", "items": [{"title": "No target"}]}]},
    "requires 'path' or 'url'",
)
expect_invalid(
    {
        "groups": [
            {
                "id": "guides",
                "title": "Guides",
                "items": [{"title": "Both", "path": "both/", "url": "/both/"}],
            }
        ]
    },
    "both 'path' and 'url'",
)
expect_invalid(
    {
        "groups": [
            {
                "id": "guides",
                "title": "Guides",
                "items": [
                    {"title": "First", "path": "same/"},
                    {"title": "Second", "path": "same/"},
                ],
            }
        ]
    },
    "duplicates navigation identity",
)

def navigation_at_depth(max_depth: int) -> dict[str, object]:
    deep_node: dict[str, object] = {"title": "Level 1", "path": "level-1/"}
    cursor = deep_node
    for depth in range(2, max_depth + 1):
        child: dict[str, object] = {"title": f"Level {depth}", "path": f"level-{depth}/"}
        cursor["children"] = [child]
        cursor = child
    return {"groups": [{"id": "deep", "title": "Deep", "items": [deep_node]}]}


_, deep_count = validate_navigation(navigation_at_depth(MAX_NAVIGATION_DEPTH))
assert deep_count == MAX_NAVIGATION_DEPTH
expect_invalid(
    navigation_at_depth(MAX_NAVIGATION_DEPTH + 1),
    "exceeds the supported navigation depth",
)

with tempfile.TemporaryDirectory() as temporary_directory:
    temporary = Path(temporary_directory)
    json_path = temporary / "navigation.json"
    json_path.write_text(json.dumps(valid))
    assert load_navigation(json_path) == valid

    toml_path = temporary / "navigation.toml"
    toml_path.write_text(
        """\
[[groups]]
id = "guides"
title = "Guides"

[[groups.items]]
title = "Start"
path = "start/"
"""
    )
    assert load_navigation(toml_path)["groups"][0]["items"][0]["path"] == "start/"

    unsupported_path = temporary / "navigation.yaml"
    unsupported_path.write_text("groups: []\n")
    try:
        load_navigation(unsupported_path)
    except NavigationError as error:
        assert ".json or .toml" in str(error)
    else:
        raise AssertionError("Expected unsupported navigation format")

schema = json.loads((ROOT / "schemas/navigation.schema.json").read_text())
assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
assert schema["$defs"]["node"]["properties"]["children"]["items"]["$ref"] == "#/$defs/node"

print("navigation schema and validation: 15 checks passed")
