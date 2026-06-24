#!/usr/bin/env python3
"""CDK app entrypoint.

Deploy with (from the repo root, infra extra installed):

    uv sync --extra infra
    cd infra
    cdk bootstrap        # first time per account/region
    cdk deploy

Every resource is tagged/named with the app id "cadgen" so this stack's resources
are easy to tell apart from anything else in the account.

Environment knobs (optional):
    DELIVERY_SENDER   verified SES sender address (defaults to cad@garrychess.ai)
    BEDROCK_MODEL_ID  Bedrock model id for generation
    CDK_DEFAULT_REGION / AWS_REGION   deploy region (defaults to us-east-2)
"""

import os

import aws_cdk as cdk
from stacks.api_stack import ChessStepApiStack

# Shared app identity for naming + tagging.
APP_ID = "cadgen"
STACK_NAME = "CadgenChessStepStack"

app = cdk.App()

stack = ChessStepApiStack(
    app,
    STACK_NAME,
    app_id=APP_ID,
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION")
        or os.environ.get("AWS_REGION", "us-east-2"),
    ),
    delivery_sender=os.environ.get("DELIVERY_SENDER", "cad@garrychess.ai"),
    bedrock_model_id=os.environ.get(
        "BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-8-v1:0"
    ),
)

# Tag every resource in the app so they're filterable in the console / billing.
cdk.Tags.of(app).add("app", APP_ID)
cdk.Tags.of(app).add("appId", APP_ID)
cdk.Tags.of(app).add("component", "chess-step-generator")

app.synth()
