# FDM + PLA design constraints (Bambu A1 mini class)

Design the geometry so it prints well without fighting the process.

## Orientation & supports
- The model prints bottom-up in layers. A flat base on the plate needs no raft of
  supports under the whole piece -- keep one.
- Overhangs steeper than ~45deg from vertical sag or need supports. Supports leave
  scars on the faces they touch -- keep them off show surfaces.

## Bridges
- Unsupported horizontal spans ("bridges") print cleanly only up to ~10 mm and
  droop beyond that. Avoid long bridges; break them up or add a wall under them.

## Walls, features, text
- Minimum reliable wall ~0.8 mm at a 0.4 mm nozzle; finer detail won't resolve.
- Engraved text/recesses read better than raised text; keep strokes >= ~0.8 mm
  and depth ~0.4-0.6 mm.

## PLA specifics
- Stiff and brittle: thin long protrusions (spears, antennae, thin manes) snap in
  handling/shipping. Make them thick, or design them detachable.
- Sharp internal corners are stress risers -- add small fillets.
- Very fine points print rounded/stringy, not crisp.

## Stability (for tall pieces on a moving-bed printer)
- Keep a low centre of gravity and a base wide enough that the piece doesn't tip
  or ghost at speed. A slightly wider-than-spec base improves both printing and
  shipping survival.
