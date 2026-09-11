"""Build Backend agenda-import JSON payload from raw UEGAR records."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from feature.formatter.appointment_mapper import map_appointment
from feature.formatter.parsers import norm_ws
from feature.formatter.resource_mapper import map_resources
from utils.logger import get_logger
from utils.paths import DATA_DIR, ensure_runtime_dirs

logger = get_logger("payload_formatter")


class PayloadFormatError(ValueError):
    """Raised when the final payload fails validation."""


def build_import_payload(
    raw_events: Sequence[dict[str, Any]],
    agenda_code: str,
    agenda_label: str,
    agenda_date: str,
    scraped_at: str | None = None,
    display_name: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Transform raw crawler records into one Backend-compatible import object.

    Returns (payload, warnings). Does not invent agenda_date — caller must
    pass the selected agenda date from crawl context (DD/MM/YYYY).
    """
    warnings: list[str] = []
    code = norm_ws(agenda_code)
    label = norm_ws(agenda_label) or code
    date = norm_ws(agenda_date)
    if not code:
        raise PayloadFormatError("agenda_code is required")
    if not date:
        raise PayloadFormatError(
            "agenda_date is required (must come from crawl context)"
        )
    if not _looks_like_fr_date(date):
        warnings.append(
            f"agenda_date {date!r} is not DD/MM/YYYY; writing as provided"
        )

    events = [dict(row) for row in raw_events if isinstance(row, dict)]
    appointments: list[dict[str, Any]] = []
    for index, raw in enumerate(events):
        appt = map_appointment(
            raw,
            agenda_code=code,
            agenda_date=date,
            warnings=warnings,
            index=index,
        )
        if appt:
            appointments.append(appt)

    resources = map_resources(events, agenda_code=code, warnings=warnings)

    scraped = scraped_at or _utc_now_z()
    payload: dict[str, Any] = {
        "schemaVersion": "1.1",
        "source": "UEGAR",
        "sourceLocale": "fr-FR",
        "scrapedAt": scraped,
        "agendas": [
            {
                "code": code,
                "label": label,
                "type": "MULTI_RESOURCE",
            }
        ],
        "resources": resources,
        "appointments": appointments,
        "agendaPreferences": {},
    }
    if norm_ws(display_name):
        payload["userContext"] = {"displayName": norm_ws(display_name)}

    validate_import_payload(payload, warnings)
    return payload, warnings


def validate_import_payload(
    payload: dict[str, Any],
    warnings: list[str] | None = None,
) -> None:
    warn = warnings if warnings is not None else []
    if payload.get("schemaVersion") != "1.1":
        raise PayloadFormatError("schemaVersion must be '1.1'")
    if payload.get("source") != "UEGAR":
        raise PayloadFormatError("source must be 'UEGAR'")
    if payload.get("sourceLocale") != "fr-FR":
        raise PayloadFormatError("sourceLocale must be 'fr-FR'")
    for key in ("agendas", "resources", "appointments"):
        if not isinstance(payload.get(key), list):
            raise PayloadFormatError(f"{key} must be an array")

    for i, appt in enumerate(payload["appointments"]):
        if not isinstance(appt, dict):
            raise PayloadFormatError(f"appointments[{i}] must be an object")
        if not norm_ws(appt.get("agendaCode")):
            raise PayloadFormatError(f"appointments[{i}].agendaCode missing")
        if not norm_ws(appt.get("date")):
            raise PayloadFormatError(f"appointments[{i}].date missing")
        if "sourceAppointmentId" not in appt:
            warn.append(
                f"appointments[{i}]: missing sourceAppointmentId "
                "(raw event_tag empty)"
            )
        if not norm_ws(appt.get("localStartTime")):
            warn.append(f"appointments[{i}]: missing localStartTime")
        individual = appt.get("individual")
        if isinstance(individual, dict) and not norm_ws(
            individual.get("externalId")
        ):
            warn.append(
                f"appointments[{i}]: individual.externalId missing after parse"
            )


def default_import_json_path(stamp: str | None = None) -> Path:
    ensure_runtime_dirs()
    if stamp:
        return DATA_DIR / f"agenda-import_{stamp}.json"
    from feature.agendas.vacations_db import paired_run_output_paths

    _, _, import_path = paired_run_output_paths()
    return import_path


def write_import_payload(
    payload: dict[str, Any],
    path: Path | None = None,
) -> Path:
    out = path or default_import_json_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    logger.info("Agenda import JSON written | path=%s", out)
    return out


def load_raw_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as exc:
                raise PayloadFormatError(
                    f"Invalid JSONL at {path}:{line_no}: {exc}"
                ) from exc
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def format_raw_jsonl_file(
    raw_jsonl_path: Path,
    *,
    agenda_code: str,
    agenda_label: str,
    agenda_date: str,
    scraped_at: str | None = None,
    display_name: str | None = None,
    output_path: Path | None = None,
) -> tuple[Path, dict[str, Any], list[str]]:
    """Fresh payload from current raw JSONL only (never merges prior imports)."""
    raw_events = load_raw_jsonl(raw_jsonl_path)
    payload, warnings = build_import_payload(
        raw_events,
        agenda_code=agenda_code,
        agenda_label=agenda_label,
        agenda_date=agenda_date,
        scraped_at=scraped_at,
        display_name=display_name,
    )
    out = write_import_payload(payload, path=output_path)
    return out, payload, warnings


def _utc_now_z() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _looks_like_fr_date(value: str) -> bool:
    parts = value.split("/")
    if len(parts) != 3:
        return False
    d, m, y = parts
    return d.isdigit() and m.isdigit() and y.isdigit() and len(y) == 4
