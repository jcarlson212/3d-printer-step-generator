"""API Gateway -> container Lambda -> Bedrock, with SES delivery.

The Lambda is a container image because STEP export needs build123d/OpenCascade,
which is far too large for a zip/layer. It calls Bedrock to generate the CAD code,
executes it to a STEP file in /tmp, and emails the result via SES.

NOTE on timeouts: API Gateway has a hard 29s integration timeout. A full
generation (LLM + CAD kernel) can exceed that. For the first cut the route is
synchronous and best-effort; for production, switch to async invocation
(API GW -> SQS/Lambda async, or Step Functions) and return a 202 + order id.
"""

from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
)
from aws_cdk import (
    aws_apigateway as apigw,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as _lambda,
)
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[2]


class ChessStepApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        delivery_sender: str,
        bedrock_model_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Container Lambda built from infra/lambda/Dockerfile, with repo root as
        # build context so the printforge package can be copied in.
        fn = _lambda.DockerImageFunction(
            self,
            "GenerateFn",
            code=_lambda.DockerImageCode.from_image_asset(
                directory=str(REPO_ROOT),
                file="infra/lambda/Dockerfile",
            ),
            memory_size=3008,
            timeout=Duration.minutes(10),  # Lambda itself; API GW still caps at 29s
            environment={
                "USE_SES": "1",
                "DELIVERY_SENDER": delivery_sender,
                "BEDROCK_MODEL_ID": bedrock_model_id,
            },
        )

        # Permissions: invoke Bedrock models + send email via SES.
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=["*"],
            )
        )
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendRawEmail", "ses:SendEmail"],
                resources=["*"],
            )
        )

        # REST API with an API key + usage plan for basic protection.
        api = apigw.RestApi(
            self,
            "ChessStepApi",
            rest_api_name="chess-step-api",
            description="Generate 3D-printable chess piece STEP files via Bedrock.",
            deploy_options=apigw.StageOptions(stage_name="prod"),
        )
        generate = api.root.add_resource("generate")
        generate.add_method(
            "POST",
            apigw.LambdaIntegration(fn),
            api_key_required=True,
        )

        key = api.add_api_key("ChessStepApiKey")
        plan = api.add_usage_plan(
            "ChessStepUsagePlan",
            throttle=apigw.ThrottleSettings(rate_limit=5, burst_limit=10),
        )
        plan.add_api_key(key)
        plan.add_api_stage(stage=api.deployment_stage)

        CfnOutput(self, "ApiUrl", value=api.url_for_path("/generate"))
        CfnOutput(
            self,
            "ApiKeyId",
            value=key.key_id,
            description="Get value: aws apigateway get-api-key --api-key <id> --include-value",
        )
