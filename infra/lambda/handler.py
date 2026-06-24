"""Lambda handler: API Gateway -> Bedrock generation -> STEP -> SES email.

Request body is a ChessWorkflowRequest JSON (same schema the local CLI uses). The
provider is forced to Bedrock regardless of what the body says, and delivery goes
out via SES. STEP files are written to /tmp (the only writable Lambda path).
"""

from __future__ import annotations

import json
import os

from printforge.core.providers import Provider, ProviderConfig
from printforge.workflows.chess.engine import run_chess_workflow
from printforge.workflows.chess.models import ChessWorkflowRequest


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event: dict, context: object) -> dict:  # noqa: ARG001
    try:
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            import base64

            raw = base64.b64decode(raw).decode("utf-8")
        data = json.loads(raw)
    except (ValueError, TypeError) as e:
        return _response(400, {"error": f"invalid JSON body: {e}"})

    # Force Bedrock provider in the cloud (ignore any provider in the request).
    data["provider"] = ProviderConfig(
        provider=Provider.BEDROCK,
        model=os.environ.get("BEDROCK_MODEL_ID"),
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
    ).model_dump(mode="json")

    try:
        request = ChessWorkflowRequest.model_validate(data)
    except Exception as e:
        return _response(422, {"error": "request validation failed", "detail": str(e)})

    try:
        result = run_chess_workflow(request, out_dir="/tmp/out", send_email=True)
    except Exception as e:  # generation/CAD/delivery failure
        return _response(
            500,
            {
                "error": "generation failed",
                "detail": str(e),
                "order_id": request.order.order_id,
            },
        )

    return _response(
        200,
        {
            "order_id": result.order_id,
            "ok": result.ok,
            "delivery": result.delivery_detail,
            "pieces": [
                {
                    "color": a.color.value,
                    "piece": a.piece.value,
                    "step": a.step_filename,
                    "error": a.error,
                }
                for a in result.artifacts
            ],
        },
    )
