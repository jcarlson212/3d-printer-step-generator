# CAD masterclass: sculpting beautiful, intricate chess pieces in build123d

This is the core craft reference. Read it as the playbook for *how* to turn a brief
into a sculptural, print-ready solid — not just a blocky approximation. The goal is
work that looks turned on a lathe and hand-carved, with classical detail, not a
stack of primitives. Aim higher than the reference STLs: those are the floor.

---

## 1. How solid CAD actually works (and why it matters here)

build123d sits on the OpenCascade B-rep kernel. A solid is a closed shell of exact
analytic faces (planes, cylinders, cones, NURBS) — not a mesh. Practical consequences:

- **Curves are exact.** A revolved profile is a true surface of revolution, so the
  body reads as smoothly turned at any scale. Prefer revolve/loft/sweep over stacks
  of cylinders whenever the form is round.
- **Booleans are exact.** Union/cut/intersect produce new exact topology. This is how
  you carve detail: model the gross form, then *subtract* flutes, slits, crenels,
  engraving, and erosion.
- **Fillets/chamfers are first-class.** Rounding edges isn't cosmetic — it's how you
  get the soft, worn, hand-finished read of a real piece, and it removes stress
  risers and sharp print artifacts at the same time.
- **One body.** The deliverable is ONE watertight manifold solid bound to `result`.
  Build sub-parts freely, then fuse. Validate mentally: every feature must connect.

Two APIs coexist; pick one per solid and don't interleave them:
- **Algebra API** — objects + operators: `result = base + neck - flute`. Best for
  assembling primitives and boolean detailing.
- **Builder API** — `with BuildPart()/BuildSketch()/BuildLine()` context blocks. Best
  for profile-driven forms (revolve, loft, sweep) where you sketch then operate.

---

## 2. The five form-making operations

These do 95% of the work. Master them before reaching for primitives.

### revolve — every body of rotation (pawn stem, all collars, finials, the spine of every piece)
Sketch a closed HALF-profile in a plane that contains the Z axis (e.g. `Plane.XZ`),
on the +X side, then spin it about Z. The silhouette you draw *is* the piece.
```python
with BuildPart() as part:
    with BuildSketch(Plane.XZ) as profile:
        with BuildLine():
            # Half-section from base (bottom) up to the finial, hugging the Z axis.
            # Use lines for collars/steps and Spline for the soft baluster curves.
            Polyline((0, 0), (16, 0), (16, 4))            # base disc edge
            Spline((16, 4), (6, 20), (9, 34), tangents=((0, 1), (0, 1)))  # body sweep
            Polyline((9, 34), (0, 40))                    # neck to top, back to axis
            Line((0, 40), (0, 0))                         # close along the axis
        make_face()
    revolve(axis=Axis.Z)
result = part.part
```
The art is in the profile: classical pieces are a sequence of **ogees** (S-curves),
**tori** (bead rings), **fillets** (coves), and **astragals** (small half-round
collars). Draw them with `Spline` for sweeps and short `Line`/`RadiusArc` segments
for crisp rings. Vary curvature — a lifeless taper looks 3D-printed; a turned
baluster breathes.

### loft — organic transitions between changing cross-sections (the knight's neck/head, a tapering twisted body)
Stack sketches at different heights/orientations and skin between them.
```python
with BuildPart() as neck:
    for z, (rx, ry), tilt in [(0, (9, 9), 0), (14, (7.5, 9.5), 8),
                               (26, (6, 11), 16), (34, (7, 13), 22)]:
        with BuildSketch(Plane.XY.offset(z).rotated((0, tilt, 0))):
            Ellipse(rx, ry)
    loft()
result = neck.part
```
Lofting elliptical sections along a leaning spine gives the knight's arched,
forward-leaning neck far better than any boolean of primitives. More sections =
more control over the curve.

### sweep — a constant (or scaled) profile driven along a path (manes, handles, ribs, the throat line)
```python
with BuildPart() as mane:
    with BuildLine():
        path = Spline((0, 34, 30), (-6, 30, 24), (-7, 20, 16), tangents=...)
    with BuildSketch(Plane.XZ):
        Ellipse(3, 1.6)        # the mane's cross-section
    sweep()
```

### extrude + make_face — plates, crests, flat heraldic detail
Sketch a 2D outline (letters, a shield, a cross), extrude, then fuse or cut.

### fillet / chamfer — the finishing pass that makes it look real
```python
result = fillet(result.edges().group_by(Axis.Z)[0], radius=1.2)   # soften base rim
# Select edges by position/length/geometry, then round. Wrap risky selections:
try:
    result = fillet(result.edges().filter_by(GeomType.CIRCLE).sort_by(Axis.Z)[-1], 0.6)
except Exception:
    pass
```
Round nearly every hard transition a little. Sharp CAD edges are the #1 tell of an
amateur model and the #1 source of chipping in PLA.

---

## 3. Carving intricacy (the subtractive vocabulary)

Detail is mostly *removed*, via polar/grid arrays of cutting tools.

### Fluting (Greek column flutes down a body) — `PolarLocations`
```python
flute = Cylinder(radius=1.4, height=22)                 # the cutter
flutes = PolarLocations(radius=8.5, count=20) * Pos(0, 0, 14) * flute
result = body - flutes
```
20–24 shallow half-round flutes turn a plain stem into a Doric/Ionic column — the
backbone of a "Greek architecture" theme. Reeding is the same idea in reverse (add
half-rounds instead of cutting).

### Crenellations (rook battlements) — polar array of box cuts
```python
merlon_gap = Box(6, 14, 9)
gaps = PolarLocations(radius=0, count=8) * Pos(0, 13, top_z) * merlon_gap
result = tower - gaps                                   # leaves 8 merlons
```

### Beading / astragal rings (necklaces of tiny spheres or a torus)
```python
beads = PolarLocations(radius=11, count=28) * Sphere(1.1)
result = body + Pos(0, 0, collar_z) * beads
```

### Engraving & inscriptions — `Text` cut shallowly into a face
```python
with BuildSketch(Plane.XY.offset(base_top)) as t:
    Text("ΣΕΛΗΝΗ", font_size=4)
result -= extrude(t.sketch, amount=-0.6)               # recessed, ≥ min feature
```

### Egg-and-dart, dentils, acanthus — repeated motif via arrays of small lofted/revolved units fused around a collar. Build ONE unit, array it with `PolarLocations`, fuse.

### Weathered / eroded marble (the Parthenon-fragment look)
Two complementary techniques, both boolean:
```python
import random
random.seed(7)                                         # deterministic erosion
# (a) chip the silhouette: subtract a few wedge/box cuts at the edges & a broken corner
result -= Pos(11, 0, 30) * Rot(0, 35, 0) * Box(8, 20, 8)   # a fractured break face
# (b) pit the surface: scatter shallow spherical divots
for _ in range(40):
    a = random.uniform(0, 6.28); z = random.uniform(6, 50); r = random.uniform(7, 11)
    result -= Pos(r*math.cos(a), r*math.sin(a), z) * Sphere(random.uniform(0.6, 1.4))
result = fillet(result.edges().filter_by(GeomType.LINE).group_by(SortBy.LENGTH)[-1][:6], 0.5)
```
Erosion reads as antiquity; a clean *broken* face (one big planar cut, lightly
filleted) sells "fragment of the Parthenon" better than uniform roughness. Keep
pits shallow so walls stay above the min wall and the piece stays printable.

> Texture vs geometry: true "marble grain" is a surface finish (print material /
> post-processing), not B-rep geometry. Express the theme through *form* — eroded
> planes, chipped edges, classical motifs, a matte broken profile — and note finish
> in the explanation.

---

## 4. Proportion and beauty (Staunton, classically informed)

- **Silhouette first.** A piece is judged in profile from across a board. Make the
  outline alone unmistakable and elegant before adding surface detail.
- **Rhythm of the turning.** Alternate convex (bead/ovolo) and concave (cove/scotia)
  elements up the body; separate them with crisp fillets. Avoid one monotonous taper.
- **Golden-ish vertical divisions.** Base : body : crown roughly 1 : 2 : 1 reads well;
  place the visual "waist" a bit below center.
- **A wide, confident base.** A slightly oversized, stepped, filleted base both looks
  grounded and survives shipping. Add a shallow felt recess underneath.
- **Classical grammar for a Greek theme.** Fluted shaft, an echinus/ovolo under the
  collar, a torus base ring, restrained egg-and-dart or bead-and-reel — the language
  of the Parthenon. Don't over-ornament; antiquity is disciplined.
- **Coherent family.** Share base diameter, collar style, and surface treatment across
  a set so the pieces are obviously siblings.

---

## 5. Per-piece recipes (skeletons — elaborate, don't copy verbatim)

Each is a starting structure. Add the curvature, flutes, beading, fillets, and theme
treatment from §3–4 to make it beautiful. Dimensions in mm; parameterize at the top.

### Pawn — pure revolve
Ball finial on a collared, ovee stem from a domed base. One clean `revolve` of a
well-drawn half-profile (base torus → cove → ball-neck astragal → sphere top), then a
base-rim fillet. The whole piece is the profile — spend your effort there.

### Rook — revolve + crenellation cuts
```python
tower = revolve(<cylindrical castle half-profile with a torus base and top ring>)
tower -= PolarLocations(0, 8) * Pos(0, R_top, top_z) * Box(gap_w, wall*3, crenel_h)
result = fillet(tower.edges()..., 0.6)        # soften merlon tops & base
```
Optional: vertical reeding on the shaft, a course of dentils under the battlement.

### Bishop — revolve + mitre slit + bead finial
Revolve the tall ogee body and mitre; cut the characteristic diagonal slit with a
thin rotated box (`Pos*Rot*Box`, width > nozzle); top with a small revolved bead.
Add a ring of beading at the collar.

### Queen — revolve body + coronet of points + ball finial
Revolve the elegant body; build ONE coronet spike (a small lofted/ revolved cone),
array it with `PolarLocations(radius, count=9)`, fuse; cap with a sphere on an
astragal. Keep spikes thick enough not to be fragile; chamfer their tips.

### King — revolve body + cross finial
Revolve the stately body and crown; build a cross patée from two filleted boxes (or
extruded profile) and fuse on a short neck. Thicken cross arms to the min wall and
chamfer the arm ends; the cross is the classic failure point.

### Knight — the sculptural one (loft + sweep + boolean detailing)
This is where craft shows. Don't approximate with stacked boxes.
1. **Base + collar:** revolve a disc + collar (shared with the set).
2. **Neck/head spine:** `loft` 5–7 elliptical sections along a forward-leaning,
   arching spine (see §2 loft) — wider at the jaw, narrowing at the poll. Lean the
   sections so the crest is convex (back) and the throat concave (front).
3. **Muzzle:** fuse a tapered lofted/swept block angled down-forward; round the nose
   with a fillet; suggest nostrils with two tiny shallow sphere cuts.
4. **Jaw & cheek:** fuse a softened wedge; blend into the neck with fillets.
5. **Mane:** `sweep` an elliptical section down the crest spline; then cut shallow
   parallel grooves (a small array of thin box/cylinder cuts) to suggest locks.
6. **Ears:** two small lofted cones at the poll, leaning back; give them real
   thickness — no needle tips.
7. **Eyes/brow:** a brow ridge (small swept bead) and a shallow spherical eye socket
   cut on each side give it life.
8. **Unify:** fuse everything, then a global light fillet pass on the major seams so
   it reads as carved stone, not assembled blocks.
9. **Theme:** apply §3 erosion / a broken classical break face for the Parthenon look.
Reinforce the neck (load-bearing, #1 ship-failure point); keep the muzzle's forward
overhang within the material's overhang limit or short enough to self-support.

---

## 6. Printability is part of the design (FDM / PLA)

Weave these in from the first sketch, not as an afterthought:
- Flat, stable, slightly-wide base; natural print orientation is base-down (no full
  support raft). Add a felt recess under the base.
- Keep overhangs within the material limit (≈45° from vertical) or short; the knight's
  muzzle and the queen's coronet are the usual offenders — angle or thicken them.
- Detail (flutes, slits, engraving, crenel gaps) must be wider than the nozzle and
  walls thicker than the min wall, or it won't resolve.
- No thin unsupported protrusions unless designed as a separate, detachable part.
- Fillet sharp internal corners (stress risers) and outer edges (chipping).
- One connected, watertight, manifold solid — fuse all sub-parts; verify nothing
  floats or is zero-thickness.

---

## 7. Output discipline

- Parameterize named dimensions at the top so the piece is rescalable.
- Assign the final fused solid to `result`.
- Build a genuinely sculptural form — profiles with real ogee rhythm, classical
  motifs, sculpted knight anatomy, thematic erosion — then a finishing fillet pass.
  Beauty comes from the curves and the carving, not from more primitives.
```
