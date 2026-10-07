"""Fail closed for paid Aether API calls under the owner's no-paid-API policy.

Local credential readiness and historical spending caps are not spending approval.
There is deliberately no environment variable, CLI flag, or saved-setting bypass.
"""
from short_video_credentials import CredentialError


def require_paid_api_allowed() -> None:
    raise CredentialError("aether_paid_api_disabled")
