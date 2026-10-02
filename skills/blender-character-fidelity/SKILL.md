---
name: blender-character-fidelity
description: "Build or repair reference-faithful Blender characters from images. Use for character likeness, face shape, body proportions, hair silhouette, outfit and signature accessories, character-spec JSON, three/five-view turnarounds, staged modeling, camera matching, neutral and beauty renders, identity scoring, and prioritized correction loops. Use for standalone Blender assets or before Three.js integration; this is not a generic image-to-3D provider or automatic face-recognition service."
---

# Blender Character Fidelity

Preserve the supplied character before adding polish. Treat generated geometry as a
draft, not proof of likeness. Do not beautify the face, lengthen legs, enlarge eyes,
replace stylized anatomy, or simplify identity-bearing accessories without a requested
design change. Resolve this directory from the loaded SKILL.md. Run tools in the user's
character project; never write models into the skill package.

## Start and required references

1. Read project AGENTS.md and inspect all supplied images at full and face-crop scale.
2. Read [character-contract.md](references/character-contract.md) before writing the spec.
3. Read [modeling-playbook.md](references/modeling-playbook.md) before geometry or cameras.
4. Read [identity-scorecard.md](references/identity-scorecard.md) before any scoring.
5. Record whether Blender CLI / bpy, image viewing, rendering, and independent review
   are available. Record the actual Blender version. Target Blender 4.2+; verify the
   local version with a smoke render. Missing Blender permits preparation, not a claim
   that a model was built or visually verified.
6. Copy [assets/AGENTS.md](assets/AGENTS.md) into the character project, or merge its
   applicable instructions into an existing AGENTS.md. Never overwrite unrelated rules.
7. Copy [character-spec.example.json](assets/character-spec.example.json), replace its
   illustrative values from the references, and validate it. The draft must not pass
   the final gate. Do not manufacture source hashes or measurement targets.

## Pipeline and phase exits

Save a new `.blend` checkpoint and a new review directory at every geometry gate.
Record `stage / input hashes / changes / evidence / failures / next action` in
`reviews/stages.md`. A phase is done only with the evidence below.

| Stage | Work | Exit evidence |
| --- | --- | --- |
| 0 — reference lock | Extract observed traits; label inferred/unknown areas; write character-spec JSON. | Original hashes, five identity categories, source links per lock, approved inference decisions. |
| 1 — turnaround | Prepare front/true side/back; add front and rear 3/4 for five views. | Shared height/landmark guides, same pose/outfit/person, provenance, contradictions listed. |
| 2 — blockout | Establish head/body ratio, shoulders/hips, torso/legs, head and hair masses. | Neutral silhouettes, ratio errors, front/side/back comparison. No detail while proportions fail. |
| 3 — identity geometry | Refine facial planes/profile, hair clumps, garment construction and accessories. | Face front/side/3/4 crops, full-body view set, lock-by-lock review. |
| 4 — camera match | Fit source projection, distance, tilt/roll, crop, lens/ortho scale and pose. | Fixed camera parameters, same pixel crop, source overlay, lens uncertainty recorded. |
| 5 — lookdev | Match color blocks, roughness, fabric, metal and hair under neutral light, then beauty lighting. | Neutral clay/material captures and separate beauty review; source style retained. |
| 6 — evidence loop | Render every view, measure supported traits, run fresh-eyes review, correct failures. | Hash-bound manifest, measured metrics, both score sets, lower reconciled scores, next pass. |
| 7 — delivery | Pack dependencies; reopen the saved file; rerender/rescore after the last edit. | Final `.blend`, source/spec, all captures, score JSON, remaining uncertainty, optional game export. |

Calibrate cameras during blockout as well as stage 4: perspective mismatch must not
be sculpted into the face. Keep canonical orthographic and source-matched camera sets
separate. Generated unseen views are hypotheses, not new observations.

Use a consistent T/A pose for modeling. Preserve the source pose in a separate review
state if needed; never compare poses as interchangeable silhouettes. Do not mirror
asymmetric bangs, clips, earrings, sleeves or garment openings.

## Minimal executable workflow

Set `<skill-dir>` to this package and `<project>` to the folder containing the spec.
Python 3.10+ runs the validator and gate; optional silhouette IoU needs Pillow.
Blender runs the renderer with its bundled Python. JSON paths are relative to the
spec directory. Keep originals and review artifacts inside that project.

```bash
python3 <skill-dir>/scripts/validate_character.py <project>/character-spec.json
# After replacing draft values, reviewing hypotheses, and locking the spec:
python3 <skill-dir>/scripts/validate_character.py <project>/character-spec.json --ready

# Author REVIEW scene, CHARACTER collection, cameras and attached landmarks;
# save and pack the source .blend first. See character-contract.md.
blender --background <project>/model/character.blend --python-exit-code 2 \
  --python <skill-dir>/scripts/render_review.py -- \
  --spec <project>/character-spec.json --out reviews/iteration-001 --iteration 1

# Produce proxy evidence for blind review, without builder scores.
python3 <skill-dir>/scripts/score_identity.py \
  --spec <project>/character-spec.json \
  --manifest <project>/reviews/iteration-001/manifest.json \
  --measure-only --out <project>/reviews/iteration-001/metrics.json

# Fill both reviews from the complete captures, not from this command.
python3 <skill-dir>/scripts/score_identity.py \
  --spec <project>/character-spec.json \
  --manifest <project>/reviews/iteration-001/manifest.json \
  --review <project>/reviews/iteration-001/review.json \
  --out <project>/reviews/iteration-001/score.json
```

On Windows use `python` and a quoted absolute Blender executable path; in PowerShell
prefix that executable with `&`. Commands above are argv examples, not a dependency
on Bash. The renderer refuses to overwrite previous reviews and does not save over
the input `.blend`. Exit codes: `0` pass, `1` needs correction/budget stop, `2` invalid
or missing evidence. Draft validation alone is not acceptance.

## Correction loop

Use the scorecard's order: evidence/camera errors → face and body → hair → outfit →
accessories → material/lighting polish. Missing critical accessories are identity
blockers and move ahead of cosmetic work.

1. Keep the previous accepted checkpoint; freeze camera, pose, scale and lighting for
   comparisons unless the camera is the recorded defect.
2. Choose <=3 fixes. Name the object/region, discrepancy, intended adjustment and
   exact views/measurements that must improve.
3. Change that stage only; rerender all views and rescore critical regions.
4. Pass `--previous <previous-score.json>` from round 2 onward. A spec change starts
   a new series; never compare different specs as the same baseline.
5. Revert regressions in passing identity locks. At the budget or plateau limit return
   `needs_revision`, best checkpoint and next pass. Never lower thresholds or skip
   a category to declare high fidelity.

## Routing and delivery

- Use `threejs-image-generator` only when reference generation is needed; originals
  remain authoritative. Respect user-selected image tools.
- Use `threejs-3d-generator` optionally for a base mesh or later rigging. Load its
  provider rules first. Its fused-mesh requirement is provider-specific; keep Blender
  body, hair, outfit and accessories editable as separate components.
- Load `threejs-qa-release` when an export enters a Three.js game. Identity acceptance
  does not establish browser performance, rig quality, animation or game release.
- Do not require paid generation for standalone Blender work. Do not label primitive
  fallback geometry high fidelity when the needed modeling capability is unavailable.

Report source/spec identity, assumptions, checkpoint, manifest, category scores and
metrics, review method, unresolved failures and iteration count. On failure, state
the next prioritized correction and link the actual evidence.

This adapts the repository's multiview/T-A-pose generate→validate→retry cycle,
measured-evidence/fresh-eyes scorecard and visual-verification checklist. The complete
character gates are packaged here without a mandatory sibling dependency.
