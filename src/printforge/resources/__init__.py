"""Packaged reference documents + a loader to inject them into prompts.

These distilled docs give the generation model durable, on-topic knowledge
(build123d API, STEP/STL background, FDM/PLA limits, how to model a knight)
without paying for full external docs every call. See ``SOURCES.md`` for the
authoritative upstream links.

Templates pick which docs to include via ``resource_keys`` (see
:class:`printforge.core.prompt.BasePieceTemplate`).
"""

from __future__ import annotations

from importlib.resources import files

# Stable key -> filename. Add a doc here to make it injectable.
RESOURCES: dict[str, str] = {
    "build123d": "build123d_cheatsheet.md",
    "step_stl": "step_stl_primer.md",
    "fdm_pla": "fdm_pla_constraints.md",
    "knight_guide": "staunton_knight_guide.md",
    # The in-depth CAD craft reference: how to sculpt beautiful, intricate chess
    # pieces in build123d. Injected into every chess piece prompt.
    "cad_masterclass": "cad_chess_masterclass.md",
}


def load_resource(key: str) -> str:
    """Return the text of a packaged resource by key."""
    try:
        filename = RESOURCES[key]
    except KeyError:
        raise KeyError(f"Unknown resource '{key}'. Known: {sorted(RESOURCES)}") from None
    return files(__package__).joinpath(filename).read_text(encoding="utf-8")


def knowledge_pack(keys: list[str]) -> str:
    """Concatenate the given resources into one prompt-ready reference block."""
    parts: list[str] = []
    for key in keys:
        parts.append(f"<<< REFERENCE: {key} >>>")
        parts.append(load_resource(key).strip())
        parts.append("")
    return "\n".join(parts).strip()
