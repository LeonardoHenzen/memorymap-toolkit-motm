from typing import Any
from datetime import date
import regex as re
import calendar

from dataclasses import dataclass


@dataclass
class Timespan:
    start: date
    end: date

    def __init__(self, start: date | None = None, end: date | None = None):
        self.start = start
        self.end = end if end else start

    def as_tuple(self):
        return (self.start, self.end)


MONTHS_DE = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
    "jan": 1,
    "feb": 2,
    "mär": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "okt": 10,
    "nov": 11,
    "dez": 12,
}

NAMED_PERIODS = {
    "1. weltkrieg": Timespan(date(1914, 7, 28), date(1918, 11, 11)),
    "2. weltkrieg": Timespan(date(1939, 9, 1), date(1945, 9, 2)),
}


def _last_day(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _parse_partial_date_range(s: str) -> tuple[date, date] | None:
    """
    Parse a single date expression into a (start, end) tuple,
    where end reflects the last day of the known precision.

    >>> _parse_partial_date_range("1941-08-25")
    (datetime.date(1941, 8, 25), datetime.date(1941, 8, 25))

    >>> _parse_partial_date_range("25/08/1941")
    (datetime.date(1941, 8, 25), datetime.date(1941, 8, 25))

    >>> _parse_partial_date_range("19. Januar 1913")
    (datetime.date(1913, 1, 19), datetime.date(1913, 1, 19))

    >>> _parse_partial_date_range("Januar 1934")
    (datetime.date(1934, 1, 1), datetime.date(1934, 1, 31))

    >>> _parse_partial_date_range("Sept. 1943")
    (datetime.date(1943, 9, 1), datetime.date(1943, 9, 30))

    >>> _parse_partial_date_range("1923")
    (datetime.date(1923, 1, 1), datetime.date(1923, 12, 31))

    >>> _parse_partial_date_range("194?")
    (datetime.date(1940, 1, 1), datetime.date(1949, 12, 31))

    >>> _parse_partial_date_range("1930er Jahre")
    (datetime.date(1930, 1, 1), datetime.date(1939, 12, 31))
    """
    s = s.strip()

    # Fuzzy year (194?) — before stripping ?
    m = re.fullmatch(r"(\d{3})\?", s)
    if m:
        year = int(m.group(1) + "0")
        return date(year, 1, 1), date(year + 9, 12, 31)

    s = s.rstrip("*").rstrip("?").strip()
    s = re.sub(r"\s+", " ", s)

    # ISO datetime: 1941-08-25 00:00:00
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return d, d

    # DD/MM/YYYY
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return d, d

    # DD.MM.YYYY
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return d, d

    # DD. MonthName YYYY
    m = re.fullmatch(r"(\d{1,2})\.?\s+([a-zäöü]+\.?)\s+(\d{4})", s, re.IGNORECASE)
    if m:
        month = MONTHS_DE.get(m.group(2).lower().rstrip("."))
        if month:
            d = date(int(m.group(3)), month, int(m.group(1)))
            return d, d

    # MonthName YYYY → full month range
    m = re.fullmatch(r"([a-zäöü]+\.?)\s+(\d{4})", s, re.IGNORECASE)
    if m:
        month = MONTHS_DE.get(m.group(1).lower().rstrip("."))
        if month:
            year = int(m.group(2))
            return date(year, month, 1), _last_day(year, month)

    # Decade: 1930er Jahre
    m = re.fullmatch(r"(\d{4})er\s+jahre", s, re.IGNORECASE)
    if m:
        year = int(m.group(1))
        return date(year, 1, 1), date(year + 9, 12, 31)

    # Plain year → full year range
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        year = int(m.group(1))
        return date(year, 1, 1), date(year, 12, 31)

    return None


def parse_timespan(raw: Any) -> Timespan:
    """
    Convert a raw string into a Timespan.
    Returns None if the string cannot be parsed.

    >>> parse_timespan("19. Januar 1913")
    Timespan(start=datetime.date(1913, 1, 19), end=datetime.date(1913, 1, 19))

    >>> parse_timespan("ca. 1929–1935")
    Timespan(start=datetime.date(1929, 1, 1), end=datetime.date(1935, 12, 31))

    >>> parse_timespan("Ende 1942- Mai 1945")
    Timespan(start=datetime.date(1942, 12, 31), end=datetime.date(1945, 5, 31))

    >>> parse_timespan("1932/Januar 1933")
    Timespan(start=datetime.date(1932, 1, 1), end=datetime.date(1933, 1, 31))

    >>> parse_timespan("1941-08-25")
    Timespan(start=datetime.date(1941, 8, 25), end=datetime.date(1941, 8, 25))

    >>> parse_timespan("25/08/1941*")
    Timespan(start=datetime.date(1941, 8, 25), end=datetime.date(1941, 8, 25))

    >>> parse_timespan("1930er Jahre")
    Timespan(start=datetime.date(1930, 1, 1), end=datetime.date(1939, 12, 31))

    >>> parse_timespan("1. Weltkrieg")
    Timespan(start=datetime.date(1914, 7, 28), end=datetime.date(1918, 11, 11))

    >>> parse_timespan("194?")
    Timespan(start=datetime.date(1940, 1, 1), end=datetime.date(1949, 12, 31))

    >>> parse_timespan("Während des Dienstes")
    Timespan(start=None, end=None)

    >>> parse_timespan("")
    Timespan(start=None, end=None)

    >>> parse_timespan("-")
    Timespan(start=None, end=None)

    >>> parse_timespan("1928-1932")
    Timespan(start=datetime.date(1928, 1, 1), end=datetime.date(1932, 12, 31))

    >>> parse_timespan("1936-38")
    Timespan(start=datetime.date(1936, 1, 1), end=datetime.date(1938, 12, 31))
    
    >>> parse_timespan("1938-194?")
    Timespan(start=datetime.date(1938, 1, 1), end=datetime.date(1949, 12, 31))
    """
    if not raw:
        return Timespan()

    s = str(raw).strip().strip('"').strip()

    if not s or s in ("-", "?"):
        return Timespan()

    # Named periods
    if s.lower() in NAMED_PERIODS:
        return NAMED_PERIODS[s.lower()]

    # Strip qualifiers
    qualifiers = (
        r"^(ca\.\s*|ab\s+|vor\s+|nach\s+dem\s+|nach\s+|bis\s+|während\s+des\s+\w+\s*)"
    )
    s_clean = re.sub(qualifiers, "", s, flags=re.IGNORECASE).strip()

    # Strip trailing annotations like "(ca. 2 Monate)"
    s_clean = re.sub(r"\(.*?\)", "", s_clean).strip()

    # "Ende YYYY" → last day of that year
    def parse_ende(part: str) -> tuple[date, date] | None:
        m = re.fullmatch(r"ende\s+(\d{4})", part.strip(), re.IGNORECASE)
        if m:
            d = date(int(m.group(1)), 12, 31)
            return d, d
        return None

    def try_range(left: str, right: str) -> Timespan:
        start_range = parse_ende(left) or _parse_partial_date_range(left)
        end_range = parse_ende(right) or _parse_partial_date_range(right)
        if start_range and end_range:
            return Timespan(start_range[0], end_range[1])
        if start_range:
            return Timespan(start_range[0], start_range[1])
        return Timespan()

    # En dash — always a range separator
    m = re.search(r"\s*–\s*", s_clean)
    if m:
        return try_range(s_clean[: m.start()], s_clean[m.end() :])
    
    # YYYY-YYYY (plain year range like 1928-1932)
    m = re.fullmatch(r"(\d{4})-(\d{4})", s_clean)
    if m:
        return Timespan(date(int(m.group(1)), 1, 1), date(int(m.group(2)), 12, 31))
    
    # YYYY-YY (short end year like 1936-38 → 1936-1938)
    m = re.fullmatch(r"(\d{4})-(\d{2})", s_clean)
    if m:
        century = m.group(1)[:2]
        end_year = int(century + m.group(2))
        return Timespan(date(int(m.group(1)), 1, 1), date(end_year, 12, 31))
    
    # YYYY-YYY? (fuzzy short end year like 1938-194? → 1938 to 1940–1949)
    m = re.fullmatch(r"(\d{4})-(\d{3})\?", s_clean)
    if m:
        end_decade = int(m.group(2) + "0")
        return Timespan(date(int(m.group(1)), 1, 1), date(end_decade + 9, 12, 31))
    
    # Hyphen — separator only if followed by space or letter (protects ISO dates)
    m = re.search(r"-\s+|-(?=[A-Za-zÄÖÜäöü])", s_clean)
    if m:
        return try_range(s_clean[: m.start()], s_clean[m.end() :])

    # Slash — range separator (1932/Januar 1933), but not in DD/MM/YYYY
    if not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}\*?", s_clean):
        slash_sep = re.split(r"\s*/\s*", s_clean, maxsplit=1)
        if len(slash_sep) == 2:
            result = try_range(slash_sep[0], slash_sep[1])
            if result:
                return result

    # Single value
    single = parse_ende(s_clean) or _parse_partial_date_range(s_clean)
    if single:
        return Timespan(single[0], single[1])

    return Timespan()


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
