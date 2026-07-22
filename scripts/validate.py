#!/usr/bin/env python3
"""Validate generated Clash and Quantumult X rule files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "generated"
CLASH_RE = re.compile(r"^  - (DOMAIN|DOMAIN-SUFFIX|DOMAIN-KEYWORD|DOMAIN-REGEX),.+$")
QX_RE = re.compile(r"^(HOST|HOST-SUFFIX|HOST-KEYWORD|HOST-WILDCARD),[^,]+,.+$")


def main() -> int:
    manifest = json.loads((GENERATED / "manifest.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    ids = [entry["id"] for entry in manifest["entries"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate IDs in manifest")
    for entry in manifest["entries"]:
        clash_path = GENERATED / "clash" / f"{entry['id']}.yaml"
        qx_path = GENERATED / "quantumultx" / f"{entry['id']}.list"
        if not clash_path.is_file() or not qx_path.is_file():
            errors.append(f"missing output for {entry['id']}")
            continue
        clash_rules = [line for line in clash_path.read_text(encoding="utf-8").splitlines() if line.startswith("  - ")]
        qx_rules = [
            line for line in qx_path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        if len(clash_rules) != entry["rule_count"]:
            errors.append(f"rule count mismatch: {entry['id']}")
        if any(not CLASH_RE.match(line) for line in clash_rules):
            errors.append(f"invalid Clash syntax: {entry['id']}")
        if any(not QX_RE.match(line) for line in qx_rules):
            errors.append(f"invalid Quantumult X syntax: {entry['id']}")
        expected_qx = entry["rule_count"] - entry["quantumultx_unsupported_regex"]
        if len(qx_rules) != expected_qx:
            errors.append(f"Quantumult X rule count mismatch: {entry['id']}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"validated {manifest['vendor_count']} vendors, "
        f"{manifest['aggregate_count']} aggregates and {sum(e['rule_count'] for e in manifest['entries'])} rules"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
