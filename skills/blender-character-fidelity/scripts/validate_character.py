#!/usr/bin/env python3
"""Validate the small character-spec v1 contract. No third-party dependencies."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

CATEGORIES = ("face", "body", "hair", "outfit", "accessories")
FULL = {"front", "side", "back"}
FACE = {"face_front", "face_side", "face_three_quarter"}
THREE_QUARTER = {"front_three_quarter", "back_three_quarter"}


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def number(value, low=None, high=None):
    return (type(value) in (int, float) and math.isfinite(value)
            and (low is None or value >= low) and (high is None or value <= high))


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def read_json(path):
    def bad_constant(value):
        raise ContractError(f"Nonfinite JSON number: {value}")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=bad_constant,
                      object_pairs_hook=unique_object)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def local_path(root, raw):
    require(nonempty(raw) and "\\" not in raw, "Use nonempty portable relative paths")
    path = Path(raw)
    require(not path.is_absolute() and ".." not in path.parts and ":" not in raw,
            f"Unsafe project path: {raw}")
    resolved = (Path(root) / path).resolve()
    require(resolved.is_relative_to(Path(root).resolve()), f"Path escapes project: {raw}")
    return resolved


def hash_file(root, path, expected):
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected),
            f"Missing/invalid SHA-256: {path}")
    resolved = local_path(root, path)
    require(resolved.is_file(), f"Missing evidence: {path}")
    require(digest(resolved) == expected, f"Stale evidence hash: {path}")
    return resolved


def unique_rows(rows, label):
    require(isinstance(rows, list) and rows, f"{label} must be a nonempty array")
    ids = [r["id"] for r in rows]
    require(all(isinstance(i, str) and re.fullmatch(r"[a-z0-9_-]+", i) for i in ids),
            f"{label}: invalid ID")
    require(len(ids) == len(set(ids)), f"{label}: duplicate ID")
    return {r["id"]: r for r in rows}


def validate(spec, root, ready=False):
    require(type(spec["schema_version"]) is int and spec["schema_version"] == 1, "Unsupported spec schema")
    require(nonempty(spec["character_id"]) and nonempty(spec["style"]), "Missing identity/style")
    require(spec["status"] in ("draft", "locked"), "Invalid spec status")
    require(spec["coordinates"] == {"unit": "m", "up": "+Z", "front": "-Y", "image_origin": "top-left"},
            "Coordinate convention differs from v1")
    if ready:
        require(spec["status"] == "locked", "Spec is draft; final evidence is blocked")
        require("REPLACE" not in spec["style"], "Replace illustrative style")
    sources = unique_rows(spec["sources"], "sources")
    for row in sources.values():
        require(row["kind"] in ("original", "generated"), "Invalid source provenance")
        require(nonempty(row["view"]) and nonempty(row["notes"]), "Missing source provenance notes")
        local_path(root, row["path"])
        if ready:
            require("REPLACE" not in row["notes"], "Replace source provenance notes")
            hash_file(root, row["path"], row["sha256"])
    require(any(s["kind"] == "original" for s in sources.values()), "No original source")
    locks = unique_rows(spec["locks"], "locks")
    require({r["category"] for r in locks.values()} == set(CATEGORIES), "Locks must cover all five categories")
    for row in locks.values():
        require(nonempty(row["description"]) and type(row["critical"]) is bool, "Invalid identity lock")
        require(row["certainty"] in ("observed", "inferred", "unknown"), "Invalid certainty")
        require(isinstance(row["source_ids"], list) and row["source_ids"]
                and set(row["source_ids"]) <= sources.keys(), "Missing lock source")
        if row["certainty"] == "observed":
            require(any(sources[i]["kind"] == "original" for i in row["source_ids"]),
                    "Observed lock must cite an original")
        if ready:
            require("REPLACE" not in row["description"], "Replace illustrative locks")
            require(not (row["critical"] and row["certainty"] == "unknown"), "Critical unknown lock")
            if row["certainty"] == "inferred":
                require(nonempty(row.get("decision")), "Inferred lock needs a recorded decision")
    proportions = spec["proportions"]
    require((number(proportions["working_height_m"], 0.01) or (not ready and proportions["working_height_m"] is None))
            and (number(proportions["head_units"], 1) or (not ready and proportions["head_units"] is None))
            and nonempty(proportions["notes"]),
            "Invalid working proportions")
    if ready:
        require("ILLUSTRATIVE" not in proportions["notes"], "Replace illustrative proportions")
    review = spec["review"]
    require(nonempty(review["scene"]) and nonempty(review["collection"]), "Missing scene/collection")
    require(type(review["frame"]) is int, "Frame must be integer")
    require(isinstance(review["resolution"], list) and len(review["resolution"]) == 2
            and all(type(n) is int and 16 <= n <= 8192 for n in review["resolution"]), "Invalid resolution")
    require(type(review["samples"]) is int and 1 <= review["samples"] <= 4096, "Invalid samples")
    require(type(review["seed"]) is int and review["seed"] >= 0, "Invalid seed")
    require(review["view_transform"] in ("Standard", "AgX"), "Unsupported view transform")
    views = unique_rows(review["views"], "views")
    require(FULL | FACE <= views.keys(), "Missing required body or face view")
    require(not (THREE_QUARTER & views.keys()) or THREE_QUARTER <= views.keys(), "Add both three-quarter views")
    require(len({v["camera"] for v in views.values()}) == len(views), "Each view needs its own camera")
    for key, view in views.items():
        require(nonempty(view["camera"]) and view["projection"] in ("ORTHO", "PERSP"), "Invalid camera")
        require(view["role"] in ("full", "face", "source"), "Invalid view role")
        if key in FULL | THREE_QUARTER:
            require(view["projection"] == "ORTHO" and view["role"] == "full", "Canonical views must be full orthographic")
        if key in FACE:
            require(view["role"] == "face", "Face view must have face role")
    landmarks = review["landmarks"]
    require(isinstance(landmarks, dict) and landmarks and all(nonempty(v) for v in landmarks.values()), "Missing landmarks")
    measurements = {} if not ready and spec["measurements"] == [] else unique_rows(spec["measurements"], "measurements")
    if ready:
        require(any(m["category"] == "face" and m["kind"] == "landmarks" for m in measurements.values()), "Need face landmark evidence")
        require(any(m["category"] == "body" and m["kind"] == "ratio" for m in measurements.values()), "Need body ratio evidence")
    for m in measurements.values():
        require(m["category"] in CATEGORIES and m["view"] in views, "Unknown measurement category/view")
        require(m["source_id"] in sources and sources[m["source_id"]]["kind"] == "original", "Measurements require originals")
        require(number(m["tolerance"], 1e-9, 1) and nonempty(m["notes"]), "Invalid tolerance/notes")
        if ready:
            require("ILLUSTRATIVE" not in m["notes"] and "REPLACE" not in m["notes"], "Replace illustrative metric targets")
        require(m["kind"] in ("landmarks", "ratio", "silhouette"), "Unsupported metric")
        if m["kind"] == "landmarks":
            require(isinstance(m["targets"], dict) and len(m["targets"]) >= 3
                    and m["targets"].keys() <= landmarks.keys(), "Invalid landmark targets")
            require(number(m["normalizer"], 1e-9, 1), "Invalid face normalizer")
            require(all(isinstance(p, list) and len(p) == 2 and all(number(v, 0, 1) for v in p)
                        for p in m["targets"].values()), "Invalid UV target")
        elif m["kind"] == "ratio":
            require(isinstance(m["points"], list) and len(m["points"]) == 4
                    and set(m["points"]) <= landmarks.keys(), "Invalid ratio points")
            require(number(m["target"], 1e-9), "Invalid ratio target")
        else:
            require(m["category"] == "body", "MVP IoU is whole-body only")
            local_path(root, m["mask_path"])
            if ready:
                hash_file(root, m["mask_path"], m["mask_sha256"])
    quality = spec["quality"]
    weights = quality["weights"]
    require(set(weights) == set(CATEGORIES) and all(number(v, 1e-9, 1) for v in weights.values())
            and abs(sum(weights.values()) - 1) < 1e-9, "Weights must cover five categories and sum to 1")
    require(number(quality["category_floor"], 1, 100)
            and number(quality["overall_floor"], quality["category_floor"], 100), "Invalid score floors")
    for field in ("max_iterations", "plateau_rounds"):
        require(type(quality[field]) is int and quality[field] >= 1, f"Invalid {field}")
    require(number(quality["plateau_delta"], 0.001, 100), "Invalid plateau delta")
    return spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--ready", action="store_true", help="Require locked spec and current source files")
    args = parser.parse_args()
    try:
        validate(read_json(args.spec), args.spec.resolve().parent, args.ready)
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    print("READY" if args.ready else "VALID DRAFT/STRUCTURE (not a fidelity pass)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
