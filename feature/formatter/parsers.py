"""Shared string/time parsers for UEGAR raw → Backend import mapping."""

from __future__ import annotations

import re
from typing import Any

_TITLE_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2})\s*>\s*(?P<end>\d{2}:\d{2})\s*-\s*(?P<label>.+)$"
)
_PERSONNE_RE = re.compile(
    r"^(?P<name>.+?)\s+"
    r"(?:né|née)\s+le\s+"
    r"(?P<birth>\d{2}/\d{2}/\d{4})\s+"
    r"\((?P<age>\d+)\s+ans\s*-\s*(?P<ext_id>\d+)\)"
    r"(?P<suffix>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_ARRIVAL_RE = re.compile(r"Arriv[ée]e\s+[àa]\s+(\d{2}:\d{2})", re.IGNORECASE)
_DEPARTURE_RE = re.compile(r"D[ée]part\s+[àa]\s+(\d{2}:\d{2})", re.IGNORECASE)
_WORK_STOP_RE = re.compile(r"En\s+arr[êe]t\s+de\s+travail", re.IGNORECASE)
_LAST_NUMERIC_PAREN_RE = re.compile(r"^(?P<label>.*)\((?P<code>\d+)\)\s*$")
_LAST_SITE_PAREN_RE = re.compile(r"^(?P<label>.*)\((?P<code>[^)]+)\)\s*$")
_INFIRMIERE_PREFIX_RE = re.compile(r"^Infirmi[èe]re\s+", re.IGNORECASE)


def norm_ws(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def omit_empty(data: dict[str, Any]) -> dict[str, Any]:
    """Drop None / blank strings; keep False and 0."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, dict):
            nested = omit_empty(value)
            if nested:
                out[key] = nested
            continue
        out[key] = value
    return out


def parse_title(title: str) -> tuple[str | None, str | None, str | None]:
    text = norm_ws(title)
    if not text:
        return None, None, None
    m = _TITLE_RE.match(text)
    if not m:
        return None, None, None
    return m.group("start"), m.group("end"), norm_ws(m.group("label"))


def map_period(data_moment: str) -> str | None:
    raw = norm_ws(data_moment).upper()
    if raw == "AM":
        return "MORNING"
    if raw == "PM":
        return "AFTERNOON"
    return None


def parse_personne(personne: str) -> dict[str, Any] | None:
    display = norm_ws(personne)
    if not display:
        return None
    m = _PERSONNE_RE.match(display)
    if not m:
        return None
    individual = {
        "externalId": m.group("ext_id"),
        "fullName": norm_ws(m.group("name")),
        "birthDate": m.group("birth"),
        "ageAtAppointment": int(m.group("age")),
        "displayLine": display,
    }
    return individual


def has_work_stop(personne: str) -> bool:
    return bool(_WORK_STOP_RE.search(norm_ws(personne)))


def parse_etablissement(etablissement: str) -> dict[str, Any] | None:
    display = norm_ws(etablissement)
    if not display:
        return None
    m = _LAST_NUMERIC_PAREN_RE.match(display)
    if not m:
        return None
    return {
        "externalId": m.group("code"),
        "label": norm_ws(m.group("label")),
        "displayLine": display,
    }


def parse_site(lieu: str) -> dict[str, Any] | None:
    display = norm_ws(lieu)
    if not display:
        return None
    m = _LAST_SITE_PAREN_RE.match(display)
    if not m:
        return None
    return {
        "code": norm_ws(m.group("code")),
        "label": norm_ws(m.group("label")),
        "timezone": "Europe/Paris",
    }


def parse_queue(arrivee_depart: str) -> dict[str, Any] | None:
    text = norm_ws(arrivee_depart)
    if not text:
        return None
    arrived = None
    departed = None
    am = _ARRIVAL_RE.search(text)
    dm = _DEPARTURE_RE.search(text)
    if am:
        arrived = am.group(1)
    if dm:
        departed = dm.group(1)
    if arrived and departed:
        status = "DEPARTED"
    elif arrived:
        status = "ARRIVED"
    elif departed:
        status = "DEPARTED"
    else:
        return None
    out: dict[str, Any] = {"status": status}
    if arrived:
        out["arrivedAtLocal"] = arrived
    if departed:
        out["departedAtLocal"] = departed
    return out


def clean_realise_par_name(realise_par: str) -> str:
    name = norm_ws(realise_par)
    if not name:
        return ""
    return _INFIRMIERE_PREFIX_RE.sub("", name, count=1).strip()


def category_from_visit_label(label: str) -> tuple[dict[str, str], dict[str, str] | None]:
    text = norm_ws(label)
    if text.casefold() == "visite infirmier".casefold():
        return {"label": "Visite médicale"}, {"label": "Visite infirmier"}
    return {"label": text}, None
