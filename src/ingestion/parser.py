import csv
import io
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REQUIRED_COLUMNS = ("phone", "timezone")


@dataclass
class ContactRow:
    phone: str
    timezone: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class RowError:
    line: int
    reason: str


@dataclass
class ParseResult:
    valid: list[ContactRow] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)


def _valid_timezone(tz: str) -> bool:
    try:
        ZoneInfo(tz)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def parse_contacts(csv_text: str) -> ParseResult:
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise ValueError(f"CSV missing required column(s): {', '.join(missing)}")

    result = ParseResult()
    # DictReader's first data row is line 2 in the file.
    for offset, raw in enumerate(reader):
        line = offset + 2
        phone = (raw.get("phone") or "").strip()
        timezone = (raw.get("timezone") or "").strip()
        if not phone:
            result.errors.append(RowError(line, "missing phone"))
            continue
        if not _valid_timezone(timezone):
            result.errors.append(RowError(line, f"invalid timezone: {timezone!r}"))
            continue
        metadata = {
            k: (v or "").strip()
            for k, v in raw.items()
            if k not in REQUIRED_COLUMNS and k is not None
        }
        result.valid.append(ContactRow(phone=phone, timezone=timezone, metadata=metadata))
    return result
