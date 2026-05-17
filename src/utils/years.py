import re
from datetime import date


def expand_year_token(token: str) -> str:
    value = str(token).strip()
    if not value:
        raise ValueError("Year is required.")
    if not value.isdigit():
        raise ValueError(f"Invalid year: {token}")

    year = int(value)
    if year < 100:
        year += 2000
    return str(year)


def normalize_year_separator(value: str) -> str:
    return re.sub(r"\s*(?:-|~|到|至|—|–)\s*", "-", value.strip())


def parse_period_token(token: str) -> tuple[str, int | None]:
    value = str(token).strip()
    match = re.fullmatch(r"(\d{2,4})\s*(?:(?:[hH])([12])|([上下])(?:半(?:年)?)?)?", value)
    if not match:
        raise ValueError(f"Invalid year or half-year: {token}")

    year = expand_year_token(match.group(1))
    half_text = match.group(2) or match.group(3)
    if not half_text:
        return year, None
    half = int(half_text) if half_text.isdigit() else (1 if half_text == "上" else 2)
    return year, half


def period_sort_key(year: str, half: int | None) -> tuple[int, int]:
    return int(year), half or 0


def period_label(year: str, half: int | None) -> str:
    return f"{year}H{half}" if half else year


def normalize_year_arg(year_arg: str) -> str:
    value = normalize_year_separator(str(year_arg))
    if not value:
        raise ValueError("Year or year range is required.")
    if value.lower() == "all":
        return "all"
    if "-" in value:
        parts = [part.strip() for part in value.split("-", 1)]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("Invalid year range format. Use YYYY-YYYY, YY-YY, or YYH2-YYH1.")
        start_year, start_half = parse_period_token(parts[0])
        end_year, end_half = parse_period_token(parts[1])
        if (start_half is None) != (end_half is None):
            raise ValueError("Both sides of a range must use the same precision.")
        if period_sort_key(start_year, start_half) > period_sort_key(end_year, end_half):
            raise ValueError("Start period must not be later than end period.")
        return f"{period_label(start_year, start_half)}-{period_label(end_year, end_half)}"

    year, half = parse_period_token(value)
    return period_label(year, half)


def years_in_arg(year_arg: str) -> set[str] | None:
    normalized = normalize_year_arg(year_arg)
    if normalized == "all":
        return None
    if "H" in normalized:
        periods = half_year_periods_in_arg(normalized)
        if periods is None:
            return None
        return {year for year, _half in periods}
    if "-" in normalized:
        start_year, end_year = map(int, normalized.split("-", 1))
        return {str(year) for year in range(start_year, end_year + 1)}
    return {normalized}


def half_year_periods_in_arg(year_arg: str) -> set[tuple[str, int]] | None:
    normalized = normalize_year_arg(year_arg)
    if normalized == "all":
        return None
    if "H" not in normalized:
        return None

    parts = normalized.split("-", 1)
    if len(parts) == 1:
        start_year, start_half = parse_period_token(parts[0])
        return {(start_year, start_half or 1)}

    start_year, start_half = parse_period_token(parts[0])
    end_year, end_half = parse_period_token(parts[1])
    periods = set()
    year = int(start_year)
    half = start_half or 1
    while (year, half) <= (int(end_year), end_half or 2):
        periods.add((str(year), half))
        if half == 1:
            half = 2
        else:
            year += 1
            half = 1
    return periods


def date_half(date_str: str) -> tuple[str, int] | None:
    try:
        value = date.fromisoformat(str(date_str).strip())
    except ValueError:
        return None
    return str(value.year), 1 if value.month <= 6 else 2


def contest_matches_year_arg(row: dict, year_arg: str) -> bool:
    normalized = normalize_year_arg(year_arg)
    if normalized == "all":
        return True

    periods = half_year_periods_in_arg(normalized)
    if periods is not None:
        contest_period = date_half(row.get("date", ""))
        return contest_period in periods

    years = years_in_arg(normalized)
    return years is None or str(row.get("year", "")) in years