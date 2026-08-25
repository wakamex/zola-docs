#!/usr/bin/env python3

import argparse
import json
import shutil
import statistics
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any

from convert_mdbook_site import convert as convert_mdbook
from generate_version_tombstones import discover_routes


class CorpusError(ValueError):
    pass


def load_manifest(path: Path) -> dict[str, Any]:
    document = tomllib.loads(path.read_text())
    required = {"schema", "id", "repository", "revision", "adapter", "generators"}
    missing = required - set(document)
    if missing:
        raise CorpusError(f"manifest lacks: {', '.join(sorted(missing))}")
    if document["schema"] != 1:
        raise CorpusError("unsupported corpus manifest schema")
    if document["adapter"] not in {"mdbook"}:
        raise CorpusError(f"unsupported corpus adapter: {document['adapter']}")
    expected_native_only = document.get("expected_native_only_routes", [])
    if not isinstance(expected_native_only, list) or not all(
        isinstance(route, str) and route.startswith("/") for route in expected_native_only
    ):
        raise CorpusError("expected_native_only_routes must be an array of root-relative routes")
    generators = document["generators"]
    if not isinstance(generators, list) or len(generators) < 2:
        raise CorpusError("manifest requires at least two [[generators]]")
    identifiers: set[str] = set()
    for generator in generators:
        if not isinstance(generator, dict):
            raise CorpusError("generators must be tables")
        identifier = generator.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise CorpusError("generator ids must be unique non-empty strings")
        identifiers.add(identifier)
        if not isinstance(generator.get("cwd"), str):
            raise CorpusError(f"generator {identifier} requires cwd")
        command = generator.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
            raise CorpusError(f"generator {identifier} requires a string command array")
        if not isinstance(generator.get("output"), str):
            raise CorpusError(f"generator {identifier} requires output")
        version_command = generator.get("version_command")
        expected_version = generator.get("expected_version")
        if not isinstance(version_command, list) or not version_command or not all(
            isinstance(part, str) for part in version_command
        ):
            raise CorpusError(f"generator {identifier} requires a string version_command array")
        if not isinstance(expected_version, str) or not expected_version:
            raise CorpusError(f"generator {identifier} requires expected_version")
    return document


def verify_revision(document: dict[str, Any], source: Path) -> None:
    expected = document["revision"]
    if not isinstance(expected, str) or not expected:
        raise CorpusError("manifest revision must be a non-empty string")
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    actual = result.stdout.strip()
    if actual != expected:
        raise CorpusError(f"source revision is {actual}, expected {expected}")


def expand(value: str, variables: dict[str, str]) -> str:
    try:
        return value.format_map(variables)
    except KeyError as error:
        raise CorpusError(f"unknown manifest placeholder: {error.args[0]}") from error


def safe_output(path: Path, work: Path) -> Path:
    resolved = path.resolve()
    if resolved == work or not resolved.is_relative_to(work):
        raise CorpusError(f"generator output must be below the corpus work directory: {resolved}")
    return resolved


def clear_output(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def output_bytes(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def normalized_routes(directory: Path) -> set[str]:
    normalized: set[str] = set()
    for route in discover_routes(directory):
        if route.endswith(".html"):
            normalized.add(route.removesuffix(".html") + "/")
        else:
            normalized.add(route)
    return normalized


def measured_run(command: list[str], cwd: Path, measurement: Path) -> tuple[float, int]:
    started = time.perf_counter()
    result = subprocess.run(
        ["/usr/bin/time", "-f", "%e\t%M", "-o", str(measurement), *command],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - started
    if result.returncode:
        raise CorpusError(
            f"command failed in {cwd}: {' '.join(command)}\n{result.stdout}{result.stderr}"
        )
    fields = measurement.read_text().strip().split("\t")
    if len(fields) != 2:
        raise CorpusError("GNU time returned an unexpected measurement")
    return elapsed, int(fields[1])


def prepare(document: dict[str, Any], source: Path, work: Path, theme: Path, mdbook: str) -> dict[str, Any]:
    verify_revision(document, source)
    converted = work / "converted"
    if converted.exists():
        raise CorpusError(f"converted site already exists: {converted}")
    work.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if document["adapter"] == "mdbook":
        details = convert_mdbook(source, converted, theme, mdbook)
    else:
        raise CorpusError(f"unsupported corpus adapter: {document['adapter']}")
    return {
        "adapter": document["adapter"],
        "seconds": round(time.perf_counter() - started, 6),
        **details,
    }


def fetch(document: dict[str, Any], destination: Path) -> dict[str, str]:
    if destination.exists():
        raise CorpusError(f"source destination already exists: {destination}")
    repository = document["repository"]
    if not isinstance(repository, str) or not repository:
        raise CorpusError("manifest repository must be a non-empty string")
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--filter=blob:none", repository, str(destination)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(destination), "checkout", "--detach", document["revision"]],
        check=True,
    )
    verify_revision(document, destination)
    return {"repository": repository, "revision": document["revision"], "destination": str(destination)}


def benchmark(
    document: dict[str, Any],
    source: Path,
    work: Path,
    zola: Path,
    mdbook: str,
    runs: int,
    warmups: int,
) -> dict[str, Any]:
    verify_revision(document, source)
    converted = work / "converted"
    if not converted.is_dir():
        raise CorpusError(f"prepare the converted site first: {converted}")
    variables = {
        "source": str(source.resolve()),
        "work": str(work),
        "converted": str(converted),
        "zola": str(zola.resolve()),
        "mdbook": mdbook,
    }
    results: list[dict[str, Any]] = []
    for generator in document["generators"]:
        identifier = generator["id"]
        cwd = Path(expand(generator["cwd"], variables)).resolve()
        output = safe_output(Path(expand(generator["output"], variables)), work)
        variables["output"] = str(output)
        command = [expand(part, variables) for part in generator["command"]]
        version_command = [expand(part, variables) for part in generator["version_command"]]
        version_result = subprocess.run(version_command, capture_output=True, text=True, check=True)
        version = (version_result.stdout or version_result.stderr).strip()
        if version != generator["expected_version"]:
            raise CorpusError(
                f"generator {identifier} version is {version!r}, expected {generator['expected_version']!r}"
            )
        measurements: list[float] = []
        memory: list[int] = []
        measurement = work / f".{identifier}.time"
        for index in range(warmups + runs):
            clear_output(output)
            elapsed, maximum_rss = measured_run(command, cwd, measurement)
            if index >= warmups:
                measurements.append(elapsed)
                memory.append(maximum_rss)
        routes = normalized_routes(output)
        results.append(
            {
                "id": identifier,
                "version": version,
                "runs_seconds": [round(value, 6) for value in measurements],
                "median_seconds": round(statistics.median(measurements), 6),
                "min_seconds": round(min(measurements), 6),
                "max_seconds": round(max(measurements), 6),
                "max_rss_kib": max(memory),
                "files": sum(1 for path in output.rglob("*") if path.is_file()),
                "html_files": sum(1 for path in output.rglob("*.html") if path.is_file()),
                "bytes": output_bytes(output),
                "routes": len(routes),
                "route_set": routes,
            }
        )
    baseline = results[0]["route_set"]
    expected_native_only = set(document.get("expected_native_only_routes", []))
    for result in results:
        routes = result.pop("route_set")
        missing = baseline - routes
        result["routes_shared_with_first"] = len(routes & baseline)
        result["routes_only_in_this_generator"] = sorted(routes - baseline)
        result["expected_routes_missing_from_first"] = sorted(missing & expected_native_only)
        result["unexpected_routes_missing_from_first"] = sorted(missing - expected_native_only)
    return {
        "site": document["id"],
        "revision": document["revision"],
        "runs": runs,
        "warmups": warmups,
        "generators": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and benchmark reproducible documentation corpora")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    fetch_command = subparsers.add_parser("fetch")
    fetch_command.add_argument("manifest", type=Path)
    fetch_command.add_argument("--destination", type=Path, required=True)
    for operation in ("prepare", "benchmark"):
        command = subparsers.add_parser(operation)
        command.add_argument("manifest", type=Path)
        command.add_argument("--source", type=Path, required=True)
        command.add_argument("--work", type=Path, required=True)
        command.add_argument("--mdbook", default="mdbook")
        if operation == "prepare":
            command.add_argument("--theme", type=Path, default=Path(__file__).resolve().parents[1])
        else:
            command.add_argument("--zola", type=Path, required=True)
            command.add_argument("--runs", type=int, default=5)
            command.add_argument("--warmups", type=int, default=1)
            command.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        document = load_manifest(args.manifest)
        if args.operation == "fetch":
            result = fetch(document, args.destination.resolve())
            print(json.dumps(result, indent=2, sort_keys=True))
            return
        source = args.source.resolve()
        work = args.work.resolve()
        if args.operation == "prepare":
            result = prepare(document, source, work, args.theme.resolve(), args.mdbook)
        else:
            if args.runs < 1 or args.warmups < 0:
                raise CorpusError("runs must be positive and warmups cannot be negative")
            result = benchmark(
                document, source, work, args.zola, args.mdbook, args.runs, args.warmups
            )
            if args.output:
                args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, subprocess.CalledProcessError, CorpusError, tomllib.TOMLDecodeError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
