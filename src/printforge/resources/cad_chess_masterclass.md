# CAD masterclass: sculpting beautiful, intricate chess pieces in build123d

This is the core craft reference and the **mechanics manual** for emitting valid
build123d that exports to STEP. Read it as the playbook for *how* to turn a brief
into a sculptural, print-ready solid — not just a blocky approximation. The goal is
work that looks turned on a lathe and hand-carved, with classical detail, not a
stack of primitives.

Every code block below has been **executed and verified to produce a valid STEP**
on build123d 0.11 — copy these patterns and trust them. Any reference STLs you are
shown are loose, abstract inspiration for what a knight (or any piece) *can* look
like; they are not targets to match. Your design should be *better* than them and
may take a different form. Their main value is grounding the mechanics of producing
clean STEP code.

## 0. Verified API truths (the things models get wrong)

- **`PolarLocations(radius, count) * obj` returns a LIST of placed copies**, not a
  single object. You can `body + cutters` and `body - cutters` (both work), but you
  CANNOT `Pos(...) * cutters` (a list can't be left-multiplied by a transform). To
  place an arrayed feature at a height, translate the object FIRST, then array:
  `PolarLocations(radius=10, count=28) * (Pos(0, 0, 12) * Sphere(1.2))`. Same for
  `GridLocations`.
- **Builder vs algebra — don't interleave them in one expression.** Inside
  `with BuildPart() as p:` use operations (`revolve()`, `loft()`, `sweep()`,
  `extrude()`, `add(...)`); get the solid out with `p.part`. Outside a builder, use
  the algebra API (`a + b`, `a - b`, `Pos`, `Rot`). Mixing the two in a single line
  is the #1 cause of errors.
- **`Polyline`/`Line`/`Spline`/`RadiusArc` are BuildLine-only.** Use them only inside
  `with BuildLine():`, then `make_face()` inside the enclosing `with BuildSketch():`.
- **Fillet edge selection can raise "no suitable edges"** — always wrap a fillet whose
  edge set you're not 100% sure of in `try/except Exception: pass`.
- `Pos(x, y, z) * shape` translates; `Rot(rx, ry, rz) * shape` rotates (degrees).
  Primitives (`Box`, `Cylinder`, `Sphere`, `Cone`) are centered at the origin.

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

### Fluting (Greek column flutes down a body) — `PolarLocations` [verified]
Make the cutter tall enough to span the fluted region, then array and subtract.
Don't try to `Pos` the arrayed list — translate is baked into the cutter's height.
```python
body = Pos(0, 0, 22) * Cylinder(radius=10, height=44)
flute = Cylinder(radius=1.6, height=46)                 # spans the full body
result = body - PolarLocations(radius=10, count=20) * flute
```
**Doric** ≈ 20 broad flutes meeting at a sharp ridge (arris); **Ionic** ≈ 24 deeper
flutes separated by a flat fillet. Reeding is the reverse — `+` half-rounds instead
of cutting. Both are the backbone of a "Greek architecture" theme.

### Crenellations (rook battlements) — polar array of box cuts [verified]
`radius=0` with `rotate=True` puts a copy at center rotated to each angle; a long
box then cuts a notch in each direction.
```python
tower = Pos(0, 0, 22) * Cylinder(radius=11, height=44)
gap = Box(7, 30, 9)
result = tower - PolarLocations(radius=0, count=8) * (Pos(0, 0, 42) * gap)
```

### Beading / astragal (bead-and-reel ring of spheres) [verified]
Position the sphere FIRST, then array (a `PolarLocations * shape` result is a list
and cannot be `Pos`-multiplied).
```python
body = Pos(0, 0, 20) * Cylinder(radius=10, height=40)
result = body + PolarLocations(radius=10, count=28) * (Pos(0, 0, 12) * Sphere(1.2))
```

### Engraving & inscriptions — `Text` cut shallowly into a face [verified]
```python
base = Pos(0, 0, 4) * Cylinder(radius=16, height=8)
with BuildSketch(Plane.XY.offset(8)) as t:
    Text("ΣΕΛΗΝΗ", font_size=5)
result = base - extrude(t.sketch, amount=-0.6)          # recessed, ≥ min feature
```

### Egg-and-dart, dentils, acanthus — build ONE motif unit (a small lofted/revolved
solid), array it around a collar with `PolarLocations`, fuse. Egg-and-dart sits on an
ovolo; dentils are a ring of small rectangular blocks under a cornice.

### Weathered / eroded marble (the Parthenon-fragment look) [verified]
**Restraint is everything.** Real weathering is one strong broken face plus a FEW
shallow chips concentrated near edges and high points, with large SMOOTH marble
passages in between. Do NOT pepper the whole surface with uniform pits — that reads as
noise, not antiquity. Aim for ~6–12 shallow pits, not dozens.
```python
import math, random
random.seed(7)
result = Pos(0, 0, 20) * Cylinder(radius=10, height=40)
# (a) one clean broken/fractured face — the dominant "fragment" read
result -= Pos(9, 0, 34) * Rot(0, 35, 0) * Box(10, 26, 10)
# (b) a FEW shallow chips, weighted to the upper/edge region (not all over)
for _ in range(8):
    a = random.uniform(0, 6.283); z = random.uniform(24, 38); rr = random.uniform(8.5, 10.5)
    result -= Pos(rr*math.cos(a), rr*math.sin(a), z) * Sphere(random.uniform(0.5, 1.0))
```
Erosion reads as antiquity; a clean *broken* face (one big planar cut, lightly
filleted) sells "fragment of the Parthenon" better than uniform roughness. Keep
pits shallow so walls stay above the min wall and the piece stays printable.

> Texture vs geometry: true "marble grain" is a surface finish (print material /
> post-processing), not B-rep geometry. Express the theme through *form* — eroded
> planes, chipped edges, classical motifs, a matte broken profile — and note finish
> in the explanation.

---

## 3b. Advanced surface & form techniques (verified)

These unlock whole design families beyond the plain revolve. Each is executed and
exports a valid STEP. They generalize: apply the twist/ripple/lattice/knurl to any
piece's body, not just the demo shape.

### Twisted / spiral flutes — loft rotated cross-sections [verified]
A twisted column comes from lofting the SAME fluted cross-section repeated up the
height, each copy rotated a little. Build the cross-section from computed points in a
`Polyline(..., close=True)`.
```python
import math
def fluted_pts(r, amp, lobes, n=160):
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n
        rad = r + amp * math.cos(lobes * t)     # lobes flutes around
        out.append((rad * math.cos(t), rad * math.sin(t)))
    return out
height, slices, twist_deg = 50, 14, 90          # 90deg of twist over the height
with BuildPart() as col:
    for i in range(slices):
        z = height * i / (slices - 1)
        ang = twist_deg * i / (slices - 1)
        with BuildSketch(Plane.XY.offset(z).rotated((0, 0, ang))):
            with BuildLine():
                Polyline(*fluted_pts(9, 1.2, 12), close=True)
            make_face()
    loft()
result = col.part
```

### Rippled / swirled body — modulate the radius per section [verified]
Loft sections whose radius is a base silhouette plus a sinusoidal ripple whose phase
shifts with height (the swirl). Great for organic, flowing vases/bodies.
```python
import math
def wave_pts(z, n=160):
    base = 7 + 4 * math.sin(math.pi * z / 44)          # the silhouette
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n
        rad = base + 0.9 * math.sin(16 * t + 0.18 * z)  # 16 ribs; phase shifts w/ z -> swirl
        out.append((rad * math.cos(t), rad * math.sin(t)))
    return out
with BuildPart() as v:
    for i in range(22):
        z = 44 * i / 21
        with BuildSketch(Plane.XY.offset(z)):
            with BuildLine():
                Polyline(*wave_pts(z), close=True)
            make_face()
    loft()
result = v.part
```

### Porous / voronoi-style shell — hollow + punch cells [verified]
A true Voronoi is hard in B-rep; this reads the same: shell the body (outer minus a
slightly smaller inner), then subtract scattered cell holes, and keep a solid base for
strength. Keep hole count modest (each is a boolean; large counts are slow + heavy).
```python
import math, random
random.seed(3)
outer = Pos(0, 0, 24) * Cylinder(radius=11, height=48)
inner = Pos(0, 0, 24) * Cylinder(radius=8.5, height=49)
shell = outer - inner
holes = []
for _ in range(90):
    a = random.uniform(0, 6.283); z = random.uniform(4, 44)
    holes.append(Pos(10 * math.cos(a), 10 * math.sin(a), z) * Sphere(random.uniform(1.6, 2.8)))
result = (shell - holes) + Pos(0, 0, 3) * Cylinder(radius=14, height=6)  # solid base
```

### Helical rib (thread/rope) — sweep along a `Helix` [verified]
```python
core = Pos(0, 0, 22) * Cylinder(radius=8, height=44)
with BuildPart() as ribs:
    with BuildLine():
        Helix(pitch=14, height=42, radius=8.4)         # lefthand=True for opposite handedness
    with BuildSketch(Plane.XZ):
        Circle(1.3)
    sweep()
result = core + ribs.part
```

### Diamond knurl — crosshatched helical grooves [verified, heavy ~50s]
Don't cut hundreds of individual diamonds (too slow). Cut two opposing families of
helical grooves; the diamonds are what's left between them. `.rotate(Axis.Z, a)` spaces
the starts; `lefthand` flips the handedness.
```python
import math
band = Pos(0, 0, 10) * Cylinder(radius=10, height=14)
def grooves(lefthand, n=12):
    out = []
    for k in range(n):
        with BuildPart() as g:
            with BuildLine():
                Helix(pitch=10, height=16, radius=10, lefthand=lefthand).rotate(Axis.Z, 360 * k / n)
            with BuildSketch(Plane.XZ):
                Rectangle(1.1, 1.1, rotation=45)
            sweep()
        out.append(Pos(0, 0, 2) * g.part)
    return out
result = band - grooves(False) - grooves(True)
```

> Performance: knurl and dense porous shells do many booleans — keep counts modest
> and expect longer execution. Prefer twist/ripple (loft-based, cheap) when you can.

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

## 5. Per-piece recipes (verified — runnable starting points)

Every recipe below was executed and exports a valid STEP. They are deliberately
SIMPLE skeletons: take them as a correct scaffold, then layer on §3 detail (flutes,
beading, engraving, erosion), draw richer ogee profiles, and add fillets to make the
piece sculptural. Parameterize dimensions at the top. (FIDE Staunton: king ~95 mm;
Q > B > N ≈ R > P scale down; base diameter ~40–50% of height.)

### Pawn — pure revolve + ball finial [verified]
The whole piece IS the profile — spend your effort drawing the ogee curve well.
```python
import math
with BuildPart() as pawn:
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Polyline((0, 0), (14, 0), (14, 3))                       # base disc
            Spline((14, 3), (6, 8), (5, 16), tangents=((-0.3, 1), (0, 1)))   # cove
            Spline((5, 16), (6.5, 24), (4, 30), tangents=((0, 1), (-0.4, 1)))  # neck ogee
            Line((4, 30), (0, 33)); Line((0, 33), (0, 0))            # close on the axis
        make_face()
    revolve(axis=Axis.Z)
    add(Pos(0, 0, 36) * Sphere(5))                                   # ball finial
result = pawn.part
```

### Rook — revolve body + crenellation cuts [verified]
```python
tower = Pos(0, 0, 22) * Cylinder(radius=11, height=44)              # replace with a revolved profile
gap = Box(7, 30, 9)
result = tower - PolarLocations(radius=0, count=8) * (Pos(0, 0, 42) * gap)
```
Better: revolve a castle profile (torus base, slight entasis, top ring), then cut the
notches; optional vertical reeding + a course of dentils under the battlement.

### Bishop — revolve body + mitre slit + bead finial [verified]
```python
with BuildPart() as body:
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Polyline((0, 0), (13, 0), (13, 3))
            Spline((13, 3), (6, 12), (7, 30), tangents=((-0.3, 1), (0, 1)))
            Spline((7, 30), (3, 45), (0, 52), tangents=((0, 1), (-1, 0.6)))  # mitre
            Line((0, 52), (0, 0))
        make_face()
    revolve(axis=Axis.Z)
result = body.part - Pos(0, 0, 44) * Rot(0, 35, 0) * Box(3, 30, 16)  # diagonal slit
result += Pos(0, 0, 55) * Sphere(2.5)                                # bead finial
```

### Queen — revolve body + coronet of points + monde [verified]
```python
with BuildPart() as body:
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Polyline((0, 0), (15, 0), (15, 3))
            Spline((15, 3), (7, 14), (8, 50), tangents=((-0.3, 1), (0, 1)))
            Line((8, 50), (10, 56)); Line((10, 56), (0, 56)); Line((0, 56), (0, 0))
        make_face()
    revolve(axis=Axis.Z)
spike = Pos(0, 0, 60) * Cone(bottom_radius=1.8, top_radius=0.4, height=8)
result = body.part + PolarLocations(radius=8, count=9) * spike + Pos(0, 0, 70) * Sphere(3)
```
Keep spikes thick enough not to snap; chamfer the tips.

### King — revolve body + cross patée [verified]
```python
with BuildPart() as body:
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Polyline((0, 0), (16, 0), (16, 3))
            Spline((16, 3), (7, 16), (8, 70), tangents=((-0.3, 1), (0, 1)))
            Line((8, 70), (11, 76)); Line((11, 76), (0, 76)); Line((0, 76), (0, 0))
        make_face()
    revolve(axis=Axis.Z)
result = body.part + Pos(0, 0, 88) * Box(3.5, 3.5, 18) + Pos(0, 0, 90) * Box(3.5, 12, 3.5)
```
Thicken the cross arms to the min wall and chamfer the ends — the cross is the
classic ship-failure point.

### Knight — THE INTEGRATED HEAD (this is make-or-break) [verified]
A knight lives or dies on the head. The cardinal sin is a vertical neck-cylinder with
a horizontal cone/pipe muzzle stuck on the side and two bare cones for ears — that
reads as junkyard plumbing, not a horse. Build the head as ONE coherent mass that
**arches forward and dips DOWN** into a tapered muzzle (muzzle at the front-bottom,
poll up-back), fused into the neck. The recipe below produces a real equine head:
```python
# CURVED ogee base (revolve a profile) -- real knights flow, they aren't straight cylinders
with BuildPart() as base:
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Polyline((0,0),(16,0),(16,3))
            Spline((16,3),(11,7),(12.5,11),tangents=((-0.6,1),(0.2,1)))   # cove flare
            Line((12.5,11),(0,11)); Line((0,11),(0,0))
        make_face()
    revolve(axis=Axis.Z)
result = base.part
with BuildPart() as neck:
    for z,cx,(a,b) in [(11,0,(9,8)),(20,1,(8.6,8)),(29,3,(8,8.2)),(37,4.5,(7.8,8.6)),(42,5,(7.5,8.8))]:
        with BuildSketch(Plane.XY.offset(z)):
            with Locations((cx,0)): Ellipse(a,b)
    loft()
# HEAD: make it EQUINE, not canine -- a LONG face with a near-straight nose bridge
# (gentle dip), narrowing to a SMALL muzzle far forward (x~35). A short, steeply-dipping
# muzzle reads as a dog snout; keep it long and shallow.
with BuildPart() as head:
    for x,zc,(a,b) in [(-3,43,(11,8.5)),(6,44,(10,8)),(15,41,(8,6.8)),(23,38,(6,5.2)),(30,35,(4.6,4.2)),(35,33,(3.6,3.4))]:
        with BuildSketch(Plane.YZ.offset(x)):
            with Locations((0,zc)): Ellipse(b,a)
    loft()
result += neck.part + head.part
result += Pos(3,0,33)*scale(Sphere(7), by=(1.2,1.0,0.9))        # big JAW at the back-bottom
result -= Pos(31,0,32)*Rot(0,12,0)*Box(9,7,1.0)                 # lip line at the muzzle
result -= Pos(33,1.7,34)*Sphere(0.9); result -= Pos(33,-1.7,34)*Sphere(0.9)  # nostrils
# SMALL ALMOND eyes on the SIDE (a big round recessed lens reads as a drone -- avoid it):
for sy in (1,-1):
    result -= Pos(9,sy*7.2,42)*Rot(0,0,sy*-18)*scale(Sphere(1.7), by=(1.6,0.4,0.9))
    result += Pos(9.5,sy*7.3,42)*Sphere(0.8)
def ear(sy):                                                   # upright ears at the poll
    return Pos(-2,sy*4,47)*Rot(sy*-10,-6,0)*scale(Cone(bottom_radius=2.6,top_radius=0.3,height=10),by=(0.45,1,1))
result += ear(1)+ear(-1)
# MANE lying ALONG the crest (hugs the neck; never a thin ribbon that hooks off the back):
with BuildPart() as mane:
    with BuildLine(): Spline((-4,0,47),(-6,0,38),(-6,0,28),(-4,0,18),tangents=((0.2,0,-1),(0.3,0,-1)))
    with BuildSketch(Plane.YZ): Ellipse(3.4,2.2)
    sweep()
mm = mane.part
for i in range(6): mm -= Pos(-6,0,20+i*4.5)*Rot(0,12,0)*Box(2.0,9,0.9)
result += mm
try: result = fillet(result.edges().group_by(Axis.Z)[0],radius=1.0)
except Exception: pass
```
This reads as a horse, not a dog or a drone. The three tells to avoid: a SHORT
steeply-dipping muzzle (dog), a BIG round recessed eye-lens (drone), and a thin mane
ribbon that hooks off the back. Long shallow face + small almond side-eyes + a mane
that hugs the crest fixes all three. **Horns/antlers for non-horse themes must seat
their base INTO the poll (overlap z~44-47), not float above the head.**
**Vary the head per theme** — don't ship the identical head on every piece. Shift the
proportions, the eye size/shape, the muzzle length, the ear/horn style, and the
surface to suit the theme (a dragon snout is longer with a heavy brow; a minimalist
head is smoother with smaller features; a cute theme has big round eyes).
Elevate from there: more head sections for a finer equine curve; a swept mane of locks
down the crest (a ribbon + groove cuts, NEVER a cluster of spheres); a brow ridge and
recessed eye sockets; a global light fillet so seams read as carved. Then apply the
theme (erosion / scales / panels / etc.) over this solid head — never instead of it.
Reinforce the neck (load-bearing, #1 ship-failure point).

---

## 5b. Aesthetics: what reads as good vs amateurish (human-reviewed)

These are distilled from real human design review. They are the difference between
"a 4/10 that looks like primitives stitched together" and "an 8/10 that reads as the
thing." Apply them to EVERY piece.

**The head (fixes the most common failure):**
- Muzzle/mouth = a sculpted front-of-head with a mouth-line groove + recessed nostrils.
  NEVER a sphere stuck on a cylinder ("balls and cylinders"), never a horizontal pipe.
- Ears/horns = flattened, curved, shaped forms fused into the head with real overlap.
  NEVER bare naked cones; never floating or only point-touching the head.
- The head is one integrated mass (forehead→jaw→muzzle) leaning forward-and-DOWN.

**Detail & theme (don't be basic):**
- Simplify from REAL references (use the reference images), don't invent from primitives.
  Enumerate the theme's signature features and actually carve them: a dragon has
  overlapping shingle-scales + snout + swept horns + spinal ridge; cyberpunk has a
  thick carved jetpack + antenna + recessed screen-glass eyes + wheels/vents; gothic
  has clustered pinnacles + crockets + finials + pointed lancet windows.
- Make detail SUBSTANTIAL and deep enough to read at piece size — timid, shallow, or
  uniform texture (a faint speckle, neat rings of bumps) looks like noise.
- Integrate texture across the WHOLE form (head, body, base) as one language, not an
  isolated band on the shaft.
- The base is a design opportunity that carries the theme (gear/wheels, broken column,
  hex boss…) — not a default cylinder/disc.

**Material read:**
- Marble/stone stays SMOOTH; peppering it with pits makes it look like corroded/cast
  metal. Weather it with one clean broken face + a few edge chips, not all-over pitting.

**Structure (also ship-safety):**
- Every added mass must overlap and truly fuse — no floating, no kissing-at-a-point.
  A detached ear is both ugly and a guaranteed print/ship failure. Props (sword,
  antenna, spire) must be THICK enough not to snap, or be a separate detachable part —
  a wire-thin sword reads bad and breaks.

**Themes reinterpret the FORM, not just the surface (the most important one):**
- A theme is not a texture you spray on a fixed knight. Let it distort the whole
  silhouette — the base shape, the body proportions, the head — by an amount
  proportional to how different the theme is, and add theme props.
- Mild themes (marble, art-deco): keep the horse-head knight, vary base + surface +
  ornament. Strong character themes: REINTERPRET the body. Example — a "Kirby knight"
  is not a horse head with pink texture; it's Kirby's round body + big round eyes +
  little feet, given a knight read with a swept mane down the back, ear-tufts, and a
  (thick) sword & shield. The piece should still read as a knight, but its form is
  reimagined around the character.
- Always pull reference images of BOTH the theme subject and real Staunton knights,
  and design the simplification from them — curved flowing base/neck, clear animal
  face (eyes/brow/mouth), theme-specific body and props.

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
