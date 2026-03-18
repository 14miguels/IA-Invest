from typing import Iterable, List, Optional, Union


def unique_preserve_order(values: Iterable[str], upper: bool = False) -> List[str]:
    """Return unique non-empty strings while preserving order.
    If upper=True, normalize to uppercase (useful for tickers)."""
    seen = set()
    result: List[str] = []

    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned:
            continue
        if upper:
            cleaned = cleaned.upper()
        if cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)

    return result


def assets_to_csv(assets: Optional[Iterable[str]]) -> str:
    """Convert assets/tickers into a stable comma-separated string (uppercased, unique)."""
    if not assets:
        return ""
    return ",".join(unique_preserve_order(assets, upper=True))


def csv_to_assets(value: Optional[str]) -> List[str]:
    """Convert a comma-separated asset string back into a cleaned, uppercased list."""
    if not value:
        return []
    parts = (part.strip() for part in str(value).split(","))
    return unique_preserve_order(parts, upper=True)


def clamp(value: Union[int, float], minimum: Union[int, float], maximum: Union[int, float]) -> Union[int, float]:
    """Clamp a number between minimum and maximum (order-agnostic bounds)."""
    if minimum > maximum:
        minimum, maximum = maximum, minimum
    return max(minimum, min(value, maximum))
