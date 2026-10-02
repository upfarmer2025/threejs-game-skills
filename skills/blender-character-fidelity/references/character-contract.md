# Character contract

## Contents

- Project and reference authority
- Spec and metrics
- Blender setup
- Evidence and reviews
- Tool boundary

## Project and reference authority

```text
character-project/
  AGENTS.md
  character-spec.json
  references/original/
  references/turnaround/
  references/masks/
  model/character.blend
  model/checkpoints/
  reviews/stages.md
  reviews/iteration-001/{manifest.json,review.json,score.json,*.png}
  exports/
```

All JSON artifact paths are relative to the spec folder; absolute paths, traversal
and symlinks escaping it are rejected. Keep original image bytes immutable. Hash with:

```bash
python3 -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('references/original/front.png').read_bytes()).hexdigest())"
```

Authority: explicit user decisions → original views → approved inference → generated
auxiliary views. Resolve conflicting originals explicitly. Hidden backs/accessories
remain unknown until a design decision; do not call their reconstruction verified.

## Spec and metrics

The example is deliberately `draft`. The standard-library validator implements this
small versioned contract directly; it is not a generic JSON Schema interpreter.

For incomplete inputs, a draft may use `null` proportions and `measurements: []`.
Do not invent body ratios from a portrait to satisfy a validator. Ready/final validation
requires the supported measurements and complete decisions described below.

| Field | Meaning |
| --- | --- |
| `schema_version`, `character_id`, `status` | Version 1, stable identifier, draft/locked. |
| `style` | Anatomy/rendering intent and traits that must not be idealized. |
| `coordinates` | Meters, +Z up, faces -Y, top-left image UV; left/right are anatomical. |
| `sources[]` | ID, path, SHA-256, original/generated kind, view and provenance notes. |
| `locks[]` | ID, category, description, source IDs, certainty, critical flag, inference decision. |
| `proportions` | Working height, head units and provenance/uncertainty notes. Executable ratio checks go in measurements. |
| `review` | Scene/collection, frame, resolution, samples/seed, view transform, named cameras/landmarks. |
| `measurements[]` | Original source, comparable view, category, target, tolerance and correspondence notes. |
| `quality` | Weights, per-category/overall floors, budget and plateau policy, frozen before iteration. |

All five categories need locks: face/body/hair/outfit/accessories. If no accessories
exist, lock their absence. Inferred locks require a `decision` recording a user-approved
or task-authorized assumption. Never fill it just to pass. Critical unknowns block ready
validation; noncritical unknowns remain disclosed. Every lock is visually reviewed.

Final acceptance needs at least one original-source face `landmarks` check and body
`ratio` check. Never invent numeric targets. Sources and targets share the declared
view/crop/pose; for perspective originals add a source-matched camera. Generated views
are modeling guides, not independent measurements of the original.

- `landmarks`: `targets` maps >=3 visible IDs to `[u,v]` in [0,1]. `normalizer` is
  reference head/face height divided by frame height. NME = mean pixel distance /
  reference head height. u distances are scaled by width/height for nonsquare frames.
- `ratio`: `points` = `[a,b,c,d]`; actual = pixel distance(a,b)/distance(c,d);
  error = `abs(actual-target)/target`. No front-vs-oblique width comparison.
- Optional `silhouette`: `mask_path` and `mask_sha256` bind a binary reference mask.
  White is foreground. Compare against clay-render alpha >=128 at identical resolution;
  error = `1-IoU`. Do not resize/align automatically. This MVP compares the entire
  character, so the category must be body. Hair/outfit IoU needs separately authored
  segmentation; do not mislabel whole-body IoU as hair identity. This check needs Pillow.

Each check has `id/category/view/source_id/tolerance/notes`. All checks are gates.
Example tolerances, to calibrate before locking: face NME .035; body ratio relative
error .04; silhouette error .10 (IoU >=.90). These are policies, not universal constants.
Sources with too little observable anatomy may be insufficient for a final fidelity
claim: prepare a draft and identify missing evidence instead of fabricating it.

## Blender setup

Create scene `REVIEW` with renderable meshes in `CHARACTER`, lights, cameras and
attached landmark objects. Exclude floors/background planes/reference cards from
render visibility; alpha must represent the character alone. Convert hair curves in
a review copy if needed: the MVP requires all character renderables to be meshes.
Pack image textures. The renderer rejects unsupported unbound external dependencies
(linked libraries, unpacked images, movie clips, volumes and external simulation caches).

Use one fixed pose/frame for all views. Canonical full-body cameras share orthographic
scale, target height and +Z vertical axis. With character facing -Y:

| View ID | Direction from target | Projection |
| --- | --- | --- |
| front | (0,-1,0) | ORTHO |
| side | (+1,0,0), anatomical left | ORTHO |
| back | (0,+1,0) | ORTHO |
| front_three_quarter | (+1,-1,0) | ORTHO |
| back_three_quarter | (+1,+1,0) | ORTHO |
| face_front / face_side / face_three_quarter | corresponding direction, head target | declared ORTHO or PERSP |
| source_match (optional) | fit the original image | declared ORTHO or PERSP |

Minimum: front/side/back plus all three face views. Add both full-body 3/4 views for
five-view mode; add opposite-side/detail views for asymmetry. Keep perspective originals
and canonical orthographic comparison distinct. Camera orientation recipe:
`camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()`.
Choose framing once and freeze it; a justified reframe requires a new comparison baseline.

Map landmark IDs to objects, e.g. `jaw_left: LM_jaw_left`. Vertex-parent or constrain
them to the evaluated geometry. Inspect attachment after sculpt/retopology. Loose
empties are not evidence of anatomy. Only annotate visible source landmarks; depth
alone does not establish visibility, so review occlusion manually.

Renderer: CPU Cycles, fixed frame/resolution/samples/seed, transparency, disabled DOF,
exposure 0, gamma 1, specified view transform. It emits clay and neutral-material passes
under the REVIEW scene's authored neutral lights and records camera/color settings.
Use a separate beauty scene for presentation. Runtime adjustments are never saved.

The lighting snapshot covers world/light node links and common socket values, packed
images, ramps and light shape/size/angle settings. Custom shader or driver state still
needs an explicit visual check; the snapshot is not a complete scene serializer.

## Evidence and reviews

The manifest binds spec hash, saved blend path/hash, iteration, Blender version, frame,
render settings, cameras, geometry diagnostics, landmark projections and PNG paths/hashes.
No completed manifest is written on partial render failure. Score JSON also binds the
manifest/review hashes. Changing inputs invalidates acceptance.

Load a distinct saved `.blend` checkpoint for each iteration. Never overwrite a blend
referenced by an earlier manifest: the next round rechecks that earlier file too.
Previous scores are recomputed from their bound manifests, reviews and measurement
evidence; editing a summary score or plateau counter invalidates the history.

`review.json` fields: `schema_version: 1`, actual `manifest_sha256`, `builder` and
`fresh_eyes`. Each reviewer object has:

- `reviewer`: actual nonempty identity; independent reviewer differs from builder.
- `inspected_views`: all manifest view IDs, no curated subset.
- `categories`: all five, each with numeric 0–100 score, reason and evidence view IDs.
- `locks`: every spec lock ID maps to `pass` boolean plus a concrete reason.
- `hard_failures`: observed blockers, empty only after image inspection.
- `fresh_eyes.mode`: independent/adversarial_self; self-review also needs a
  `case_against` sentence in each category.

Use [review.example.json](../assets/review.example.json); null scores are intentional.
Hash the manifest using the same command as above. Independent reviewers must not see
builder scores or rationale. Their full capture coverage is recorded as an attestation;
the script cannot verify that a person actually looked at an image.

## Tool boundary

`validate_character.py` checks the spec and, with `--ready`, original hashes/decisions.
`render_review.py` captures existing geometry/cameras; it does not build faces or solve
lenses. `score_identity.py` recomputes proxies, checks freshness, reconciles reviews and
orders corrections. Modeling, annotation and perceptual review still need image inspection.

Blender's [world_to_camera_view](https://docs.blender.org/api/current/bpy_extras.object_utils.html)
returns bottom-left NDC; the renderer converts to top-left UV. Put
[--python-exit-code](https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html)
before `--python` so script exceptions fail headless runs.
