# 3d-printer-step-generator (`printforge`)

Agentic workflows that turn a creative brief into a **3D-printable STEP file**.
The first workflow makes **chess pieces** (currently the **knight**, white or
black) targeting a **Bambu Lab A1 mini** printing **Bambu PLA Basic**.

An LLM (Claude / OpenAI / a local LM Studio server / AWS Bedrock) writes
parametric [`build123d`](https://build123d.readthedocs.io/) CAD code; we execute
that code in an isolated process to export a **guaranteed-valid STEP** (the model
never hand-writes STEP). The finished STEP file(s) plus a detailed design
explanation are emailed to the customer (default `cad@garrychess.ai`).

## How it works

```
request (order + scope + theme + machine/material)
        │
        ▼
workflow engine  ── for each (color, piece) in scope, one at a time ──┐
        │   feeds prior pieces' STEP + detailed_explanation forward    │
        ▼                                                              │
  generation agent (pydantic-ai, structured output)                   │
   • shared prompt template (BasePieceTemplate → ChessPieceTemplate    │
     → KnightTemplate) injects machine + material + per-piece gotchas  │
   • returns: build123d code + detailed_explanation                    │
        ▼                                                              │
  executor: run code in subprocess → export .step  ───────────────────┘
        ▼
  delivery: email STEP file(s) + concatenated explanations (SES / SMTP / save)
```

### Layout

```
src/printforge/
  core/
    profiles.py     # MachineProfile / MaterialProfile (physical constraints)
    registry.py     # registered machines + materials (Bambu A1 mini, PLA Basic)
    providers.py    # ProviderConfig + build_model (Claude/OpenAI/LMStudio/Bedrock)
    prompt.py       # BasePieceTemplate — inheritable shared prompt template
    order.py        # OrderInfo: validated customer/order fields
    agent.py        # pydantic-ai agent → {cad_code, detailed_explanation}
    executor.py     # run build123d code → STEP (isolated subprocess)
    delivery.py     # email the result (SES / SMTP / save-to-disk)
  workflows/chess/
    pieces.py       # Color / PieceType enums, standard Staunton sizing
    templates.py    # ChessPieceTemplate + per-piece templates (knight enabled)
    themes.py       # reusable themes (Parthenon knight)
    models.py       # ChessWorkflowRequest / results
    engine.py       # the workflow orchestrator
  cli/main.py       # interactive local CLI
infra/              # AWS CDK (Python): API Gateway → container Lambda → Bedrock + SES
examples/           # example request JSON + example build123d code & real STEP
```

## Setup

Uses [`uv`](https://docs.astral.sh/uv/) and a virtual environment.

```bash
uv venv                      # create .venv (Python 3.11)
uv sync --extra dev --extra cad --extra aws
# extras: cad = build123d (STEP export), aws = boto3/Bedrock, infra = CDK, dev = tests/lint
```

> `cad` pulls in OpenCascade (large). Without it, runs still produce CAD code +
> explanation but skip STEP export.

Copy `.env.example` → `.env` and fill in whatever you use (or pass credentials in
the CLI).

## Local usage

Interactive — asks questions, validates every field, then runs:

```bash
uv run printforge knight
```

Build a request and save it without running:

```bash
uv run printforge new my_order.json
```

Run a saved request non-interactively (same schema the cloud uses):

```bash
uv run printforge run examples/requests/knight_parthenon_white.json
```

### Providers

Pick at the prompt, or set in the request's `provider` block:

| provider    | credentials                                  |
|-------------|----------------------------------------------|
| `anthropic` | `ANTHROPIC_API_KEY` (or entered in CLI)      |
| `openai`    | `OPENAI_API_KEY` (or entered in CLI)         |
| `lmstudio`  | `base_url` (default `http://localhost:1234/v1`) |
| `bedrock`   | AWS default credential chain + region        |

### Output

Per order you get `out/<ORDER_ID>/`: the `.step` file(s), the generated `.py`
CAD code, each piece's `.explanation.md`, and `delivery_email.txt`. With no mail
server configured, the email is written to `out/deliveries/` instead of sent.

## Configuration & extending

- **New printer / filament** — add a `MachineProfile` / `MaterialProfile` to
  `core/registry.py`. Everything is request-overridable (`machine_key`,
  `material_key`, `preferred_materials`).
- **New piece** — add a template subclass in `workflows/chess/templates.py` and
  list it in `ENABLED_PIECES` (today: knight only). The full-set workflow
  (pawns/knights/bishops/rooks/queen/king, black/white) is a small step from here.
- **Gotchas** — each piece template ships code-default printing gotchas; a request
  overrides them per piece via `gotcha_overrides`.
- **Dimensions** — default to standard Staunton sizes; override via `dimensions`.

## AWS deployment (CDK)

API Gateway → container Lambda (Bedrock + build123d) → SES email.

```bash
uv sync --extra infra
cd infra
cdk bootstrap      # first time per account/region
cdk deploy
```

POST a `ChessWorkflowRequest` JSON to the `/generate` endpoint (API key required;
see stack outputs `ApiUrl` / `ApiKeyId`). The Lambda forces the Bedrock provider
and emails the STEP via SES.

**Not deployed yet — needs credentials.** Two prerequisites:
1. AWS credentials/account to deploy into.
2. **SES is not set up.** Email delivery to `cad@garrychess.ai` requires a
   verified SES identity (and moving out of the SES sandbox to email arbitrary
   customers). Until then, local runs fall back to save-to-disk.

> Note: API Gateway has a hard 29s timeout; a full LLM+CAD generation can exceed
> it. The synchronous route is fine for testing; production should move to async
> (SQS/Lambda async or Step Functions returning `202 + order_id`).

## Order fields

Required: `first_name`, `last_name`, `email` (validated), `shipping_address`
(basic check). Optional: `phone`, `quantity`, `stripe_payment_link`, `deadline`,
`notes`. An `order_id` is auto-generated. Piece `dimensions` default to standard
Staunton sizes; `preferred_materials` defaults to `["bambu_pla_basic"]` and is
validated against what the machine supports.

## Tests

```bash
uv run pytest
```
