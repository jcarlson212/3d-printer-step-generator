"""Request/result models for the chess-piece workflow."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from printforge.core.delivery import DeliveryConfig
from printforge.core.order import OrderInfo
from printforge.core.prompt import TargetDimensions
from printforge.core.providers import ProviderConfig
from printforge.core.registry import resolve_machine_material

from .pieces import STANDARD_SIZE_MM, Color, PieceType
from .templates import ENABLED_PIECES, get_template


class PieceDimensions(BaseModel):
    """Optional dimension override. Missing fields fall back to standard Staunton."""

    height_mm: float | None = Field(default=None, gt=0)
    width_mm: float | None = Field(default=None, gt=0, description="Max base footprint.")
    depth_mm: float | None = Field(default=None, gt=0)


class ChessWorkflowRequest(BaseModel):
    """A single configurable run of the chess-piece workflow.

    Today the scope is constrained to the enabled pieces (knight only); the request
    shape already supports more colors/pieces for the future full-set workflow.
    """

    order: OrderInfo

    # Scope: which colors and which piece types to generate this run.
    colors: list[Color] = Field(min_length=1)
    pieces: list[PieceType] = Field(min_length=1)

    # Creative + physical configuration.
    theme: str | None = None
    dimensions: PieceDimensions | None = None

    # Machine / material (request-overridable; defaults to Bambu A1 mini + PLA Basic).
    machine_key: str | None = None
    material_key: str | None = Field(
        default=None, description="Primary print material; defaults to preferred_materials[0]."
    )
    preferred_materials: list[str] = Field(
        default_factory=lambda: ["bambu_pla_basic"],
        description="Customer-preferred materials, chosen from what the machine supports.",
    )

    # Per-piece gotcha overrides: {piece_slug: [gotcha, ...]} replaces code defaults.
    gotcha_overrides: dict[str, list[str]] = Field(default_factory=dict)

    # Vision: feed rendered views of reference STLs/images to a vision-capable model.
    use_vision: bool = False
    reference_stl_dir: str | None = Field(
        default=None, description="Directory of reference .stl files to render and show the model."
    )
    reference_images: list[str] = Field(
        default_factory=list, description="Paths to reference image files (png/jpg)."
    )
    max_reference_images: int = Field(default=4, ge=1, le=12)

    # Execution + delivery.
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    export_step: bool = Field(
        default=True, description="Run the CAD code to export a .step (needs the 'cad' extra)."
    )
    max_repairs: int = Field(
        default=2, ge=0, le=5,
        description="If STEP export fails, feed the error back to the model to fix its "
        "code and retry, up to this many times.",
    )

    @model_validator(mode="after")
    def _validate(self) -> ChessWorkflowRequest:
        # Scope must be within what's currently enabled.
        disabled = [p for p in self.pieces if p not in ENABLED_PIECES]
        if disabled:
            allowed = sorted(p.value for p in ENABLED_PIECES)
            raise ValueError(
                f"Pieces {[p.value for p in disabled]} are not enabled yet. "
                f"Currently runnable: {allowed}."
            )
        # Dedupe while preserving order.
        self.colors = list(dict.fromkeys(self.colors))
        self.pieces = list(dict.fromkeys(self.pieces))

        # Material selection defaults to the first preferred material.
        if not self.material_key and self.preferred_materials:
            self.material_key = self.preferred_materials[0]

        # Validate machine/material compatibility (raises with a clear message).
        machine, _ = resolve_machine_material(self.machine_key, self.material_key)
        unsupported = [
            m for m in self.preferred_materials if m not in machine.supported_material_keys
        ]
        if unsupported:
            raise ValueError(
                f"preferred_materials {unsupported} not supported on '{machine.key}' "
                f"(supported: {machine.supported_material_keys})."
            )
        return self

    def target_for(self, piece: PieceType) -> TargetDimensions:
        """Resolve target dimensions: request override wins, else standard Staunton."""
        std_h, std_w = STANDARD_SIZE_MM[piece]
        dims = self.dimensions
        return TargetDimensions(
            height_mm=(dims.height_mm if dims and dims.height_mm else std_h),
            max_footprint_mm=(dims.width_mm if dims and dims.width_mm else std_w),
        )

    def gotchas_for(self, piece: PieceType) -> list[str]:
        """Effective piece gotchas: request override wins, else template defaults."""
        template = get_template(piece)
        return template.effective_gotchas(self.gotcha_overrides.get(piece.value))

    def work_units(self) -> list[tuple[Color, PieceType]]:
        """All (color, piece) pairs to generate this run, in a stable order."""
        return [(c, p) for c in self.colors for p in self.pieces]


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #


class PieceArtifact(BaseModel):
    """The output of one workflow step (one color+piece)."""

    color: Color
    piece: PieceType
    cad_code: str
    detailed_explanation: str
    step_filename: str | None = None
    step_path: str | None = None
    step_bytes_len: int | None = None
    error: str | None = None
    stages: int = 0  # how many build-loop iterations this piece took
    warnings: list[str] = Field(default_factory=list)  # non-blocking check warnings


class WorkflowResult(BaseModel):
    order_id: str
    artifacts: list[PieceArtifact] = Field(default_factory=list)
    delivery_detail: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.artifacts) and all(a.error is None for a in self.artifacts)
