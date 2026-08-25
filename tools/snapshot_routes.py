#!/usr/bin/env python3

import argparse
import ast
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from generate_version_tombstones import discover_routes


SCRIPT_SOURCE = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
SEARCH_INDEX = re.compile(r'["\']([^"\']*searchindex[^"\']*\.js)["\']')


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "zola-docs-route-benchmark/1"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode()


def snapshot_sitemap(source: str, root_url: str) -> set[str]:
    parsed_source = urlsplit(source)
    if parsed_source.scheme in {"http", "https"}:
        document = fetch_text(source)
    else:
        document = Path(source).read_text()
    root = urlsplit(root_url.rstrip("/") + "/")
    if root.scheme not in {"http", "https"} or not root.netloc:
        raise ValueError("sitemap root must be an absolute HTTP(S) URL")
    routes: set[str] = set()
    try:
        tree = ET.fromstring(document)
    except ET.ParseError as error:
        raise ValueError(f"invalid sitemap XML: {error}") from error
    for location in tree.findall(".//{*}url/{*}loc"):
        if not location.text:
            continue
        target = urlsplit(location.text.strip())
        if target.scheme != root.scheme or target.netloc != root.netloc:
            continue
        if not target.path.startswith(root.path):
            continue
        relative = target.path[len(root.path) :]
        routes.add("/" + relative if relative else "/")
    if not routes:
        raise ValueError("sitemap does not contain routes below the supplied root")
    return routes


def parse_mdbook_search_index(source: str) -> set[str]:
    prefix = "JSON.parse('"
    start = source.find(prefix)
    if start != -1:
        start += len(prefix)
        end = source.rfind("')")
        if end <= start:
            raise ValueError("mdBook search index has an incomplete JSON.parse wrapper")
        decoded = ast.literal_eval("'" + source[start:end] + "'")
    else:
        prefix = "Object.assign(window.search, "
        start = source.find(prefix)
        end = source.rfind(");")
        if start == -1 or end <= start:
            raise ValueError("mdBook search index has an unknown wrapper")
        decoded = source[start + len(prefix) : end]
    document = json.loads(decoded)
    urls = document.get("doc_urls")
    if not isinstance(urls, list):
        raise ValueError("mdBook search index does not contain doc_urls")
    routes = {"/"}
    for value in urls:
        if not isinstance(value, str):
            raise ValueError("mdBook doc_urls entries must be strings")
        path = value.split("#", 1)[0].split("?", 1)[0].lstrip("/")
        if path:
            routes.add("/" + path)
    return routes


def snapshot_mdbook(root_url: str) -> set[str]:
    root = root_url.rstrip("/") + "/"
    index = fetch_text(root)
    scripts = SCRIPT_SOURCE.findall(index)
    searcher = next((source for source in scripts if "searcher" in source), None)
    if searcher is None:
        raise ValueError("mdBook page does not reference a searcher script")
    searcher_source = fetch_text(urljoin(root, searcher))
    match = SEARCH_INDEX.search(searcher_source)
    if match is None:
        raise ValueError("mdBook searcher does not reference a search index script")
    search_index = fetch_text(urljoin(root, match.group(1)))
    return parse_mdbook_search_index(search_index)


def write_routes(routes: set[str], output: Path) -> None:
    output.write_text("".join(f"{route}\n" for route in sorted(routes)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot canonical routes from a documentation build")
    subparsers = parser.add_subparsers(dest="format", required=True)
    directory = subparsers.add_parser("directory")
    directory.add_argument("source", type=Path)
    directory.add_argument("--output", "-o", type=Path, required=True)
    mdbook = subparsers.add_parser("mdbook")
    mdbook.add_argument("source")
    mdbook.add_argument("--output", "-o", type=Path, required=True)
    sitemap = subparsers.add_parser("sitemap")
    sitemap.add_argument("source")
    sitemap.add_argument("--root", required=True)
    sitemap.add_argument("--output", "-o", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.format == "directory":
            routes = discover_routes(args.source)
        elif args.format == "mdbook":
            routes = snapshot_mdbook(args.source)
        else:
            routes = snapshot_sitemap(args.source, args.root)
        if not routes:
            raise ValueError("source did not contain any routes")
        write_routes(routes, args.output)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print(f"wrote {len(routes)} routes to {args.output}")


if __name__ == "__main__":
    main()
