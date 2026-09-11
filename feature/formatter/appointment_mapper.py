"""Map one raw UEGAR vacation event → Backend appointment object."""

from __future__ import annotations

from typing import Any

from feature.formatter.parsers import (
    category_from_visit_label,
    clean_realise_par_name,
    has_work_stop,
    map_period,
    norm_ws,
    omit_empty,
    parse_etablissement,
    parse_personne,
    parse_queue,
    parse_site,
    parse_title,
)


def map_appointment(
    raw: dict[str, Any],
    *,
    agenda_code: str,
    agenda_date: str,
    warnings: list[str],
    index: int,
) -> dict[str, Any] | None:
    tag = norm_ws(raw.get("event_tag"))
    title = norm_ws(raw.get("title"))
    start, end, visit_label = parse_title(title)
    if not start or not visit_label:
        warnings.append(
            f"appointment[{index}]: could not parse title {title!r}"
        )

    appt: dict[str, Any] = {
        "agendaCode": agenda_code,
        "date": agenda_date,
    }
    if tag:
        appt["sourceAppointmentId"] = tag

    if start:
        appt["localStartTime"] = start
    if end:
        appt["localEndTime"] = end

    period = map_period(str(raw.get("data_moment") or ""))
    if period:
        appt["period"] = period
    elif norm_ws(raw.get("data_moment")):
        warnings.append(
            f"appointment[{index}] tag={tag}: unknown data_moment "
            f"{raw.get('data_moment')!r}"
        )

    if visit_label:
        category, sub = category_from_visit_label(visit_label)
        appt["category"] = category
        if sub:
            appt["subCategory"] = sub

    personne = str(raw.get("personne") or "")
    individual = parse_personne(personne)
    if individual:
        appt["individual"] = individual
    elif norm_ws(personne):
        warnings.append(
            f"appointment[{index}] tag={tag}: could not parse personne "
            f"{norm_ws(personne)!r}"
        )

    if has_work_stop(personne):
        appt["flags"] = {"isWorkStopped": True}

    member = parse_etablissement(str(raw.get("etablissement") or ""))
    if member:
        appt["member"] = member
    elif norm_ws(raw.get("etablissement")):
        warnings.append(
            f"appointment[{index}] tag={tag}: could not parse etablissement "
            f"{norm_ws(raw.get('etablissement'))!r}"
        )

    site = parse_site(str(raw.get("lieu") or ""))
    if site:
        appt["site"] = site
    elif norm_ws(raw.get("lieu")):
        warnings.append(
            f"appointment[{index}] tag={tag}: could not parse lieu "
            f"{norm_ws(raw.get('lieu'))!r}"
        )

    performed = _performed_by(raw)
    if performed:
        appt["performedByResource"] = performed

    queue = parse_queue(str(raw.get("arrivee_depart") or ""))
    if queue:
        appt["queue"] = queue

    canceled = int(raw.get("is_canceled") or 0) == 1
    css = norm_ws(raw.get("css_class"))
    if canceled or css.casefold() == "canceled":
        appt["status"] = "CANCELLED"

    return omit_empty(appt)


def _performed_by(raw: dict[str, Any]) -> dict[str, Any] | None:
    name = clean_realise_par_name(str(raw.get("realise_par") or ""))
    fid = norm_ws(raw.get("ressource_fonction_id"))
    detail = raw.get("ressource_detail")
    if isinstance(detail, dict):
        detail_fid = norm_ws(detail.get("_fonction_id"))
        if not fid and detail_fid:
            fid = detail_fid
        if not name:
            name = clean_realise_par_name(str(detail.get("Identité") or ""))
    if not name and not fid:
        return None
    out: dict[str, Any] = {}
    if fid:
        out["sourceExternalId"] = fid
    if name:
        out["fullName"] = name
    return omit_empty(out) or None
