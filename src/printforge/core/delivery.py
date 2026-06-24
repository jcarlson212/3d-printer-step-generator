"""Delivery of the finished STEP file(s) + explanation to the customer/fulfilment.

The same payload (one email: the concatenated detailed explanations as the body,
the STEP file(s) attached) is delivered for both local and cloud runs. The
transport is pluggable:

* ``ses``  -- Amazon SES (used in the Lambda / cloud path).
* ``smtp`` -- any SMTP server (used for local runs; configured via env).
* ``save`` -- write the email + attachments to disk (zero-config fallback so a
  local run always "delivers" something even with no mail server).

Default transport is ``auto``: SES if running in AWS, else SMTP if configured,
else save-to-disk.
"""

from __future__ import annotations

import os
from email.message import EmailMessage
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, EmailStr, Field

DEFAULT_RECIPIENT = "cad@garrychess.ai"


class DeliveryMethod(str, Enum):
    AUTO = "auto"
    SES = "ses"
    SMTP = "smtp"
    SAVE = "save"


class Attachment(BaseModel):
    filename: str
    content: bytes
    mime_type: str = "application/step"


class DeliveryConfig(BaseModel):
    recipient: EmailStr = DEFAULT_RECIPIENT
    sender: str | None = Field(
        default=None, description="From address; defaults to DELIVERY_SENDER env or recipient."
    )
    method: DeliveryMethod = DeliveryMethod.AUTO

    # SMTP (local). Falls back to env vars when unset.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True

    # SES (cloud).
    aws_region: str | None = None

    # save-to-disk fallback location.
    save_dir: str = "out/deliveries"

    def resolved_sender(self) -> str:
        return self.sender or os.environ.get("DELIVERY_SENDER") or str(self.recipient)


class DeliveryResult(BaseModel):
    method: DeliveryMethod
    recipient: str
    detail: str


def _build_email(cfg: DeliveryConfig, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.resolved_sender()
    msg["To"] = str(cfg.recipient)
    msg.set_content(body)
    return msg


def _attach(msg: EmailMessage, attachments: list[Attachment]) -> None:
    for att in attachments:
        maintype, _, subtype = att.mime_type.partition("/")
        msg.add_attachment(
            att.content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=att.filename,
        )


def _choose_method(cfg: DeliveryConfig) -> DeliveryMethod:
    if cfg.method is not DeliveryMethod.AUTO:
        return cfg.method
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("USE_SES"):
        return DeliveryMethod.SES
    if cfg.smtp_host or os.environ.get("SMTP_HOST"):
        return DeliveryMethod.SMTP
    return DeliveryMethod.SAVE


def deliver(
    cfg: DeliveryConfig,
    *,
    subject: str,
    body: str,
    attachments: list[Attachment],
) -> DeliveryResult:
    method = _choose_method(cfg)
    msg = _build_email(cfg, subject, body)
    _attach(msg, attachments)

    if method is DeliveryMethod.SES:
        return _send_ses(cfg, msg)
    if method is DeliveryMethod.SMTP:
        return _send_smtp(cfg, msg)
    return _save_to_disk(cfg, msg, subject, body, attachments)


def _send_ses(cfg: DeliveryConfig, msg: EmailMessage) -> DeliveryResult:
    import boto3  # imported lazily so non-AWS local runs don't need boto3

    region = cfg.aws_region or os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("ses", region_name=region)
    client.send_raw_email(
        Source=msg["From"],
        Destinations=[msg["To"]],
        RawMessage={"Data": msg.as_bytes()},
    )
    return DeliveryResult(
        method=DeliveryMethod.SES, recipient=msg["To"], detail=f"sent via SES ({region})"
    )


def _send_smtp(cfg: DeliveryConfig, msg: EmailMessage) -> DeliveryResult:
    import smtplib

    host = cfg.smtp_host or os.environ["SMTP_HOST"]
    port = cfg.smtp_port or int(os.environ.get("SMTP_PORT", "587"))
    username = cfg.smtp_username or os.environ.get("SMTP_USERNAME")
    password = cfg.smtp_password or os.environ.get("SMTP_PASSWORD")
    with smtplib.SMTP(host, port) as server:
        if cfg.smtp_use_tls:
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(msg)
    return DeliveryResult(
        method=DeliveryMethod.SMTP, recipient=msg["To"], detail=f"sent via SMTP ({host}:{port})"
    )


def _save_to_disk(
    cfg: DeliveryConfig,
    msg: EmailMessage,
    subject: str,
    body: str,
    attachments: list[Attachment],
) -> DeliveryResult:
    out = Path(cfg.save_dir)
    out.mkdir(parents=True, exist_ok=True)
    safe_subject = "".join(c if c.isalnum() or c in "-_" else "_" for c in subject)[:60]
    (out / f"{safe_subject}.eml").write_bytes(msg.as_bytes())
    (out / f"{safe_subject}.txt").write_text(f"To: {cfg.recipient}\n\n{body}", encoding="utf-8")
    for att in attachments:
        (out / att.filename).write_bytes(att.content)
    return DeliveryResult(
        method=DeliveryMethod.SAVE,
        recipient=str(cfg.recipient),
        detail=f"saved to {out.resolve()} (no mail transport configured)",
    )
