"""Build deduplicated top-level resources[] from raw.ressource_detail."""

from __future__ import annotations

from typing import Any

from feature.formatter.parsers import norm_ws, omit_empty


def map_resources(
    raw_events: list[dict[str, Any]],
    *,
    agenda_code: str,
    warnings: list[str],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for index, raw in enumerate(raw_events):
        detail = raw.get("ressource_detail")
        if not isinstance(detail, dict) or not detail:
            continue

        raw_fid = norm_ws(raw.get("ressource_fonction_id"))
        detail_fid = norm_ws(detail.get("_fonction_id"))
        if raw_fid and detail_fid and raw_fid != detail_fid:
            warnings.append(
                f"resource[{index}] tag={norm_ws(raw.get('event_tag'))}: "
                f"ressource_fonction_id={raw_fid!r} differs from "
                f"ressource_detail._fonction_id={detail_fid!r} "
                "(not merged)"
            )

        source_id = detail_fid or raw_fid
        if not source_id:
            warnings.append(
                f"resource[{index}] tag={norm_ws(raw.get('event_tag'))}: "
                "missing fonction id; skipped resource row"
            )
            continue

        if source_id in by_id:
            continue

        resource = omit_empty(
            {
                "sourceExternalId": source_id,
                "fullName": norm_ws(detail.get("Identité")),
                "civility": norm_ws(detail.get("Civilité")),
                "professionalPhone": norm_ws(
                    detail.get("Téléphone professionnel")
                ),
                "professionalEmail": norm_ws(
                    detail.get("Courriel professionnel")
                ),
                "functionType": _function_type(detail.get("Type de fonction")),
                "agendaCode": agenda_code,
            }
        )
        # Fax intentionally omitted from Backend payload.
        by_id[source_id] = resource
        order.append(source_id)

        # Keep a separate entry when IDs conflict (do not merge).
        if raw_fid and detail_fid and raw_fid != detail_fid:
            if raw_fid not in by_id:
                stub = omit_empty(
                    {
                        "sourceExternalId": raw_fid,
                        "fullName": norm_ws(raw.get("realise_par"))
                        or norm_ws(detail.get("Identité")),
                        "agendaCode": agenda_code,
                    }
                )
                by_id[raw_fid] = stub
                order.append(raw_fid)

    return [by_id[key] for key in order]


def _function_type(value: Any) -> dict[str, str] | None:
    label = norm_ws(value)
    if not label:
        return None
    return {"label": label}
