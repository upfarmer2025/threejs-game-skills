# Modeling and reference playbook

## Consistent references

Keep originals immutable. Record crop boxes for face/detail crops. Normalize display
scale with shared anatomical head-top, chin, shoulder, waist, crotch, knee, ankle and
sole guides; distinguish hair crown from skull. Never stretch each body part separately.

Three views: front, actual 90-degree side, back. Five views: add front and rear 45-degree
views. Use one neutral T/A pose, expression and scale. Keep hairline, garment seams,
hem and accessories consistent. Add face front/side/3/4 and detail crops. For asymmetry,
add the other side rather than mirroring.

For generated turnarounds request: preserve the exact person, face, age cues, body
ratio, hair mass, palette, outfit and accessories; change view angle only; shared pose,
scale and neutral light; no redesign/beautification. Inspect against originals and mark
hidden details as hypotheses. One perspective image does not uniquely determine 3D shape.

## Model masses before details

Use real scale only if known; otherwise disclose a working scale. Measure ratios first.
Keep head/body/hair/outfit/accessories editable. Primitives are useful blockout evidence,
never a finished faithful character. Check front/side/back together; defer subdivision.

| Lock | Prioritize | Misleading shortcut |
| --- | --- | --- |
| Face | Skull, jaw taper, cheek planes, chin projection, eyes, nose root/tip, mouth | Painted features on an incorrect head; generic attractive face |
| Body | Head/body, neck/shoulder, ribcage/pelvis, torso/leg split, limb volumes | Longer legs/narrower waist called polish |
| Hair | Hairline, bangs, crown, side depth, nape, primary clumps | Strands over an incorrect helmet silhouette |
| Outfit | Layer order, cut, fastening, sleeves/hem, thickness and tension | Color blocks painted on the body |
| Accessories | Count, anatomical side, scale, motif and attachment | Generic substitutes or omitted small objects |

Refine identity planes before pores, stitches and strands. Preserve stylized anatomy.
Check neutral clay. Retopology/UV/rigging are separate tasks; after remesh or deformation,
reattach landmarks and recheck likeness.

## Cameras and lookdev

Estimate perspective vs orthographic. Use vanishing cues and foreshortening; fit crop,
lens, distance, tilt/roll and pose against distributed correspondences. Record uncertainty
instead of claiming exact focal length from one image. Keep camera/pose fixed during
geometry comparisons; an evidence-backed camera change requires a new baseline.
Use side/3/4 views to distinguish jaw depth from optical errors. Do not warp a render
independently of model/camera to improve a metric.

Start with neutral clay and readable key/fill light. Match large color relationships
and material response before detail. Preserve cel-style anatomy/shading when appropriate;
photoreal skin and glossy hair are not universally better. Keep beauty lighting separate.
Inspect saved renders, not merely the viewport or a successful script log.

## Final visual checklist

- Reopen the saved blend; dependencies resolve.
- Full-body and face view sets are complete, readable and unclipped.
- Face/profile/hair/accessories agree across angles as the same character.
- Pose, camera, crop and resolution support the declared measurements.
- Source, spec, model, render and review hashes are current.
- Both clay and neutral materials were inspected; beauty hides no defects.
- Landmark attachment and source visibility were checked manually.
- All five categories and individual locks are reviewed; uncertainty is disclosed.
- Export/reimport, animation and browser checks run separately when requested.

## Reused repository mechanisms

| Existing mechanism | Character adaptation |
| --- | --- |
| `threejs-3d-generator/SKILL.md`: multiview, T/A pose, generate/validate/retry | Reference authority, consistent turnaround, staged checkpoint/review/correction; optional base mesh |
| `threejs-aaa-graphics-builder/references/visual-scorecard.md`: evidence, fresh eyes, lower score, next pass | Landmark/ratio/IoU proxies + five identity categories + full neutral capture review |
| `threejs-qa-release/references/checklists/visual-verification.md`: captures, deterministic states, baselines | Saved-blend renders, fixed camera/frame/seed/settings, view coverage, immutable iterations |

Keep game-specific scorecards, browser QA and provider rig restrictions in their own
skills; do not import them blindly into standalone character modeling.
