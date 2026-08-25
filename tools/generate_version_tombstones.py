#!/usr/bin/env python3

import argparse
import html
import json
import re
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


START = "<!-- zola-docs-not-found-start -->"
END = "<!-- zola-docs-not-found-end -->"
STATE_MARKER = '<meta name="zola-docs-route-state" content="unavailable">'
VERSION_ID = re.compile(r"^[A-Za-z0-9._-]+$")


class TombstoneError(ValueError):
    pass


@dataclass(frozen=True)
class Version:
    id: str
    label: str
    url: str
    directory: Path
    release_order: int | None


def load_versions(path: Path) -> list[Version]:
    try:
        document = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise TombstoneError(str(error)) from error
    entries = document.get("versions") if isinstance(document, dict) else None
    if not isinstance(entries, list) or len(entries) < 2:
        raise TombstoneError("configuration requires at least two [[versions]] entries")

    versions: list[Version] = []
    ids: set[str] = set()
    release_orders: set[int] = set()
    for index, entry in enumerate(entries):
        location = f"versions[{index}]"
        if not isinstance(entry, dict):
            raise TombstoneError(f"{location} must be a table")
        unknown = set(entry) - {"id", "label", "url", "directory", "release_order"}
        if unknown:
            raise TombstoneError(f"{location} contains unknown keys: {', '.join(sorted(unknown))}")
        identifier = entry.get("id")
        label = entry.get("label")
        url = entry.get("url")
        directory = entry.get("directory")
        release_order = entry.get("release_order")
        if not isinstance(identifier, str) or not VERSION_ID.fullmatch(identifier):
            raise TombstoneError(f"{location}.id must contain only letters, digits, '.', '_', or '-'")
        if identifier in ids:
            raise TombstoneError(f"{location}.id duplicates {identifier!r}")
        ids.add(identifier)
        if not isinstance(label, str) or not label.strip():
            raise TombstoneError(f"{location}.label must be a non-empty string")
        if not isinstance(url, str) or not url:
            raise TombstoneError(f"{location}.url must be a non-empty string")
        parsed_url = urlsplit(url)
        if not (url.startswith("/") or parsed_url.scheme in {"http", "https"}):
            raise TombstoneError(f"{location}.url must be root-relative or use HTTP(S)")
        if not isinstance(directory, str) or not directory:
            raise TombstoneError(f"{location}.directory must be a non-empty string")
        public = (path.parent / directory).resolve()
        if not public.is_dir() or not (public / "404.html").is_file():
            raise TombstoneError(f"{location}.directory must contain a rendered 404.html")
        if release_order is not None:
            if not isinstance(release_order, int) or isinstance(release_order, bool):
                raise TombstoneError(f"{location}.release_order must be an integer")
            if release_order in release_orders:
                raise TombstoneError(f"{location}.release_order duplicates {release_order}")
            release_orders.add(release_order)
        versions.append(Version(identifier, label, url, public, release_order))
    return versions


def route_for_file(relative: Path) -> str:
    parts = PurePosixPath(relative.as_posix())
    if parts.name == "index.html":
        parent = parts.parent.as_posix()
        return "/" if parent == "." else f"/{parent.strip('/')}/"
    return f"/{parts.as_posix()}"


def file_for_route(route: str) -> Path:
    relative = route.removeprefix("/")
    if not relative:
        return Path("index.html")
    if route.endswith("/"):
        return Path(relative) / "index.html"
    return Path(relative)


def is_tombstone(path: Path) -> bool:
    with path.open("rb") as source:
        return STATE_MARKER.encode() in source.read(16_384)


def discover_routes(directory: Path) -> set[str]:
    routes: set[str] = set()
    for page in directory.rglob("*.html"):
        relative = page.relative_to(directory)
        if relative == Path("404.html") or is_tombstone(page):
            continue
        routes.add(route_for_file(relative))
    return routes


def join_url(root: str, route: str) -> str:
    return root.rstrip("/") + route


def nearest_ancestor(route: str, available: set[str]) -> str | None:
    relative = route.strip("/")
    parts = relative.split("/") if relative else []
    if parts and "." in parts[-1]:
        parts.pop()
    elif parts:
        parts.pop()
    while parts:
        candidate = "/" + "/".join(parts) + "/"
        if candidate in available:
            return candidate
        parts.pop()
    return "/" if "/" in available else None


def render_body(
    route: str,
    current: Version,
    available_versions: list[Version],
    current_routes: set[str],
) -> str:
    escaped_route = html.escape(route)
    lines = [
        START,
        f'<div data-version-tombstone data-route="{escaped_route}" data-version="{html.escape(current.id)}">',
        f"  <h1>Page unavailable in {html.escape(current.label)}</h1>",
        f"  <p><code>{escaped_route}</code> is not part of this documentation version.</p>",
    ]
    releases = sorted(
        (version for version in available_versions if version.release_order is not None),
        key=lambda version: version.release_order,
    )
    if releases:
        lines.append(
            "  <p>This documentation page first appears in "
            f"{html.escape(releases[0].label)}.</p>"
        )
    lines.extend(["  <p>Open this page in:</p>", "  <ul>"])
    for version in available_versions:
        lines.append(
            f'    <li><a href="{html.escape(join_url(version.url, route), quote=True)}">'
            f"{html.escape(version.label)}</a></li>"
        )
    lines.append("  </ul>")
    ancestor = nearest_ancestor(route, current_routes)
    if ancestor is not None:
        lines.append(
            "  <p>Or continue with the nearest available page in this version: "
            f'<a href="{html.escape(join_url(current.url, ancestor), quote=True)}">'
            f"{html.escape(ancestor)}</a>.</p>"
        )
    lines.extend(["</div>", END])
    return "\n".join(lines)


def render_tombstone(
    shell: str,
    route: str,
    current: Version,
    available_versions: list[Version],
    current_routes: set[str],
) -> str:
    if START not in shell or END not in shell or shell.index(START) >= shell.index(END):
        raise TombstoneError(f"{current.directory / '404.html'} lacks Zola Docs tombstone markers")
    before, remainder = shell.split(START, 1)
    _, after = remainder.split(END, 1)
    rendered = before + render_body(route, current, available_versions, current_routes) + after
    if "</head>" not in rendered:
        raise TombstoneError(f"{current.directory / '404.html'} lacks </head>")
    metadata = (
        f"  {STATE_MARKER}\n"
        '  <meta name="robots" content="noindex,follow">\n'
        f'  <meta name="zola-docs-route" content="{html.escape(route, quote=True)}">\n'
    )
    return rendered.replace("</head>", metadata + "</head>", 1)


def generate(versions: list[Version], output: Path) -> dict[str, object]:
    if output.exists():
        raise TombstoneError(f"output already exists: {output}")
    started = time.perf_counter()
    routes = {version.id: discover_routes(version.directory) for version in versions}
    all_routes = set().union(*routes.values())
    generated = 0
    generated_bytes = 0
    by_version: dict[str, int] = {}
    for current in versions:
        shell = (current.directory / "404.html").read_text()
        count = 0
        for route in sorted(all_routes - routes[current.id]):
            available = [version for version in versions if route in routes[version.id]]
            destination = output / current.id / file_for_route(route)
            destination.parent.mkdir(parents=True, exist_ok=True)
            content = render_tombstone(shell, route, current, available, routes[current.id])
            destination.write_text(content)
            count += 1
            generated += 1
            generated_bytes += len(content.encode())
        by_version[current.id] = count
    return {
        "versions": len(versions),
        "unique_routes": len(all_routes),
        "tombstones": generated,
        "bytes": generated_bytes,
        "seconds": round(time.perf_counter() - started, 6),
        "by_version": by_version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate marked cross-version documentation tombstone overlays"
    )
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = generate(load_versions(args.config), args.output)
    except (OSError, TombstoneError) as error:
        raise SystemExit(str(error)) from error
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"generated {result['tombstones']} tombstones across {result['versions']} versions "
            f"({result['bytes']} bytes in {result['seconds']}s)"
        )


if __name__ == "__main__":
    main()
