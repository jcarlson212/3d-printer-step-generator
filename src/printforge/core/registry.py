"""Registry of known machines and materials.

This is the single place to register a new printer or filament. Profiles are
keyed so requests can refer to them by string (``machine="bambu_a1_mini"``).

The default target today is the **Bambu Lab A1 mini** running **Bambu PLA Basic**
("bamboo mini, PLA basic"), but the registry is intentionally open-ended.
"""

from __future__ import annotations

from .profiles import BuildVolume, MachineProfile, MaterialProfile

# --------------------------------------------------------------------------- #
# Materials
# --------------------------------------------------------------------------- #

BAMBU_PLA_BASIC = MaterialProfile(
    key="bambu_pla_basic",
    name="Bambu PLA Basic",
    vendor="Bambu Lab",
    polymer="PLA",
    nozzle_temp_c=220,
    bed_temp_c=55,
    recommended_layer_height_mm=0.2,
    max_unsupported_overhang_deg=45.0,
    max_bridge_mm=10.0,
    min_wall_mm=0.8,
    shrinkage_pct=0.3,
    gotchas=[
        "PLA is stiff and brittle: avoid thin, long, fragile protrusions that snap "
        "when removing supports or handling (e.g. a thin spear or a delicate mane tip).",
        "PLA bridges poorly over ~10mm and sags on steep overhangs >45deg from "
        "vertical; design these away or expect support scars.",
        "Sharp internal corners concentrate stress; add small fillets where possible.",
        "Heat creep: very fine points print stringy and rounded, not crisp.",
    ],
)

MATERIALS: dict[str, MaterialProfile] = {
    BAMBU_PLA_BASIC.key: BAMBU_PLA_BASIC,
}

# --------------------------------------------------------------------------- #
# Machines
# --------------------------------------------------------------------------- #

BAMBU_A1_MINI = MachineProfile(
    key="bambu_a1_mini",
    name="Bambu Lab A1 mini",
    vendor="Bambu Lab",
    build_volume=BuildVolume(x_mm=180, y_mm=180, z_mm=180),
    nozzle_diameter_mm=0.4,
    min_feature_mm=0.8,
    supported_material_keys=[BAMBU_PLA_BASIC.key],
    default_material_key=BAMBU_PLA_BASIC.key,
    gotchas=[
        "0.4mm nozzle: features finer than ~0.8mm will not resolve cleanly.",
        "Bed-slinger (Y-axis moving bed): tall, narrow, top-heavy models can wobble "
        "and ghost at speed; keep a stable base and a sensible height/width ratio.",
        "180x180x180mm build volume; a single chess piece is small, but a full set "
        "laid out on the plate must still fit.",
        "Auto-supports work, but minimise overhangs to reduce support scars on visible faces.",
    ],
)

MACHINES: dict[str, MachineProfile] = {
    BAMBU_A1_MINI.key: BAMBU_A1_MINI,
}

DEFAULT_MACHINE_KEY = BAMBU_A1_MINI.key


def get_machine(key: str) -> MachineProfile:
    try:
        return MACHINES[key]
    except KeyError:
        raise KeyError(
            f"Unknown machine '{key}'. Known machines: {sorted(MACHINES)}"
        ) from None


def get_material(key: str) -> MaterialProfile:
    try:
        return MATERIALS[key]
    except KeyError:
        raise KeyError(
            f"Unknown material '{key}'. Known materials: {sorted(MATERIALS)}"
        ) from None


def resolve_machine_material(
    machine_key: str | None = None,
    material_key: str | None = None,
) -> tuple[MachineProfile, MaterialProfile]:
    """Resolve a (machine, material) pair, applying defaults and validating compat."""
    machine = get_machine(machine_key or DEFAULT_MACHINE_KEY)
    chosen_material_key = material_key or machine.default_material_key
    if chosen_material_key not in machine.supported_material_keys:
        raise ValueError(
            f"Material '{chosen_material_key}' is not listed as supported on "
            f"'{machine.key}' (supported: {machine.supported_material_keys}). "
            "Override the machine's supported_material_keys to allow it."
        )
    return machine, get_material(chosen_material_key)
