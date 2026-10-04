"""Cache validity policy for provider-specific quote-unit changes."""

# Bump when Bizportal mutual-fund quote-unit interpretation changes.
# Never use a public currency alias or the price magnitude as unit provenance.
BIZPORTAL_MTF_NORMALIZATION_VERSION = 1
PRICE_FIELDS = frozenset({"price", "last", "open", "high", "low"})


def required_price_normalization_version(
    indicator: str, quote_type: str
) -> int | None:
    """Version TASE funds, including numeric IDs with unknown cached type."""
    if indicator.isdigit() and quote_type.upper() in {"", "MTF"}:
        return BIZPORTAL_MTF_NORMALIZATION_VERSION
    return None