#!/usr/bin/env python3
"""Synthetic contract/gate regression tests; these do NOT test likeness or Blender."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

from score_identity import load_manifest, measure, score, validate_review
from validate_character import CATEGORIES, ContractError, digest, read_json, validate

HERE = Path(__file__).resolve().parent


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def png(path, width=32, height=32):
    def chunk(name, body):
        return struct.pack(">I", len(body)) + name + body + struct.pack(">I", zlib.crc32(name + body))
    path.parent.mkdir(parents=True, exist_ok=True)
    row = b"\x00" + bytes([127, 127, 127, 255]) * width
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b""))


def fixture(root):
    spec = read_json(HERE.parent / "assets/character-spec.example.json")
    spec["status"] = "locked"
    spec["style"] = "Synthetic fixture only; no character or likeness evidence"
    spec["review"]["resolution"] = [32, 32]
    spec["proportions"]["notes"] = "Synthetic fixture uses arbitrary working units"
    spec["sources"][0]["notes"] = "Synthetic original for gate mechanics only"
    source = root / spec["sources"][0]["path"]
    png(source)
    spec["sources"][0]["sha256"] = digest(source)
    for lock in spec["locks"]:
        lock["description"] = "Synthetic " + lock["category"] + " contract; no actual identity claim"
    for m in spec["measurements"]:
        m["notes"] = "Synthetic mathematical correspondence only"
    spec["measurements"][1]["target"] = 1.2
    model = root / "model/checkpoint-001.blend"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"SYNTHETIC FIXTURE - NOT A BLENDER FILE")
    write_json(root / "character-spec.json", spec)
    manifest = {"schema_version": 1, "character_id": spec["character_id"], "spec_sha256": digest(root / "character-spec.json"),
                "blend": {"path": model.relative_to(root).as_posix(), "sha256": digest(model)}, "iteration": 1,
                "stage": "final", "blender_version": "synthetic-test", "created_utc": "2026-01-01T00:00:00Z",
                "settings": copy.deepcopy(spec["review"]), "geometry": {"mesh_count": 1, "triangles": 12}, "views": {}}
    points = {k: [v[0], v[1], 1] for k, v in spec["measurements"][0]["targets"].items()}
    points.update({"sole": [.5, .99, 1], "shoulder_left": [.3, .5, 1], "shoulder_right": [.7, .5, 1]})
    for view in spec["review"]["views"]:
        row = {"camera": {"name": view["camera"], "projection": "ORTHO", "matrix_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]},
               "landmarks": copy.deepcopy(points), "images": {}}
        for mode in ("clay", "material"):
            image = root / f"reviews/iteration-001/{view['id']}-{mode}.png"
            png(image)
            row["images"][mode] = {"path": image.relative_to(root).as_posix(), "sha256": digest(image)}
        manifest["views"][view["id"]] = row
    manifest_path = root / "reviews/iteration-001/manifest.json"
    write_json(manifest_path, manifest)
    person = {"reviewer": "builder-fixture", "inspected_views": list(manifest["views"]),
              "categories": {c: {"score": 95, "reason": "Synthetic score for gate testing", "evidence": list(manifest["views"])} for c in CATEGORIES},
              "locks": {x["id"]: {"pass": True, "reason": "Synthetic attestation only"} for x in spec["locks"]}, "hard_failures": []}
    review = {"schema_version": 1, "manifest_sha256": digest(manifest_path), "builder": person, "fresh_eyes": copy.deepcopy(person)}
    review["fresh_eyes"].update({"reviewer": "reviewer-fixture", "mode": "independent"})
    write_json(root / "reviews/iteration-001/review.json", review)
    return spec, manifest, review


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.spec, self.manifest, self.review = fixture(self.root)
        self.manifest_path = self.root / "reviews/iteration-001/manifest.json"

    def result(self, previous=None):
        return score(self.spec, self.manifest, measure(self.spec, self.manifest, self.root), self.review, previous)

    def history_round(self, iteration, previous=None, filename="score.json"):
        """Build a real CLI score chain, including each round's immutable bindings."""
        self.manifest["iteration"] = iteration
        folder = self.root / f"reviews/iteration-{iteration:03d}"
        capture = folder / "manifest.json"
        write_json(capture, self.manifest)
        self.review["manifest_sha256"] = digest(capture)
        review_path = folder / "review.json"
        write_json(review_path, self.review)
        output = folder / filename
        command = [sys.executable, str(HERE / "score_identity.py"), "--spec", str(self.root / "character-spec.json"),
                   "--manifest", str(capture), "--review", str(review_path), "--out", str(output)]
        if previous:
            command += ["--previous", str(previous)]
        return subprocess.run(command, capture_output=True, text=True), output

    def test_cli_pass_and_measured_only(self):
        common = [sys.executable, str(HERE / "score_identity.py"), "--spec", str(self.root / "character-spec.json"),
                  "--manifest", str(self.manifest_path)]
        args = common + ["--review", str(self.root / "reviews/iteration-001/review.json"), "--out", str(self.root / "score.json")]
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_json(self.root / "score.json")["status"], "pass")
        result = subprocess.run(common + ["--measure-only", "--out", str(self.root / "metrics.json")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(read_json(self.root / "metrics.json")["identity_verified"])
        self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)  # immutable output

    def test_draft_and_example_block_ready(self):
        example = read_json(HERE.parent / "assets/character-spec.example.json")
        validate(example, self.root)
        with self.assertRaises(ContractError):
            validate(example, self.root, ready=True)

    def test_reference_limited_draft_keeps_unknowns(self):
        self.spec["status"] = "draft"
        self.spec["proportions"].update({"head_units": None, "working_height_m": None})
        self.spec["measurements"] = []
        self.spec["locks"][1]["certainty"] = "unknown"
        validate(self.spec, self.root)
        self.spec["status"] = "locked"
        with self.assertRaisesRegex(ContractError, "Critical unknown"):
            validate(self.spec, self.root, ready=True)

    def test_cli_failure_and_history_camera_guard(self):
        review_path = self.root / "reviews/iteration-001/review.json"
        self.review["builder"]["categories"]["face"]["score"] = 70
        write_json(review_path, self.review)
        command = [sys.executable, str(HERE / "score_identity.py"), "--spec", str(self.root / "character-spec.json"),
                   "--manifest", str(self.manifest_path), "--review", str(review_path), "--out", str(self.root / "score-001.json")]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        self.manifest["iteration"] = 2
        new_manifest = self.root / "reviews/iteration-002/manifest.json"
        write_json(new_manifest, self.manifest)
        self.review["manifest_sha256"] = digest(new_manifest)
        new_review = new_manifest.with_name("review.json")
        write_json(new_review, self.review)
        command = [sys.executable, str(HERE / "score_identity.py"), "--spec", str(self.root / "character-spec.json"),
                   "--manifest", str(new_manifest), "--review", str(new_review), "--out", str(self.root / "score-002.json")]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)  # previous mandatory
        command += ["--previous", str(self.root / "score-001.json")]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        self.manifest["views"]["front"]["camera"]["matrix_world"][0][3] = 1
        write_json(new_manifest, self.manifest)
        self.review["manifest_sha256"] = digest(new_manifest)
        write_json(new_review, self.review)
        command[command.index("--out") + 1] = str(self.root / "score-camera-change.json")
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Camera changed", result.stderr)

    def test_cli_rejects_tampered_history_values(self):
        self.review["builder"]["categories"]["face"]["score"] = 70
        first, first_path = self.history_round(1)
        self.assertEqual(first.returncode, 1, first.stderr)
        second, second_path = self.history_round(2, first_path)
        self.assertEqual(second.returncode, 1, second.stderr)
        original = read_json(second_path)
        self.assertEqual(original["plateau_count"], 1)
        third, third_path = self.history_round(3, second_path)
        self.assertEqual(third.returncode, 1, third.stderr)
        self.assertEqual(read_json(third_path)["stop_reason"], "plateau")
        # The actual reviews, renders and manifests stay unchanged. Neither a
        # fabricated improvement nor a reset counter may reopen the same series.
        for field in ("overall", "plateau_count"):
            with self.subTest(field=field):
                altered = copy.deepcopy(original)
                altered[field] = 0
                altered_path = second_path.with_name(f"score-altered-{field}.json")
                write_json(altered_path, altered)
                result, output = self.history_round(3, altered_path, f"score-from-altered-{field}.json")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse(output.exists(), "Invalid history must not produce a new score")

    def test_cli_rejects_cyclic_history_link(self):
        self.review["builder"]["categories"]["face"]["score"] = 70
        first, first_path = self.history_round(1)
        self.assertEqual(first.returncode, 1, first.stderr)
        second, second_path = self.history_round(2, first_path)
        self.assertEqual(second.returncode, 1, second.stderr)
        altered = read_json(second_path)
        cycle_path = second_path.with_name("score-cyclic.json")
        altered["previous_file"] = {"path": cycle_path.relative_to(self.root).as_posix(), "sha256": digest(second_path)}
        write_json(cycle_path, altered)
        result, output = self.history_round(3, cycle_path, "score-from-cycle.json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(output.exists())

    def test_cli_rejects_skipped_history_round(self):
        # Keep the series open long enough to isolate continuity from stop limits.
        self.spec["quality"].update({"max_iterations": 6, "plateau_rounds": 5})
        write_json(self.root / "character-spec.json", self.spec)
        self.manifest["spec_sha256"] = digest(self.root / "character-spec.json")
        self.review["builder"]["categories"]["face"]["score"] = 70
        first, first_path = self.history_round(1)
        self.assertEqual(first.returncode, 1, first.stderr)
        second, second_path = self.history_round(2, first_path)
        self.assertEqual(second.returncode, 1, second.stderr)
        third, third_path = self.history_round(3, second_path)
        self.assertEqual(third.returncode, 1, third.stderr)
        altered = read_json(third_path)
        altered["previous_file"] = {"path": first_path.relative_to(self.root).as_posix(), "sha256": digest(first_path)}
        altered_path = third_path.with_name("score-skipped-round.json")
        write_json(altered_path, altered)
        result, output = self.history_round(4, altered_path, "score-from-skipped-round.json")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(output.exists())

    def test_missing_view_and_stale_model(self):
        del self.manifest["views"]["face_side"]
        write_json(self.manifest_path, self.manifest)
        with self.assertRaisesRegex(ContractError, "capture set"):
            load_manifest(self.spec, self.manifest["spec_sha256"], self.root, self.manifest_path)
        (self.root / self.manifest["blend"]["path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ContractError, "Stale"):
            load_manifest(self.spec, self.manifest["spec_sha256"], self.root, self.manifest_path)

    def test_stale_render(self):
        image = self.manifest["views"]["front"]["images"]["clay"]["path"]
        (self.root / image).write_bytes(b"changed")
        with self.assertRaisesRegex(ContractError, "Stale"):
            load_manifest(self.spec, self.manifest["spec_sha256"], self.root, self.manifest_path)

    def test_low_face_not_hidden_by_total(self):
        for who in ("builder", "fresh_eyes"):
            for row in self.review[who]["categories"].values():
                row["score"] = 100
        self.review["fresh_eyes"]["categories"]["face"]["score"] = 84
        result = self.result()
        self.assertGreater(result["overall"], 90)
        self.assertEqual(result["status"], "needs_revision")
        self.assertEqual(result["scores"]["face"], 84)

    def test_metric_failure_even_when_reviews_high(self):
        self.manifest["views"]["front"]["landmarks"]["chin"] = [.5, .3, 1]
        self.assertEqual(self.result()["status"], "needs_revision")
        self.manifest["views"]["face_front"]["landmarks"]["chin"] = [.5, .85, -1]
        with self.assertRaises(ContractError):
            self.result()

    def test_critical_accessory_and_stage_block(self):
        self.review["fresh_eyes"]["locks"]["accessories-identity"]["pass"] = False
        result = self.result()
        self.assertEqual(result["failures"][0]["priority"], 1)
        self.assertEqual(result["status"], "needs_revision")
        self.manifest["stage"] = "blockout"
        self.assertEqual(self.result()["failures"][0]["priority"], 0)

    def test_review_coverage_and_self_review(self):
        self.review["fresh_eyes"]["inspected_views"].pop()
        with self.assertRaises(ContractError):
            validate_review(self.review, self.spec, self.manifest, digest(self.manifest_path))
        self.review["fresh_eyes"]["inspected_views"] = list(self.manifest["views"])
        self.review["fresh_eyes"]["reviewer"] = self.review["builder"]["reviewer"]
        with self.assertRaises(ContractError):
            validate_review(self.review, self.spec, self.manifest, digest(self.manifest_path))
        self.review["fresh_eyes"]["mode"] = "adversarial_self"
        with self.assertRaises(ContractError):
            validate_review(self.review, self.spec, self.manifest, digest(self.manifest_path))
        for row in self.review["fresh_eyes"]["categories"].values():
            row["case_against"] = "Synthetic strongest objection"
        validate_review(self.review, self.spec, self.manifest, digest(self.manifest_path))

    def test_nonfinite_generated_source_and_traversal(self):
        self.spec["measurements"][0]["normalizer"] = float("nan")
        with self.assertRaises(ContractError):
            validate(self.spec, self.root)
        self.spec["measurements"][0]["normalizer"] = .7
        self.spec["sources"][0]["kind"] = "generated"
        with self.assertRaises(ContractError):
            validate(self.spec, self.root)
        self.spec["sources"][0]["kind"] = "original"
        self.spec["sources"][0]["path"] = "../outside.png"
        with self.assertRaises(ContractError):
            validate(self.spec, self.root)

    def test_plateau_and_budget_are_not_passes(self):
        self.review["builder"]["categories"]["face"]["score"] = 70
        prev = self.result()
        self.manifest["iteration"] = 2
        nxt = self.result(prev)
        self.assertEqual(nxt["plateau_count"], 1)
        self.manifest["iteration"] = 3
        nxt = self.result(nxt)
        self.assertEqual(nxt["stop_reason"], "plateau")
        self.manifest["iteration"] = 4
        self.assertEqual(self.result(nxt)["stop_reason"], "budget")

    def test_ratio_uses_frame_aspect(self):
        self.spec["review"]["resolution"] = [64, 32]
        m = self.spec["measurements"][1]
        m["points"] = ["jaw_left", "jaw_right", "head_top", "chin"]
        m["target"] = .8 / .7
        self.assertTrue(measure(self.spec, self.manifest, self.root)[1]["pass"])

    def test_optional_iou(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is optional; IoU path not available")
        mask = self.root / "references/mask.png"
        Image.new("L", (32, 32), 255).save(mask)
        self.spec["measurements"].append({"id": "body-mask", "category": "body", "kind": "silhouette",
            "view": "front", "source_id": "original-front", "tolerance": .1, "notes": "Synthetic mask",
            "mask_path": "references/mask.png", "mask_sha256": digest(mask)})
        self.assertEqual(measure(self.spec, self.manifest, self.root)[-1]["value"], 1)
        Image.new("L", (32, 32), 0).save(mask)
        self.spec["measurements"][-1]["mask_sha256"] = digest(mask)
        with self.assertRaisesRegex(ContractError, "Empty"):
            measure(self.spec, self.manifest, self.root)


if __name__ == "__main__":
    unittest.main()
