#!/usr/bin/env python3
"""Render common trajectory prefix trees from the curated sequence CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_IN = Path("data/processed/trajectory_sequences.csv")
DEFAULT_OUT = Path("reports/agent_trajectories/figures/common_trees")
DEFAULT_TREE_OUT = Path("reports/agent_trajectories/trees/common_trees")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    return text.strip("_") or "empty"


def success(outcome: str) -> bool:
    return outcome == "func_and_sec_pass"


def sequence_tokens(row: dict[str, str]) -> list[str]:
    sequence = row.get("detailed_behavior_sequence") or row.get("raw_sequence", "")
    tokens = [token for token in sequence.split(" > ") if token]
    collapsed: list[str] = []
    for token in tokens:
        if not collapsed or collapsed[-1] != token:
            collapsed.append(token)
    return collapsed


def build_tree(rows: list[dict[str, str]], max_depth: int) -> dict[str, Any]:
    root: dict[str, Any] = {"count": 0, "success": 0, "children": {}}
    for row in rows:
        tokens = sequence_tokens(row)
        node = root
        node["count"] += 1
        if success(row.get("outcome", "")):
            node["success"] += 1
        for token in tokens[:max_depth]:
            node = node["children"].setdefault(token, {"count": 0, "success": 0, "children": {}})
            node["count"] += 1
            if success(row.get("outcome", "")):
                node["success"] += 1
    return root


def prune_tree(node: dict[str, Any], min_count: int, max_children: int) -> dict[str, Any]:
    kept = sorted(node.get("children", {}).items(), key=lambda kv: kv[1]["count"], reverse=True)
    children = {
        label: prune_tree(child, min_count, max_children)
        for label, child in kept[:max_children]
        if child["count"] >= min_count
    }
    return {"count": node["count"], "success": node.get("success", 0), "children": children}


def dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def tree_to_dot(tree: dict[str, Any], title: str) -> str:
    lines = [
        "digraph trajectory {",
        "  graph [rankdir=LR, bgcolor=\"white\", pad=0.25, nodesep=0.45, ranksep=0.65];",
        "  node [shape=box, style=\"rounded,filled\", fontname=\"Helvetica\", fontsize=10, color=\"#46515f\", fillcolor=\"#f8fafc\"];",
        "  edge [fontname=\"Helvetica\", fontsize=9, color=\"#64748b\", arrowsize=0.7];",
        f'  label="{dot_escape(title)}";',
        "  labelloc=t;",
        "  fontsize=18;",
        "  fontname=\"Helvetica-Bold\";",
    ]
    counter = 0

    def add_node(label: str, node: dict[str, Any]) -> str:
        nonlocal counter
        node_id = f"n{counter}"
        counter += 1
        count = int(node["count"])
        succ = int(node.get("success", 0))
        rate = succ / count if count else 0
        fill = "#dcfce7" if rate >= 0.7 else "#fef9c3" if rate >= 0.35 else "#fee2e2" if succ else "#f8fafc"
        node_label = f"{label}\\ncount={count}, success={succ}"
        lines.append(f'  {node_id} [label="{dot_escape(node_label)}", fillcolor="{fill}"];')
        return node_id

    def walk(parent_id: str, node: dict[str, Any]) -> None:
        for token, child in node.get("children", {}).items():
            child_id = add_node(token, child)
            lines.append(f'  {parent_id} -> {child_id} [label="{child["count"]}"];')
            walk(child_id, child)

    root_id = add_node("START", tree)
    walk(root_id, tree)
    lines.append("}")
    return "\n".join(lines) + "\n"


def grouped_rows(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        agent = row.get("agent", "")
        benchmark = row.get("benchmark", "")
        language = row.get("language", "")
        if agent and benchmark:
            groups[("benchmark_agent", f"{benchmark}::{agent}")].append(row)
        if agent and language:
            groups[("agent_language", f"{agent}::{language}")].append(row)
    return groups


def render_tree(dot_path: Path, png_path: Path) -> None:
    subprocess.run(["dot", "-Tpng", str(dot_path), "-o", str(png_path)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--tree-dir", type=Path, default=DEFAULT_TREE_OUT)
    parser.add_argument("--min-runs", type=int, default=20)
    parser.add_argument("--max-depth", type=int, default=9)
    parser.add_argument("--max-children", type=int, default=6)
    args = parser.parse_args()

    rows = read_rows(args.input)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.tree_dir.mkdir(parents=True, exist_ok=True)
    dot_dir = args.out_dir / "dot"
    png_dir = args.out_dir / "png"
    dot_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    rendered = 0
    manifest: list[dict[str, Any]] = []
    for (group_type, value), group_rows in sorted(grouped_rows(rows).items()):
        if len(group_rows) < args.min_runs:
            continue
        min_count = max(2, len(group_rows) // 50)
        tree = prune_tree(build_tree(group_rows, args.max_depth), min_count=min_count, max_children=args.max_children)
        stem = f"{group_type}__{safe_name(value)}"
        title = f"{group_type.replace('_', ' ')}: {value}"
        tree_path = args.tree_dir / f"{stem}.json"
        dot_path = dot_dir / f"{stem}.dot"
        png_path = png_dir / f"{stem}.png"
        tree_path.write_text(json.dumps(tree, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        dot_path.write_text(tree_to_dot(tree, title), encoding="utf-8")
        render_tree(dot_path, png_path)
        rendered += 1
        manifest.append(
            {
                "group_type": group_type,
                "group_value": value,
                "run_count": len(group_rows),
                "min_count": min_count,
                "max_depth": args.max_depth,
                "png": str(png_path),
                "dot": str(dot_path),
                "tree_json": str(tree_path),
            }
        )

    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {rendered} common trajectory tree PNGs into {png_dir}")


if __name__ == "__main__":
    main()
