# STEP vs STL: what they are and why we generate STEP

## STL (mesh)
- A surface **triangle mesh**: a list of triangles (facets) approximating the
  surface. No notion of curves, faces, or solids -- just points and triangles.
- Lossy for curves (a cylinder becomes many flat strips), resolution baked in.
- Ubiquitous as the slicer input for FDM printing.

## STEP (B-rep, ISO 10303 / AP203/AP214/AP242)
- A **boundary representation**: exact analytic geometry (planes, cylinders,
  NURBS surfaces) bounded into faces, shells, and solids with real topology.
- Parametric-friendly, editable in CAD, scales without quality loss.
- Text file beginning with `ISO-10303-21;` then `HEADER;` and `DATA;` sections.

## Why this project produces STEP from CAD code (not hand-written STEP)
A language model cannot reliably hand-write valid STEP -- the topology
(`CARTESIAN_POINT`, `EDGE_CURVE`, `ADVANCED_FACE`, `MANIFOLD_SOLID_BREP`, ...)
must be internally consistent or the file is rejected. Instead the model writes
parametric **build123d code**, and the OpenCascade kernel emits the STEP. The
geometry is therefore guaranteed well-formed by construction.

## Practical flow
```
LLM -> build123d Python -> (OpenCascade) -> STEP  -> slicer (-> STL/G-code) -> print
```
STEP is the durable master artifact; a slicer can mesh it to STL on demand.
