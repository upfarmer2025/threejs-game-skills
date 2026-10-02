#!/usr/bin/env python3
"""Measure geometric proxies and reconcile explicit reviews; never infer identity scores."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct
import sys

from validate_character import (CATEGORIES, FACE, FULL, digest, hash_file, nonempty,
                                number, read_json, require, validate)


def project_relative(root, path):
    resolved = Path(path).resolve()
    require(resolved.is_relative_to(root), "Evidence/output must be inside the character project")
    return resolved.relative_to(root).as_posix()


def png_size(path):
    with path.open("rb") as stream:
        header = stream.read(26)
    require(len(header) == 26 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR",
            f"Not a PNG: {path}")
    require(header[25] == 6, f"Review PNG must be RGBA: {path}")
    return list(struct.unpack(">II", header[16:24]))


def load_manifest(spec, spec_hash, root, path):
    manifest = read_json(path)
    require(manifest["schema_version"] == 1, "Unsupported manifest version")
    require(manifest["spec_sha256"] == spec_hash and manifest["character_id"] == spec["character_id"], "Stale/wrong manifest spec")
    require(manifest["settings"] == spec["review"], "Capture settings differ from spec")
    require(type(manifest["iteration"]) is int and manifest["iteration"] >= 1, "Invalid iteration")
    require(manifest["stage"] in ("blockout", "identity", "camera", "lookdev", "final"), "Invalid stage")
    require(nonempty(manifest["blender_version"]) and nonempty(manifest["created_utc"]), "Missing capture provenance")
    require(number(manifest["geometry"]["triangles"], 1) and number(manifest["geometry"]["mesh_count"], 1), "Empty geometry")
    hash_file(root, manifest["blend"]["path"], manifest["blend"]["sha256"])
    expected = {v["id"]: v for v in spec["review"]["views"]}
    require(set(manifest["views"]) == set(expected), "Incomplete or unexpected capture set")
    seen_paths = set()
    for key, row in manifest["views"].items():
        camera = row["camera"]
        require(camera["name"] == expected[key]["camera"] and camera["projection"] == expected[key]["projection"],
                f"Wrong camera: {key}")
        require(len(camera["matrix_world"]) == 4 and all(len(r) == 4 and all(number(x) for x in r)
                    for r in camera["matrix_world"]), "Invalid camera matrix")
        require(set(row["images"]) == {"clay", "material"}, f"Missing clay/material pass: {key}")
        for image in row["images"].values():
            file = hash_file(root, image["path"], image["sha256"])
            require(file not in seen_paths, "Captures reuse the same artifact path")
            seen_paths.add(file)
            require(png_size(file) == spec["review"]["resolution"], "Image resolution mismatch")
    return manifest


def measure(spec, manifest, root):
    aspect = spec["review"]["resolution"][0] / spec["review"]["resolution"][1]
    def distance(a, b):
        return math.hypot((a[0] - b[0]) * aspect, a[1] - b[1])

    results = []
    for m in spec["measurements"]:
        row = manifest["views"][m["view"]]
        def point(name):
            p = row["landmarks"][name]
            require(isinstance(p, list) and len(p) == 3 and all(number(x) for x in p)
                    and 0 <= p[0] <= 1 and 0 <= p[1] <= 1 and p[2] > 0,
                    f"Missing/off-frame/behind-camera landmark: {m['id']}/{name}")
            return p
        if m["kind"] == "landmarks":
            value = sum(distance(point(key), target) for key, target in m["targets"].items()) / len(m["targets"]) / m["normalizer"]
            error = value
        elif m["kind"] == "ratio":
            a, b, c, d = [point(i) for i in m["points"]]
            denominator = distance(c, d)
            require(denominator > 1e-9, f"Degenerate ratio: {m['id']}")
            value = distance(a, b) / denominator
            error = abs(value - m["target"]) / m["target"]
        else:
            try:
                from PIL import Image
            except ImportError as exc:
                raise ValueError("Silhouette checks need Pillow; install it in the scoring environment") from exc
            ref = hash_file(root, m["mask_path"], m["mask_sha256"])
            rendered = hash_file(root, row["images"]["clay"]["path"], row["images"]["clay"]["sha256"])
            with Image.open(ref) as original, Image.open(rendered) as capture:
                require(list(original.size) == spec["review"]["resolution"] and original.size == capture.size,
                        "Mask dimensions differ; do not resize silently")
                a = [v >= 128 for v in original.convert("L").tobytes()]
                b = [v >= 128 for v in capture.convert("RGBA").getchannel("A").tobytes()]
            require(any(a) and any(b), "Empty reference or render silhouette")
            value = sum(x and y for x, y in zip(a, b)) / sum(x or y for x, y in zip(a, b))
            error = 1 - value
        results.append({"id": m["id"], "category": m["category"], "view": m["view"],
                        "kind": m["kind"], "value": value, "error": error,
                        "tolerance": m["tolerance"], "pass": error <= m["tolerance"]})
    return results


def validate_review(review, spec, manifest, manifest_hash):
    require(review["schema_version"] == 1 and review["manifest_sha256"] == manifest_hash, "Stale/wrong review manifest")
    views = set(manifest["views"])
    locks = {r["id"] for r in spec["locks"]}
    mode = review["fresh_eyes"]["mode"]
    require(mode in ("independent", "adversarial_self"), "Invalid review mode")
    for who in ("builder", "fresh_eyes"):
        person = review[who]
        require(nonempty(person["reviewer"]), "Missing reviewer identity")
        require(isinstance(person["inspected_views"], list) and set(person["inspected_views"]) == views
                and len(person["inspected_views"]) == len(views), "Reviewer did not attest to complete capture set")
        require(set(person["categories"]) == set(CATEGORIES), "Reviewer omitted a category")
        for category, row in person["categories"].items():
            require(number(row["score"], 0, 100) and nonempty(row["reason"]), "Unscored/unexplained category")
            require(isinstance(row["evidence"], list) and row["evidence"] and set(row["evidence"]) <= views, "Invalid score evidence")
            if category == "face":
                require(FACE <= set(row["evidence"]), "Face score needs all three face views")
            if category in ("body", "outfit"):
                require(FULL <= set(row["evidence"]), "Body/outfit score needs front/side/back")
            if who == "fresh_eyes" and mode == "adversarial_self":
                require(nonempty(row.get("case_against")), "Self-review needs a case against each score")
        require(set(person["locks"]) == locks, "Reviewer omitted identity locks")
        require(all(type(r["pass"]) is bool and nonempty(r["reason"]) for r in person["locks"].values()), "Incomplete lock review")
        require(isinstance(person["hard_failures"], list) and all(nonempty(x) for x in person["hard_failures"]), "Invalid hard failures")
    if mode == "independent":
        require(review["builder"]["reviewer"].strip().casefold() != review["fresh_eyes"]["reviewer"].strip().casefold(),
                "Builder cannot be its own independent reviewer")


def score(spec, manifest, metrics, review, previous=None):
    quality = spec["quality"]
    scores = {c: min(review["builder"]["categories"][c]["score"], review["fresh_eyes"]["categories"][c]["score"])
              for c in CATEGORIES}
    overall = sum(scores[c] * quality["weights"][c] for c in CATEGORIES)
    failures = []
    def fail(priority, category, reason, action):
        failures.append({"priority": priority, "category": category, "reason": reason, "next_pass": action})
    if manifest["stage"] != "final":
        fail(0, "evidence", "Intermediate modeling stage", "Complete stage gates, save final checkpoint and recapture")
    for who in ("builder", "fresh_eyes"):
        for reason in review[who]["hard_failures"]:
            fail(1, "identity", f"{who}: {reason}", "Resolve this observed blocker and review every affected angle")
    for lock in spec["locks"]:
        for who in ("builder", "fresh_eyes"):
            item = review[who]["locks"][lock["id"]]
            if not item["pass"]:
                fail(1 if lock["critical"] else 2, lock["category"], f"{lock['id']} ({who}): {item['reason']}",
                     f"Restore locked trait: {lock['description']}; recheck both reviews")
    for m in metrics:
        if not m["pass"]:
            fail(1 if m["category"] in ("face", "body") else 2, m["category"],
                 f"{m['id']}: error {m['error']:.5f} > {m['tolerance']:.5f}",
                 f"Check camera/pose correspondence first; correct {m['category']} geometry in {m['view']} until error <= {m['tolerance']}")
    for category, value in scores.items():
        if value < quality["category_floor"]:
            reasons = " / ".join(review[p]["categories"][category]["reason"] for p in ("builder", "fresh_eyes"))
            fail(1 if category in ("face", "body") else 2, category, f"Score {value} below floor; {reasons}",
                 f"Correct documented {category} discrepancies; reach {quality['category_floor']} in both reviews")
    if overall < quality["overall_floor"]:
        weakest = min(scores, key=scores.get)
        fail(2, weakest, f"Weighted total {overall:.2f} below {quality['overall_floor']}",
             f"Improve {weakest} after all identity blockers; preserve already passing traits")
    plateau = 0
    regressions = []
    if previous:
        require(previous["spec_sha256"] == manifest["spec_sha256"]
                and previous["character_id"] == manifest["character_id"], "Previous score uses another spec/character")
        require(previous["iteration"] == manifest["iteration"] - 1, "History must use contiguous iterations")
        require(number(previous["overall"], 0, 100) and type(previous["plateau_count"]) is int
                and previous["plateau_count"] >= 0, "Malformed previous score")
        plateau = previous["plateau_count"] + 1 if overall - previous["overall"] < quality["plateau_delta"] else 0
        regressions = [c for c in CATEGORIES if scores[c] < previous["scores"][c]]
    budget = manifest["iteration"] >= quality["max_iterations"]
    if manifest["iteration"] > quality["max_iterations"]:
        fail(0, "budget", "Iteration exceeds locked budget", "Record a revised budget in a new spec/series before continuing")
    failures.sort(key=lambda x: (x["priority"], CATEGORIES.index(x["category"]) if x["category"] in CATEGORIES else -1))
    status = "pass" if not failures else "needs_revision"
    return {"schema_version": 1, "character_id": spec["character_id"], "spec_sha256": manifest["spec_sha256"],
            "iteration": manifest["iteration"], "status": status, "scores": scores, "overall": overall,
            "metrics": metrics, "reviews": review, "failures": failures,
            "next_pass": failures[:3], "regressed_categories": regressions, "plateau_count": plateau,
            "stop_reason": ("budget" if budget else "plateau") if failures and (budget or plateau >= quality["plateau_rounds"]) else None,
            "limitations": ["Geometric proxies plus reviewer attestations; not automatic recognition",
                            "Independent review unavailable" if review["fresh_eyes"]["mode"] == "adversarial_self" else "Perceptual judgments remain subjective"]}


def same_capture_conditions(previous, current):
    require(all(previous["views"][v]["camera"] == current["views"][v]["camera"] for v in current["views"]),
            "Camera changed within a series; document recalibration and start a new baseline")
    require(previous.get("lighting") == current.get("lighting"), "Lighting changed within a series; start a new baseline")


def verified_history(spec, spec_hash, root, path, seen=None):
    """Recompute prior results from their bound evidence before using stop counters."""
    path = Path(path).resolve()
    project_relative(root, path)
    seen = set() if seen is None else seen
    require(path not in seen, "Cyclic previous score history")
    seen.add(path)
    require(len(seen) <= spec["quality"]["max_iterations"], "Previous history exceeds iteration budget")
    previous = read_json(path)
    require(type(previous["schema_version"]) is int and previous["schema_version"] == 1
            and previous["status"] in ("pass", "needs_revision"), "Invalid previous score")
    manifest_path = hash_file(root, previous["manifest"]["path"], previous["manifest"]["sha256"])
    capture = load_manifest(spec, spec_hash, root, manifest_path)
    require(previous["iteration"] == capture["iteration"], "Previous score/capture iteration mismatch")
    review_path = hash_file(root, previous["review_file"]["path"], previous["review_file"]["sha256"])
    review = read_json(review_path)
    validate_review(review, spec, capture, digest(manifest_path))
    ancestor = previous.get("previous_file")
    if capture["iteration"] == 1:
        require(ancestor is None, "First round cannot have previous score")
        derived_parent = None
    else:
        require(isinstance(ancestor, dict), "Previous score history is incomplete")
        ancestor_path = hash_file(root, ancestor["path"], ancestor["sha256"])
        derived_parent, parent_capture = verified_history(spec, spec_hash, root, ancestor_path, seen)
        require(not derived_parent["stop_reason"], "Previous series stopped; revise the contract and start a new series")
        same_capture_conditions(parent_capture, capture)
    derived = score(spec, capture, measure(spec, capture, root), review, derived_parent)
    for field, value in derived.items():
        require(previous.get(field) == value, f"Previous score differs from bound evidence: {field}")
    return derived, capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--measure-only", action="store_true", help="Produce metrics before blind review; never accepts a character")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        root = args.spec.resolve().parent
        spec = validate(read_json(args.spec), root, ready=True)
        spec_hash = digest(args.spec)
        manifest = load_manifest(spec, spec_hash, root, args.manifest)
        binding = {"path": project_relative(root, args.manifest), "sha256": digest(args.manifest)}
        metrics = measure(spec, manifest, root)
        if args.measure_only:
            result = {"schema_version": 1, "status": "measured_only", "spec_sha256": spec_hash,
                      "manifest": binding, "metrics": metrics, "identity_verified": False}
            code = 0
        else:
            require(args.review is not None, "--review required for final gate")
            review = read_json(args.review)
            validate_review(review, spec, manifest, binding["sha256"])
            require(manifest["iteration"] == 1 or args.previous is not None, "--previous required after round 1")
            require(manifest["iteration"] != 1 or args.previous is None, "First round cannot have previous score")
            previous = None
            if args.previous:
                previous, old_capture = verified_history(spec, spec_hash, root, args.previous)
                require(not previous["stop_reason"], "Previous series stopped; revise the contract and start a new series")
                same_capture_conditions(old_capture, manifest)
            result = score(spec, manifest, metrics, review, previous)
            result["manifest"] = binding
            result["review_file"] = {"path": project_relative(root, args.review), "sha256": digest(args.review)}
            result["previous_file"] = ({"path": project_relative(root, args.previous), "sha256": digest(args.previous)} if args.previous else None)
            code = 0 if result["status"] == "pass" else 1
        project_relative(root, args.out)
        require(not args.out.exists(), "Output exists; keep immutable evidence and choose a new filename")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(f"{result['status']}: {args.out}")
        return code
    except (ValueError, OSError, KeyError, TypeError, AttributeError, IndexError) as exc:
        print(f"INVALID EVIDENCE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
