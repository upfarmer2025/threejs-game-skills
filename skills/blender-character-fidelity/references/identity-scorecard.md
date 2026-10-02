# Identity scorecard

Adapt measured evidence + fresh eyes + explicit next pass, not game-scene anchors.
Color entropy, edge density and triangle count do not establish likeness.

| Category | Default weight | Identity features | Evidence |
| --- | ---: | --- | --- |
| face | 35% | Skull/jaw/chin, cheeks, eye spacing/tilt, brow, nose, mouth, profile, age/style cues | Neutral face front/side/3/4; original-source NME |
| body | 25% | Head/body, shoulders/hips, torso/leg split, limb lengths/volumes | Canonical views, source-matched ratios, optional silhouette IoU |
| hair | 20% | Hairline, bang split, crown, clumps, side/back contour, asymmetry | Complete silhouette set and closeups |
| outfit | 15% | Cut, layers, neckline, seams, hem, thickness, major colors | Front/side/back and neutral material crops |
| accessories | 5% | Count, anatomical side, size, motif, position and attachment | Relevant views and per-feature locks; absence if appropriate |

Score anchors: 0 missing/unreviewed; 50 generic approximation; 70 recognizable but
major drift; 85 close with small visible deviations; 95 very close across all views;
100 no discrepancy discernible at reference resolution. These are project assessment
scales, not biometric probabilities or scientifically calibrated perceptual metrics.

Defaults: every category >=85, weighted total >=90, all configured measurements within
tolerance, every lock passing, no hard failure, all evidence current. Freeze policy
before a series. The script reconciles scores; it never invents subjective scores.

## Automatic failures

- Wrong face, body proportions, age cues, hair shape, costume or visual style.
- Missing/wrong-side critical accessory, or geometry hidden by texture/light/hair.
- Generated variants replace originals; hidden details are scored as observed.
- Pose/camera/crop mismatch, clipping, occluded diagnostic views or missing views.
- Stale hashes, missing review/metric, or uninspected captures.
- Loose landmarks moved without changing geometry, or a final blend that differs
  from the rendered evidence.

The scripts catch structure/hash/metric failures. Reviewers must report semantic
failures they cannot detect, including occlusion and stylized face drift. A machine
gate cannot substitute for image inspection.

## Fresh-eyes review

Give an independent reviewer only originals, approved spec, complete captures, this
rubric and measured evidence. Withhold builder scores and implementation rationale.
Include weak angles. Take the lower category score and retain both reviews and all
failures. To overturn a discrepancy, write a new review citing concrete evidence;
never silently overwrite the lower score.

If independent review is unavailable, write the strongest case against each category
before scoring. Label `adversarial_self` and disclose the weaker independence. Never
call a second builder pass an independent review.

## Prioritized correction and stop conditions

P0: invalid evidence, source contradiction or camera/pose mismatch; repair comparison.
P1: hard failures, failed critical locks, face/body. A missing critical accessory belongs here.
P2: failed noncritical locks, hair, garment construction, accessory shape/placement.
P3: material/light/surface polish after identity passes.

Every next pass specifies region/object, difference, adjustment, target view/metric
and threshold. Example: `Head jaw: side chin projects too far; retract chin only;
recheck profile NME and front jaw width within locked tolerances without regression.`

Choose <=3 fixes each round. Stop at `max_iterations` (default 4) or after
`plateau_rounds` improvements smaller than `plateau_delta` (defaults 2 and 1 point).
Regression counts as no improvement. Return `needs_revision`, best checkpoint and
remaining failures; a budget stop is not a pass. Require same spec hash and contiguous
iteration IDs for comparisons. Inspect prior images too: score changes alone do not
describe all local regressions.
