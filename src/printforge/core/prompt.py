"""Shared prompt-template base class.

``BasePieceTemplate`` is the inheritable contract every printable object uses to
ask the model for CAD code. It is *domain-agnostic* -- it knows how to assemble
machine constraints, material constraints, gotchas, a theme, target dimensions
and prior-step context into a prompt, and it pins the output contract (emit
build123d code that exports a STEP file).

Specific objects (a chess knight, a chess rook, ...) subclass it and supply the
form-specific ``design_brief`` and ``default_gotchas``. See
:mod:`printforge.workflows.chess.templates`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .profiles import MachineProfile, MaterialProfile

# The variable the executor reads the finished solid from. The model MUST assign
# its final part to this name. Keep in sync with executor.py.
RESULT_VAR = "result"


class TargetDimensions(BaseModel):
    """Default bounding target for a piece, in millimetres.

    STEP files are parametric/scalable, so this is guidance for proportion and
    printability rather than a hard contract; a request may override it.
    """

    height_mm: float
    max_footprint_mm: float = Field(
        description="Largest base diameter/width so the piece is stable and fits the plate."
    )


class PriorPieceContext(BaseModel):
    """A previously generated piece, fed forward into the next step's prompt."""

    slug: str
    color: str
    detailed_explanation: str
    cad_code: str | None = None
    step_filename: str | None = None


class BasePieceTemplate(BaseModel):
    """Inheritable prompt template for one printable object."""

    slug: str = Field(description="Stable id, e.g. 'knight'.")
    display_name: str
    design_brief: str = Field(
        description="Form/geometry guidance specific to this object (multi-line)."
    )
    default_gotchas: list[str] = Field(default_factory=list)
    default_target: TargetDimensions

    # ----------------------------------------------------------------- hooks --
    def cad_library(self) -> str:
        return "build123d"

    def effective_gotchas(self, override: list[str] | None) -> list[str]:
        """Piece-level gotchas: request override wins, else code defaults."""
        return list(override) if override is not None else list(self.default_gotchas)

    # --------------------------------------------------------------- prompts --
    def system_prompt(self) -> str:
        return (
            "You are a senior parametric-CAD engineer who writes clean, valid "
            f"{self.cad_library()} (Python) code for 3D printing.\n\n"
            "Hard rules:\n"
            f"1. Use the `{self.cad_library()}` library only. Assume `from build123d import *` "
            "is already done; do not re-import or define helpers you don't use.\n"
            f"2. Assign the final solid to a top-level variable named `{RESULT_VAR}`. "
            "It must be a single watertight, manifold solid (one connected body).\n"
            "3. The model is printed FDM, so design for it: a flat, stable base on the "
            "build plate; respect the overhang/bridge/wall limits given; no floating "
            "or disconnected geometry; no infinitely thin shells.\n"
            "4. Make geometry parametric where reasonable (named dimension variables at "
            "the top) so it can be rescaled later.\n"
            "5. Output is consumed by an automated executor. When asked for code, return "
            "ONLY the requested structured fields -- no markdown fences inside code.\n"
        )

    def user_prompt(
        self,
        *,
        machine: MachineProfile,
        material: MaterialProfile,
        color: str,
        theme: str | None,
        target: TargetDimensions,
        gotchas: list[str],
        prior: list[PriorPieceContext] | None = None,
    ) -> str:
        lines: list[str] = []
        lines.append(f"# Task: design a printable **{self.display_name}** ({color}).")
        lines.append("")
        lines.append("## Design brief")
        lines.append(self.design_brief.strip())
        if theme:
            lines.append("")
            lines.append("## Theme (lean into this -- it is the selling point)")
            lines.append(theme.strip())
        lines.append("")
        lines.append("## Target dimensions (parametric; proportion guidance)")
        lines.append(f"- Height: ~{target.height_mm} mm")
        lines.append(f"- Max base footprint: ~{target.max_footprint_mm} mm")
        lines.append("")
        lines.append(f"## Printer: {machine.name}")
        lines.append(
            f"- Build volume {machine.build_volume.x_mm}x{machine.build_volume.y_mm}"
            f"x{machine.build_volume.z_mm} mm; nozzle {machine.nozzle_diameter_mm} mm; "
            f"min feature ~{machine.min_feature_mm} mm."
        )
        for g in machine.gotchas:
            lines.append(f"- {g}")
        lines.append("")
        lines.append(f"## Material: {material.name} ({material.polymer})")
        lines.append(
            f"- Max unsupported overhang {material.max_unsupported_overhang_deg} deg "
            f"from vertical; max bridge {material.max_bridge_mm} mm; "
            f"min wall {material.min_wall_mm} mm."
        )
        for g in material.gotchas:
            lines.append(f"- {g}")
        lines.append("")
        lines.append(f"## {self.display_name}-specific printing gotchas")
        for g in gotchas:
            lines.append(f"- {g}")
        if prior:
            lines.append("")
            lines.append("## Earlier pieces in this set (for consistency)")
            lines.append(
                "Match the artistic language, base style, and scale conventions of "
                "these already-generated pieces:"
            )
            for p in prior:
                lines.append("")
                lines.append(f"### {p.color} {p.slug}")
                lines.append(p.detailed_explanation.strip())
        lines.append("")
        lines.append("## Deliverable")
        lines.append(
            f"Produce {self.cad_library()} code assigning the final solid to "
            f"`{RESULT_VAR}`, plus a thorough `detailed_explanation` covering the design "
            "decisions, exact parameters, how each printability gotcha was addressed, "
            "and any guidance the next piece should follow for set consistency."
        )
        return "\n".join(lines)
