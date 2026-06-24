"""Render reference STL meshes to PNG images for vision-capable models.

A text LLM can't read a binary STL, but it can look at a picture of one. This
renders a handful of angled views of each reference mesh to PNGs (headless, via
matplotlib's Agg backend) so they can be attached to the generation prompt.

Requires the optional ``vision`` extra (numpy-stl + matplotlib). If it's not
installed, :func:`render_references` returns an empty list and the workflow simply
proceeds text-only.
"""

from __future__ import annotations

import io
from pathlib import Path

# Default camera angles (elevation, azimuth) -- a front-ish and a 3/4 view.
_VIEWS: tuple[tuple[int, int], ...] = ((20, -60), (20, 60))


def vision_available() -> bool:
    try:
        import matplotlib  # noqa: F401
        import stl  # noqa: F401  (numpy-stl)

        return True
    except Exception:
        return False


def _render_one(stl_path: Path, views: tuple[tuple[int, int], ...]) -> list[bytes]:
    import matplotlib

    matplotlib.use("Agg")  # headless
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from stl import mesh as stl_mesh

    m = stl_mesh.Mesh.from_file(str(stl_path))
    out: list[bytes] = []
    for elev, azim in views:
        fig = plt.figure(figsize=(4, 4))
        ax = fig.add_subplot(111, projection="3d")
        ax.add_collection3d(Poly3DCollection(m.vectors, color="lightgray", edgecolor="none"))
        # Scale axes to the mesh bounds so it fills the frame.
        pts = m.vectors.reshape(-1, 3)
        mins, maxs = pts.min(axis=0), pts.max(axis=0)
        ctr = (mins + maxs) / 2
        span = float((maxs - mins).max()) / 2 or 1.0
        ax.set_xlim(ctr[0] - span, ctr[0] + span)
        ax.set_ylim(ctr[1] - span, ctr[1] + span)
        ax.set_zlim(ctr[2] - span, ctr[2] + span)
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=90, bbox_inches="tight")
        plt.close(fig)
        out.append(buf.getvalue())
    return out


def render_references(
    *,
    stl_dir: str | Path | None = None,
    image_paths: list[str] | None = None,
    max_images: int = 4,
    views: tuple[tuple[int, int], ...] = _VIEWS,
) -> list[bytes]:
    """Return PNG bytes for reference images: pre-rendered files first, then STLs."""
    images: list[bytes] = []

    for p in image_paths or []:
        path = Path(p)
        if path.exists():
            images.append(path.read_bytes())
            if len(images) >= max_images:
                return images[:max_images]

    if stl_dir and vision_available():
        stls = sorted(Path(stl_dir).glob("*.stl"))
        for stl_path in stls:
            try:
                for png in _render_one(stl_path, views):
                    images.append(png)
                    if len(images) >= max_images:
                        return images[:max_images]
            except Exception:
                # A bad/huge mesh shouldn't kill the run; skip it.
                continue

    return images[:max_images]
