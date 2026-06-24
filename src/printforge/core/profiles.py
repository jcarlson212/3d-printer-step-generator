"""Machine and material profiles.

These describe the *physical* constraints a generated model has to respect so the
LLM produces printable geometry. Everything here is a plain pydantic model, so a
request can override any field (see :mod:`printforge.core.overrides`).

Add a new printer or filament by appending a profile to the registry in
:mod:`printforge.core.registry` -- no other code needs to change.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BuildVolume(BaseModel):
    """Usable build volume in millimetres."""

    x_mm: float
    y_mm: float
    z_mm: float

    def fits(self, x: float, y: float, z: float) -> bool:
        return x <= self.x_mm and y <= self.y_mm and z <= self.z_mm


class MaterialProfile(BaseModel):
    """A filament + its print characteristics and printing gotchas.

    The ``gotchas`` are surfaced to the model as material-level constraints and are
    merged with machine-level and piece-level gotchas at prompt-build time.
    """

    key: str = Field(description="Stable identifier, e.g. 'bambu_pla_basic'.")
    name: str
    vendor: str | None = None
    polymer: str = Field(description="Base polymer, e.g. 'PLA'.")

    nozzle_temp_c: int
    bed_temp_c: int
    recommended_layer_height_mm: float = 0.2

    # Geometry-shaping constraints the model should design around.
    max_unsupported_overhang_deg: float = Field(
        45.0, description="Overhangs steeper than this from vertical need supports."
    )
    max_bridge_mm: float = Field(10.0, description="Longest reliable unsupported bridge.")
    min_wall_mm: float = Field(0.8, description="Thinnest reliable vertical wall.")
    shrinkage_pct: float = Field(0.3, description="Approx linear shrinkage on cooling.")

    gotchas: list[str] = Field(default_factory=list)


class MachineProfile(BaseModel):
    """A printer and the materials it can run.

    ``supported_material_keys`` references :class:`MaterialProfile` keys available
    for this machine; ``default_material_key`` is used when a request doesn't pick
    one. Both the chosen material and any field on it/here are request-overridable.
    """

    key: str = Field(description="Stable identifier, e.g. 'bambu_a1_mini'.")
    name: str
    vendor: str | None = None

    build_volume: BuildVolume
    nozzle_diameter_mm: float = 0.4
    min_feature_mm: float = Field(
        0.8, description="Smallest detail that survives at this nozzle size."
    )

    supported_material_keys: list[str]
    default_material_key: str

    gotchas: list[str] = Field(default_factory=list)
