# Character Project Instructions

Scope: this character project and descendants. Merge with existing instructions;
never overwrite unrelated rules. Load `blender-character-fidelity` from installed
skills or the source repository's `skills/` directory.

- Treat original references and locked `character-spec.json` as the identity contract.
  Keep hashes, provenance, observed/inferred/unknown labels and style intent. Generated
  views never override originals. Resolve conflicting faces/outfits explicitly.
- Preserve face shape, body ratios, hair contour, garment construction and signature
  accessories. Do not beautify, idealize, change age cues, remove asymmetry or substitute
  a generic anatomy preset to improve a score.
- Follow reference lock → turnaround → blockout → identity geometry → camera match
  → lookdev → full-view review → correction. Save checkpoints at each gate. Detail
  and texture must not conceal failed silhouettes or facial structure.
- Match source projection and pose before diagnosing geometry. Keep canonical and
  source-matched cameras separate; do not auto-fit individual revision renders.
- Keep editable components in CHARACTER, attached landmark markers and REVIEW scene
  cameras as defined by the contract. Never move markers independently to satisfy QA.
- Save/pack/reopen the blend before final evidence. Use new `reviews/iteration-NNN/`
  directories. Record spec/scene/image hashes, frame, Blender version and camera settings.
- Measure face landmarks, body ratios and comparable silhouettes. These are geometric
  proxies; high IoU, CLIP or embedding similarity does not prove character identity.
- Inspect every capture. Give an independent reviewer originals, approved spec, all
  captures, rubric and measurements; withhold builder scores/rationale. Use the lower
  category scores. Otherwise document an adversarial self-review and its limitation.
- Fail acceptance on missing critical features, inadequate/stale evidence, failed
  measurements, low category scores or unresolved identity defects. Total score must
  never compensate for an incorrect face or body.
- Fix evidence/camera, face/body, hair, outfit/accessories, then polish. Choose <=3
  specific changes per round; recheck passing locks. At budget/plateau return
  `needs_revision`, best checkpoint and next pass; never relax thresholds silently.
- Keep secrets out of files; use external generators only when authorized and in scope.
  Do not upload source images as an incidental verification step.
- Check Three.js exports separately for units/axes, materials, rigs, animation and
  runtime budgets. Blender identity acceptance is not game release acceptance.
