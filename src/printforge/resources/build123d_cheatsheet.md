# build123d cheat-sheet (for the CAD-generation model)

build123d is a Python B-rep CAD library on the OpenCascade kernel. Prefer the
**algebra (operator) API** shown here -- it is concise and composes cleanly.

Assume `from build123d import *` is already done. Assign the final solid to `result`.

## Primitives (3D)
All are centred at the origin by default; move with `Pos`.
```python
Box(length, width, height)
Cylinder(radius, height)
Sphere(radius)
Cone(bottom_radius, top_radius, height)
Torus(major_radius, minor_radius)
```

## Placement & transforms
```python
Pos(x, y, z) * shape          # translate
Rot(x_deg, y_deg, z_deg) * shape   # rotate
(Pos(0,0,10) * Rot(0,90,0)) * shape
```

## Booleans (algebra API)
```python
a + b      # fuse / union
a - b      # cut / subtract
a & b      # intersect
```

## Profiles -> solids (for organic / swept forms)
```python
# Sketch a 2D face on a plane, then extrude or revolve.
with BuildPart() as p:
    with BuildSketch(Plane.XZ) as s:
        # build a closed outline, e.g. with Polyline/Spline + make_face()
        ...
    revolve(axis=Axis.Z)        # lathe a profile (good for pawns/rooks bodies)
result = p.part

# Loft between stacked sketches for a tapering/curving neck:
with BuildPart() as p:
    with BuildSketch(Plane.XY) as s1: Circle(9)
    with BuildSketch(Plane.XY.offset(26)) as s2: Circle(7)
    loft()
result = p.part
```

## Fillets & chamfers (soften edges, reduce stress risers)
```python
result = fillet(result.edges().group_by(Axis.Z)[0], radius=1.0)   # bottom rim
result = chamfer(result.edges().filter_by(GeomType.LINE), length=0.5)
```
Edge selection can fail if no matching edges exist -- wrap risky selections in
try/except so a missing fillet never aborts the whole model.

## Inscriptions / engraving
```python
with BuildSketch(Plane.XY.offset(z)) as t:
    Text("GC", font_size=4)
engrave = extrude(t.sketch, amount=-0.6)   # recess into the base
result = result - engrave
```

## Export (the executor does this; do NOT call it yourself unless asked)
```python
export_step(result, "out.step")
```

## Common mistakes to avoid
- `Polyline`, `Line`, `Spline`, `Bezier`, `RadiusArc` are **BuildLine** objects. Use
  them only inside `with BuildLine() as l:` -- never directly in a `BuildSketch`.
  To make a face from an outline: build the line in `BuildLine`, then
  `make_face()` inside `BuildSketch`.
- Don't mix the builder API (`with BuildPart()`) and the algebra API (`+`/`-` on
  objects) in the same expression. Pick one approach per solid.
- `loft()` / `revolve()` / `extrude()` are operations that need an active
  `BuildPart`/`BuildSketch` context (builder API).
- Every sketch outline must be **closed** before `make_face()`.

## Rules of thumb
- One connected, watertight, manifold solid bound to `result`.
- Name dimensions as variables at the top so the piece is rescalable.
- Flat base on the build plate; avoid disconnected or zero-thickness geometry.
- Keep features above the printer's min-feature size.
