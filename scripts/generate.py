#!/usr/bin/env python3
"""Generate Clash/Mihomo and Quantumult X AI vendor rules from v2fly data."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "sources" / "vendors.json"
TYPE_ORDER = {"full": 0, "suffix": 1, "keyword": 2, "regexp": 3}


@dataclass(frozen=True, order=True)
class Rule:
    kind: str
    value: str


class SourceLoader:
    def __init__(self, raw_base: str, source_root: Path | None):
        self.raw_base = raw_base.rstrip("/")
        self.source_root = source_root
        self.cache: dict[str, str] = {}

    def read(self, name: str) -> str:
        if name in self.cache:
            return self.cache[name]
        if self.source_root:
            path = self.source_root / name
            if not path.is_file():
                raise FileNotFoundError(f"missing upstream source: {path}")
            text = path.read_text(encoding="utf-8")
        else:
            url = f"{self.raw_base}/{name}"
            request = urllib.request.Request(url, headers={"User-Agent": "ai-vendor-rules/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    text = response.read().decode("utf-8")
            except urllib.error.URLError as exc:
                raise RuntimeError(f"failed to fetch {url}: {exc}") from exc
        self.cache[name] = text
        return text


def parse_entry(token: str) -> Rule:
    for prefix, kind in (("full:", "full"), ("keyword:", "keyword"), ("regexp:", "regexp")):
        if token.startswith(prefix):
            value = token[len(prefix):].strip()
            if not value:
                raise ValueError(f"empty {prefix} entry")
            return Rule(kind, value)
    return Rule("suffix", token.strip())


def resolve_source(loader: SourceLoader, name: str, stack: tuple[str, ...] = ()) -> set[Rule]:
    if name in stack:
        raise ValueError(f"include cycle: {' -> '.join(stack + (name,))}")
    rules: set[Rule] = set()
    for raw_line in loader.read(name).splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        token, attributes = parts[0], set(parts[1:])
        if "@ads" in attributes:
            continue
        if token.startswith("include:"):
            rules.update(resolve_source(loader, token.split(":", 1)[1], stack + (name,)))
        else:
            rules.add(parse_entry(token))
    return rules


def sorted_rules(rules: set[Rule]) -> list[Rule]:
    return sorted(rules, key=lambda rule: (TYPE_ORDER[rule.kind], rule.value.lower(), rule.value))


def clash_line(rule: Rule) -> str:
    prefix = {
        "full": "DOMAIN",
        "suffix": "DOMAIN-SUFFIX",
        "keyword": "DOMAIN-KEYWORD",
        "regexp": "DOMAIN-REGEX",
    }[rule.kind]
    return f"{prefix},{rule.value}"


def regex_to_quantumultx_wildcard(pattern: str) -> str | None:
    """Convert simple anchored domain regexes into Quantumult X wildcards."""
    value = pattern.removeprefix("^").removesuffix("$")
    value = value.replace(r"\S+", "*").replace(r"\d+", "*").replace(r"\.", ".")
    if re.search(r"[\\^$+(){}|\[\]]", value):
        return None
    return value


def quantumultx_line(rule: Rule, policy: str) -> str:
    prefix = {"full": "HOST", "suffix": "HOST-SUFFIX", "keyword": "HOST-KEYWORD"}.get(rule.kind)
    if rule.kind == "regexp":
        wildcard = regex_to_quantumultx_wildcard(rule.value)
        if wildcard is None:
            return f"# UNSUPPORTED-REGEXP,{rule.value},{policy}"
        return f"HOST-WILDCARD,{wildcard},{policy}"
    return f"{prefix},{rule.value},{policy}"


def upstream_revision(source_root: Path | None, ref: str) -> str:
    if source_root:
        try:
            repo = source_root.parent
            return subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return ref


def render_entry(entry: dict, loader: SourceLoader, revision: str) -> tuple[str, str, dict]:
    rules: set[Rule] = set()
    for source in entry.get("sources", []):
        rules.update(resolve_source(loader, source))
    rules.update(parse_entry(value) for value in entry.get("domains", []))
    ordered = sorted_rules(rules)
    if not ordered:
        raise ValueError(f"{entry['id']} generated no rules")

    header = [
        "# AUTO-GENERATED. DO NOT EDIT.",
        f"# Name: {entry['name']}",
        f"# Upstream: v2fly/domain-list-community@{revision}",
        f"# Sources: {', '.join(entry.get('sources', [])) or 'catalog inline domains'}",
    ]
    clash = "\n".join(header + ["payload:"] + [f"  - {clash_line(rule)}" for rule in ordered]) + "\n"
    qx = "\n".join(
        header
        + [f"# Policy: {entry['policy']}"]
        + [quantumultx_line(rule, entry["policy"]) for rule in ordered]
    ) + "\n"
    unsupported = sum(
        rule.kind == "regexp" and regex_to_quantumultx_wildcard(rule.value) is None for rule in ordered
    )
    metadata = {
        "id": entry["id"],
        "name": entry["name"],
        "policy": entry["policy"],
        "rule_count": len(ordered),
        "quantumultx_unsupported_regex": unsupported,
        "sources": entry.get("sources", []),
    }
    return clash, qx, metadata


def write_outputs(destination: Path, catalog: dict, loader: SourceLoader, revision: str) -> None:
    clash_dir = destination / "clash"
    qx_dir = destination / "quantumultx"
    clash_dir.mkdir(parents=True, exist_ok=True)
    qx_dir.mkdir(parents=True, exist_ok=True)
    manifest_entries = []
    for entry in catalog["vendors"] + catalog["aggregates"]:
        clash, qx, metadata = render_entry(entry, loader, revision)
        (clash_dir / f"{entry['id']}.yaml").write_text(clash, encoding="utf-8")
        (qx_dir / f"{entry['id']}.list").write_text(qx, encoding="utf-8")
        manifest_entries.append(metadata)
    manifest = {
        "schema": 1,
        "upstream": catalog["upstream"]["repository"],
        "upstream_revision": revision,
        "vendor_count": len(catalog["vendors"]),
        "aggregate_count": len(catalog["aggregates"]),
        "entries": manifest_entries,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def compare_trees(expected: Path, actual: Path) -> list[str]:
    expected_files = {path.relative_to(expected) for path in expected.rglob("*") if path.is_file()}
    actual_files = {path.relative_to(actual) for path in actual.rglob("*") if path.is_file()}
    differences = [f"missing generated file: {path}" for path in sorted(expected_files - actual_files)]
    differences += [f"unexpected generated file: {path}" for path in sorted(actual_files - expected_files)]
    for path in sorted(expected_files & actual_files):
        if (expected / path).read_bytes() != (actual / path).read_bytes():
            differences.append(f"stale generated file: {path}")
    return differences


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, help="Path to domain-list-community/data")
    parser.add_argument("--output", type=Path, default=ROOT / "generated")
    parser.add_argument("--check", action="store_true", help="Fail if committed output is stale")
    args = parser.parse_args()

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    loader = SourceLoader(catalog["upstream"]["raw_base"], args.source_root)
    revision = upstream_revision(args.source_root, catalog["upstream"]["ref"])
    if args.check:
        with tempfile.TemporaryDirectory(prefix="ai-vendor-rules-") as directory:
            expected = Path(directory) / "generated"
            write_outputs(expected, catalog, loader, revision)
            differences = compare_trees(expected, args.output)
            if differences:
                print("\n".join(differences), file=sys.stderr)
                return 1
    else:
        write_outputs(args.output, catalog, loader, revision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
