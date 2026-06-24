"""Model-provider abstraction.

A single :class:`ProviderConfig` describes *where* to run inference. The same
workflow runs locally against Claude / OpenAI / an LM Studio server, or in the
cloud against Bedrock, just by swapping this config.

Credentials are read from the config if given, otherwise from the environment /
default credential chains -- nothing is hard-coded.
"""

from __future__ import annotations

import os
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from pydantic_ai.models import Model


class Provider(StrEnum):
    ANTHROPIC = "anthropic"  # Claude API
    OPENAI = "openai"  # OpenAI API
    LMSTUDIO = "lmstudio"  # local LM Studio server (OpenAI-compatible)
    BEDROCK = "bedrock"  # AWS Bedrock (used by the Lambda)


# Sensible default model per provider. Override via ProviderConfig.model.
DEFAULT_MODELS: dict[Provider, str] = {
    Provider.ANTHROPIC: "claude-opus-4-8",
    Provider.OPENAI: "gpt-4.1",
    Provider.LMSTUDIO: "local-model",
    # Global cross-region inference profile (matches the account's 30M tok/min quota).
    Provider.BEDROCK: "global.anthropic.claude-opus-4-8",
}


class ProviderConfig(BaseModel):
    """How and where to run the model for a workflow."""

    provider: Provider = Provider.ANTHROPIC
    model: str | None = Field(
        default=None, description="Model id; defaults per-provider if omitted."
    )

    # Credentials / endpoints (all optional; fall back to env / default chains).
    api_key: str | None = None
    base_url: str | None = Field(
        default=None,
        description="Override endpoint. For LM Studio, defaults to http://localhost:1234/v1.",
    )
    aws_region: str | None = None

    @model_validator(mode="after")
    def _fill_defaults(self) -> ProviderConfig:
        if self.model is None:
            self.model = DEFAULT_MODELS[self.provider]
        if self.provider is Provider.LMSTUDIO and not self.base_url:
            self.base_url = os.environ.get(
                "LMSTUDIO_BASE_URL", "http://localhost:1234/v1"
            )
        return self


def caching_model_settings(cfg: ProviderConfig, *, max_tokens: int = 16384) -> dict:
    """Model settings with prompt caching enabled for the provider.

    The large, stable system prompt (CAD masterclass + rules + reference docs) is the
    same on every generate/revise call and across pieces, so caching it as the prefix
    is a big win. Anthropic and Bedrock support manual cache breakpoints; OpenAI caches
    automatically; LM Studio has no caching.
    """
    settings: dict = {"max_tokens": max_tokens}
    if cfg.provider is Provider.ANTHROPIC:
        settings["anthropic_cache_instructions"] = True
        settings["anthropic_cache_messages"] = True
    elif cfg.provider is Provider.BEDROCK:
        settings["bedrock_cache_instructions"] = True
        settings["bedrock_cache_messages"] = True
    return settings


def build_model(cfg: ProviderConfig) -> Model:
    """Construct a pydantic-ai ``Model`` from a :class:`ProviderConfig`."""
    if cfg.provider is Provider.ANTHROPIC:
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key=cfg.api_key) if cfg.api_key else "anthropic"
        return AnthropicModel(cfg.model, provider=provider)  # type: ignore[arg-type]

    if cfg.provider in (Provider.OPENAI, Provider.LMSTUDIO):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        # LM Studio doesn't require a real key, but the OpenAI client demands one.
        api_key = cfg.api_key or ("lm-studio" if cfg.provider is Provider.LMSTUDIO else None)
        if cfg.base_url or api_key:
            provider = OpenAIProvider(base_url=cfg.base_url, api_key=api_key)
            return OpenAIChatModel(cfg.model, provider=provider)  # type: ignore[arg-type]
        return OpenAIChatModel(cfg.model)  # type: ignore[arg-type]

    if cfg.provider is Provider.BEDROCK:
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        region = cfg.aws_region or os.environ.get("AWS_REGION", "us-east-2")
        provider = BedrockProvider(region_name=region)
        return BedrockConverseModel(cfg.model, provider=provider)  # type: ignore[arg-type]

    raise ValueError(f"Unsupported provider: {cfg.provider}")
