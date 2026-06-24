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
from .providers import ProviderConfig, build_model


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
        model_settings={"max_tokens": 16384},
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
        model_settings={"max_tokens": 16384},
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
