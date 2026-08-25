#!/usr/bin/env python3

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any


def read_routes(path: Path) -> set[str]:
    routes = {
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if not routes:
        raise ValueError(f"route snapshot is empty: {path}")
    invalid = sorted(route for route in routes if not route.startswith("/"))
    if invalid:
        raise ValueError(f"routes must start with '/': {invalid[0]}")
    return routes


def analyze_site(site: dict[str, Any], base: Path) -> dict[str, Any]:
    name = site.get("name")
    versions = site.get("versions")
    if not isinstance(name, str) or not name:
        raise ValueError("each site requires a non-empty name")
    if not isinstance(versions, list) or len(versions) < 2:
        raise ValueError(f"{name} requires at least two versions")
    snapshots: dict[str, set[str]] = {}
    for version in versions:
        if not isinstance(version, dict):
            raise ValueError(f"{name} versions must be tables")
        identifier = version.get("id")
        routes_path = version.get("routes")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"{name} version requires a non-empty id")
        if identifier in snapshots:
            raise ValueError(f"{name} duplicates version {identifier!r}")
        if not isinstance(routes_path, str) or not routes_path:
            raise ValueError(f"{name} {identifier} requires a routes file")
        snapshots[identifier] = read_routes((base / routes_path).resolve())

    union = set().union(*snapshots.values())
    real_pages = sum(len(routes) for routes in snapshots.values())
    by_version = {
        identifier: {
            "routes": len(routes),
            "tombstones": len(union - routes),
        }
        for identifier, routes in snapshots.items()
    }
    tombstones = sum(entry["tombstones"] for entry in by_version.values())
    shell_bytes = site.get("shell_bytes", 0)
    if not isinstance(shell_bytes, int) or isinstance(shell_bytes, bool) or shell_bytes < 0:
        raise ValueError(f"{name} shell_bytes must be a non-negative integer")
    return {
        "name": name,
        "versions": len(snapshots),
        "unique_routes": len(union),
        "real_pages": real_pages,
        "tombstones": tombstones,
        "tombstones_per_real_page": round(tombstones / real_pages, 4),
        "total_file_amplification": round((real_pages + tombstones) / real_pages, 4),
        "estimated_tombstone_bytes": tombstones * shell_bytes,
        "by_version": by_version,
    }


def analyze(path: Path) -> list[dict[str, Any]]:
    document = tomllib.loads(path.read_text())
    sites = document.get("sites") if isinstance(document, dict) else None
    if not isinstance(sites, list) or not sites:
        raise ValueError("benchmark configuration requires [[sites]] entries")
    return [analyze_site(site, path.parent) for site in sites]


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure cross-version tombstone growth")
    parser.add_argument("config", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        results = analyze(args.config)
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        raise SystemExit(str(error)) from error
    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
        return
    print("site\tversions\troutes\treal pages\ttombstones\tfile amplification")
    for result in results:
        print(
            f"{result['name']}\t{result['versions']}\t{result['unique_routes']}\t"
            f"{result['real_pages']}\t{result['tombstones']}\t"
            f"{result['total_file_amplification']}x"
        )


if __name__ == "__main__":
    main()
