#!/usr/bin/env python3
"""CDK app entrypoint.

Deploy with (from the repo root, infra extra installed):

    uv sync --extra infra
    cd infra
    cdk bootstrap        # first time per account/region
    cdk deploy

Environment knobs (optional):
    DELIVERY_SENDER   verified SES sender address (defaults to cad@garrychess.ai)
    BEDROCK_MODEL_ID  Bedrock model id for generation
"""

import os

import aws_cdk as cdk
from stacks.api_stack import ChessStepApiStack

app = cdk.App()

ChessStepApiStack(
    app,
    "ChessStepApiStack",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
    delivery_sender=os.environ.get("DELIVERY_SENDER", "cad@garrychess.ai"),
    bedrock_model_id=os.environ.get(
        "BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-8-v1:0"
    ),
)

app.synth()
