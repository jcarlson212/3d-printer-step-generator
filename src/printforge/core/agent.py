"""The CAD-generation agent.

Wraps a pydantic-ai ``Agent`` with structured output so every step reliably
returns CAD code plus a thorough explanation -- no markdown parsing, the model is
forced to fill the schema and retries on mismatch.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from .profiles import MachineProfile, MaterialProfile
from .prompt import BasePieceTemplate, PriorPieceContext, TargetDimensions
from .providers import ProviderConfig, build_model, caching_model_settings


class CadGeneration(BaseModel):
    """Structured result of one generation step."""

    cad_code: str = Field(
        description="Complete build123d Python code assigning the final solid to `result`."
    )
    detailed_explanation: str = Field(
        description="Thorough rationale: form decisions, exact parameters, how each "
        "printability gotcha was handled, and guidance for set consistency."
    )


def generate_piece(
    template: BasePieceTemplate,
    *,
    provider_cfg: ProviderConfig,
    machine: MachineProfile,
    material: MaterialProfile,
    color: str,
    theme: str | None,
    target: TargetDimensions,
    gotchas: list[str],
    prior: list[PriorPieceContext] | None = None,
    personalization: list[str] | None = None,
    reference_images: list[bytes] | None = None,
) -> CadGeneration:
    """Run one generation step and return structured CAD + explanation.

    If ``reference_images`` are supplied (e.g. rendered views of reference STLs)
    they are sent alongside the text prompt for vision-capable models.
    """
    model = build_model(provider_cfg)
    agent = Agent(
        model,
        output_type=CadGeneration,
        system_prompt=template.system_prompt(),
        # CAD code + a thorough explanation is long; give the model room so the
        # output isn't truncated before `detailed_explanation`, and allow a few
        # re-tries if the structured output comes back incomplete.
        model_settings=caching_model_settings(provider_cfg),
        retries=3,
    )
    user_prompt = template.user_prompt(
        machine=machine,
        material=material,
        color=color,
        theme=theme,
        target=target,
        gotchas=gotchas,
        prior=prior,
        personalization=personalization,
    )

    prompt_input: list[object] = [user_prompt]
    if reference_images:
        from pydantic_ai import BinaryContent

        prompt_input.append(
            "Reference images of existing physical knight pieces (for silhouette / "
            "proportion / styling inspiration -- do not copy exactly):"
        )
        for img in reference_images:
            prompt_input.append(BinaryContent(data=img, media_type="image/png"))

    result = agent.run_sync(prompt_input if reference_images else user_prompt)
    return result.output


def revise_piece(
    template: BasePieceTemplate,
    *,
    provider_cfg: ProviderConfig,
    prev_code: str,
    observation: str,
    executed: bool,
    original_brief: str | None = None,
    reference_images: list[bytes] | None = None,
) -> CadGeneration:
    """Revise CAD code given an observation (a runtime error and/or geometry checks).

    This is the "reflect + act again" step of the build loop. ``executed`` is False
    when the code raised (fix the bug) and True when it ran but failed checks
    (improve the geometry). ``original_brief`` is the full original task (theme,
    styling, gotchas) -- passed every iteration so revisions never drift away from
    the aesthetic while chasing a passing geometry.
    """
    model = build_model(provider_cfg)
    agent = Agent(
        model,
        output_type=CadGeneration,
        system_prompt=template.system_prompt(),
        model_settings=caching_model_settings(provider_cfg),
        retries=3,
    )
    if executed:
        header = (
            "Your previous code ran and exported a solid, but it failed these validation "
            "checks. Revise the code to satisfy them while preserving the design intent."
        )
    else:
        header = (
            "Your previous code failed to execute. Fix the error while preserving the "
            "design intent. Common cause: using a BuildLine-only object "
            "(Polyline/Line/Spline/Bezier) outside a `with BuildLine()` block, or mixing "
            "the builder and algebra APIs."
        )
    brief_block = (
        f"--- ORIGINAL BRIEF (keep honoring this, especially the theme/styling) ---\n"
        f"{original_brief}\n\n"
        if original_brief
        else ""
    )
    prompt = (
        f"{header}\n\n"
        f"{brief_block}"
        f"--- PREVIOUS CODE ---\n{prev_code}\n\n"
        f"--- OBSERVATION ---\n{observation}\n\n"
        "Return the corrected, complete code (still assigning the final solid to "
        "`result`). Fix the problem above WITHOUT abandoning the theme and styling from "
        "the brief. Also return an updated detailed_explanation noting what changed."
    )
    if reference_images:
        from pydantic_ai import BinaryContent

        prompt_input: list[object] = [prompt, "Reference images (styling inspiration):"]
        for img in reference_images:
            prompt_input.append(BinaryContent(data=img, media_type="image/png"))
        return agent.run_sync(prompt_input).output
    return agent.run_sync(prompt).output


# A standing art-direction critique applied every refinement round. Targets the
# common ways LLM-generated CAD looks amateurish.
_REFINE_CRITIQUE = """\
Look critically at the rendered images of YOUR OWN current output above, then make it
markedly more sculptural and less basic. It is currently valid but likely too simple.
Elevate it -- raise the level of craft, do not just nudge it:
- Replace any primitive-looking stand-ins with real sculpted form. A mane must be
  flowing locks (sweep a ribbon down the crest and cut groove-locks), NEVER a cluster
  of spheres. Nostrils and eyes are SHALLOW RECESSED CUTS flush with the surface, never
  protruding balls. The nose is the smoothly blended END of the muzzle taper, not a
  stuck-on sphere.
- No free-floating or stuck-on primitives: every added mass must be blended/fused into
  the body so it reads as carved from one block; every sphere is either a smoothly
  merged mass or a recess cut INTO the surface.
- Give the silhouette real curvature and rhythm (ogee profiles, more loft sections),
  not a plain taper.
- If the theme is a ruin/antiquity, the base should read as a broken fluted column drum
  with an irregular fractured top -- not a clean cylinder.
- Add appropriate, restrained detail and finishing fillets so seams read as carved stone.
Treat the reference images and example recipes as ILLUSTRATIONS OF TECHNIQUES to
generalize -- compose your own richer structure; do not stitch the example shapes
together literally. Keep it ONE valid watertight solid, on-theme, and printable."""


def refine_piece(
    template: BasePieceTemplate,
    *,
    provider_cfg: ProviderConfig,
    prev_code: str,
    render_images: list[bytes],
    original_brief: str | None = None,
    round_num: int = 1,
    rounds_total: int = 1,
    reference_images: list[bytes] | None = None,
) -> CadGeneration:
    """Aesthetic refinement: show the model its rendered output and elevate the design.

    This runs AFTER the piece is geometrically valid -- the point is to spend
    iterations making it less basic/more sculptural, not to fix errors.
    """
    from pydantic_ai import BinaryContent

    model = build_model(provider_cfg)
    agent = Agent(
        model,
        output_type=CadGeneration,
        system_prompt=template.system_prompt(),
        model_settings=caching_model_settings(provider_cfg),
        retries=3,
    )
    brief_block = f"--- ORIGINAL BRIEF ---\n{original_brief}\n\n" if original_brief else ""
    text = (
        f"Refinement pass {round_num} of {rounds_total}.\n\n"
        f"{brief_block}"
        f"--- CURRENT CODE ---\n{prev_code}\n\n"
        f"{_REFINE_CRITIQUE}\n\n"
        "Return the improved, complete code (final solid assigned to `result`) and an "
        "updated detailed_explanation describing the specific improvements you made."
    )
    parts: list[object] = ["Rendered views of your current output:"]
    for img in render_images:
        parts.append(BinaryContent(data=img, media_type="image/png"))
    if reference_images:
        parts.append("Reference images (technique/proportion inspiration, do not copy):")
        for img in reference_images:
            parts.append(BinaryContent(data=img, media_type="image/png"))
    parts.append(text)
    return agent.run_sync(parts).output


class SafetyReport(BaseModel):
    """Verdict of the final packaging/durability QA gate."""

    ok: bool = Field(description="True if the piece is safe to print, pack, and ship as-is.")
    issues: list[str] = Field(
        default_factory=list,
        description="Concrete packaging/durability problems to fix (empty if ok).",
    )


def safety_review(
    template: BasePieceTemplate,
    *,
    provider_cfg: ProviderConfig,
    cad_code: str,
    render_images: list[bytes],
    material: MaterialProfile,
    machine: MachineProfile,
) -> SafetyReport:
    """Final QA: is the finished piece safe to print/pack/ship? Returns issues to fix."""
    from pydantic_ai import BinaryContent

    model = build_model(provider_cfg)
    agent = Agent(
        model,
        output_type=SafetyReport,
        system_prompt=(
            "You are a strict 3D-print packaging & durability QA reviewer. You judge "
            "whether a finished piece will survive printing, handling, and shipping."
        ),
        model_settings=caching_model_settings(provider_cfg),
        retries=3,
    )
    text = (
        f"Material: {material.name} ({material.polymer}) -- "
        f"min wall {material.min_wall_mm} mm; brittle if thin. Printer: {machine.name}, "
        f"min feature {machine.min_feature_mm} mm.\n\n"
        f"--- CODE ---\n{cad_code}\n\n"
        "Review the rendered piece and the code for SHIP SAFETY. Flag as issues:\n"
        "- Any part that is detached, floating, or only point/edge-touching (must be "
        "one fully-fused solid -- ears/horns/finials must share real volume with the body).\n"
        "- Thin fragile protrusions that will snap (spikes, antennae, thin manes, ears, "
        "cross/finial arms) unless they are thick enough for the material.\n"
        "- A neck or other load-bearing cross-section too thin for a top-heavy piece.\n"
        "- A base too narrow/unstable for the height (tipping/breakage risk).\n"
        "Set ok=false with concrete, actionable issues if ANY apply; ok=true only if it "
        "would reliably survive packing and shipping. These are durability guidelines, "
        "not rigid rules -- judge real risk."
    )
    parts: list[object] = ["Rendered views of the finished piece:"]
    for img in render_images:
        parts.append(BinaryContent(data=img, media_type="image/png"))
    parts.append(text)
    return agent.run_sync(parts).output
