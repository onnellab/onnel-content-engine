"""Owner-approved provider-base budget for Aether Inn.

Only one Lyria 3 Pro candidate at a provider base price <= $0.08 is permitted.
Current public price and commercial-use sources are checked separately at paid
request boundaries. Taxes, currency adjustments and invoice totals are not
represented as zero or as verified. Gemini and other paid providers remain off.
No environment, credential or generic API bypass is provided.
"""
from short_video_credentials import CredentialError

ALLOWED_LYRIA_MODEL = "lyria-3-pro-preview"
ALLOWED_LYRIA_PURPOSE = "lyria_3_pro_single"
MAX_LYRIA_CANDIDATES = 1
MAX_LYRIA_COST_USD = 0.08


def require_paid_api_allowed(*, purpose: str | None = None,
                             model: str | None = None,
                             candidate_count: int | None = None,
                             estimated_cost_usd: float | None = None) -> None:
    """Authorize *only* the owner's $0.08 Lyria 3 Pro single.

    This gate never authorizes Gemini, multiple candidates, other model names,
    unknown cost estimates, or direct promotion of an unauthorized provider.
    Existing local enabled/cap/ADC preflight checks remain mandatory.
    """
    if purpose != ALLOWED_LYRIA_PURPOSE or model != ALLOWED_LYRIA_MODEL:
        raise CredentialError("aether_paid_api_disabled")
    if type(candidate_count) is not int or candidate_count != MAX_LYRIA_CANDIDATES:
        raise CredentialError("aether_lyria_candidate_limit")
    if (type(estimated_cost_usd) not in (float, int)
            or not 0 < float(estimated_cost_usd) <= MAX_LYRIA_COST_USD + 1e-9):
        raise CredentialError("aether_lyria_spend_limit")
