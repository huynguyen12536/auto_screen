"""Scrape File d'attente cards from #divContainerVacations into SQLite."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from feature.agendas.vacations_db import (
    default_db_path,
    export_events_jsonl,
    paired_run_output_paths,
    upsert_events,
)
from feature.formatter.payload_formatter import (
    build_import_payload,
    write_import_payload,
)
from utils.logger import get_logger
from utils.timing import sleep

logger = get_logger("scrape_vacations")

CONTAINER_SELECTOR = "#divContainerVacations"
AGENDA_DATE_SELECTOR = "#ucChoixDeLaDate_VDCPeriodeData"
RESSOURCE_LINK_SUFFIX = "_ucRessourcePrincipaleEventData_lnkBtnRessourceData"
DIALOG_VISIBLE = ".ui-dialog:visible"
DIALOG_IFRAME = ".ui-dialog:visible iframe"
DIALOG_CLOSE = (
    ".ui-dialog:visible button.ui-dialog-titlebar-close, "
    ".ui-dialog:visible .ui-dialog-titlebar-close"
)
DETAIL_READY = "#ctl00_placeHolderContenuFormSansOnglet_lbIdentiteData"

_EXTRACT_JS = """
() => {
  const root = document.querySelector('#divContainerVacations');
  if (!root) return [];
  const events = root.querySelectorAll('[id$="_divEvent"]');
  return Array.from(events).map((el) => {
    const id = el.id || '';
    const m = id.match(/ctl(\\d+)_divEvent/);
    const titleEl = el.querySelector('[id$="_lbTitreEventData"]');
    const arriveeEl = el.querySelector('[id$="_lbArriveeDepartData"]');
    const personneA = el.querySelector('[id$="_ucIndividuData_lnkBtnPPData"]');
    const etabA = el.querySelector('[id$="_ucAdherentData_lnkBtnEtabData"]');
    const ressourceA = el.querySelector(
      '[id$="_ucRessourcePrincipaleEventData_lnkBtnRessourceData"]'
    );
    const lieuEl = el.querySelector(
      '[id$="_ucRessourceLieuEventData_lbRessourceData"]'
    );
    const ppDiv = el.querySelector('[id$="_divPersonnePhysique"]');
    const ppUc = el.querySelector('[id$="_ucIndividuData_divUcAfficherPP"]');
    const etabUc = el.querySelector(
      '[id$="_ucAdherentData_divUcAfficherEtablissement"]'
    );
    const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
    const multiline = (t) =>
      (t || '')
        .split(/\\n|<br\\s*\\/?>/i)
        .map((s) => s.replace(/\\s+/g, ' ').trim())
        .filter(Boolean)
        .join(' | ');
    const onclick = (ressourceA && ressourceA.getAttribute('onclick')) || '';
    const idMatch = onclick.match(/frmDetailFonction\\.aspx\\?Id=([^'\"&]+)/i);
    return {
      event_tag: el.getAttribute('tag') || '',
      ctl_index: m ? parseInt(m[1], 10) : null,
      css_class: (el.className || '').trim(),
      data_moment: el.getAttribute('data-moment') || '',
      title: clean(titleEl ? titleEl.innerText : ''),
      arrivee_depart: multiline(
        arriveeEl ? arriveeEl.innerHTML || arriveeEl.innerText : ''
      ),
      personne: clean(personneA ? personneA.innerText : ''),
      personne_id: (ppUc && ppUc.getAttribute('data-key')) || '',
      personne_filtre_key: (ppDiv && ppDiv.getAttribute('data-key')) || '',
      etablissement: clean(etabA ? etabA.innerText : ''),
      etablissement_id: (etabUc && etabUc.getAttribute('data-key')) || '',
      realise_par: clean(ressourceA ? ressourceA.innerText : ''),
      ressource_fonction_id: idMatch ? idMatch[1] : '',
      lieu: clean(lieuEl ? lieuEl.innerText : ''),
      is_canceled: el.classList.contains('Canceled') ? 1 : 0,
    };
  });
}
"""

_DETAIL_EXTRACT_JS = """
() => {
  const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  const stripColon = (t) => clean(t).replace(/\\s*:\\s*$/, '');
  const out = {};
  const hid = document.querySelector(
    '#ctl00_placeHolderContenuFormSansOnglet_HiddenFieldIDFonction'
  );
  if (hid && hid.value) out['_fonction_id'] = hid.value;

  const rows = document.querySelectorAll('.row.form-group');
  for (const row of rows) {
    const labelEl = row.querySelector('.form-label, [id*="lb"]');
    let label = '';
    if (labelEl) {
      const span = labelEl.querySelector('span') || labelEl;
      label = stripColon(span.innerText || span.textContent || '');
    }
    if (!label) continue;
    const valueRoot = row.querySelector('.col-8') || row;
    const mail = valueRoot.querySelector('a[href^="mailto:"]');
    let value = '';
    if (mail) value = clean(mail.innerText || mail.getAttribute('href') || '');
    else value = clean(valueRoot.innerText || '');
    out[label] = value;
  }

  // Named fallbacks if label scrape missed anything.
  const named = [
    ['Civilité', '#ctl00_placeHolderContenuFormSansOnglet_ucCiviliteData_lbItemData'],
    ['Identité', '#ctl00_placeHolderContenuFormSansOnglet_lbIdentiteData'],
    ['Téléphone professionnel', '#ctl00_placeHolderContenuFormSansOnglet_lbTelBureauData'],
    ['Courriel professionnel', '#ctl00_placeHolderContenuFormSansOnglet_ucEmailProData_lbCourrielData'],
    ['Fax', '#ctl00_placeHolderContenuFormSansOnglet_lbFaxData'],
    ['Type de fonction', '#ctl00_placeHolderContenuFormSansOnglet_lbTypePersonnelData'],
  ];
  for (const [key, sel] of named) {
    if (out[key]) continue;
    const el = document.querySelector(sel);
    if (!el) continue;
    const mail = el.querySelector('a[href^="mailto:"]');
    out[key] = clean(mail ? mail.innerText : el.innerText);
  }
  return out;
}
"""


def scroll_vacations_to_end(
    page: Page,
    *,
    max_rounds: int = 80,
    settle_seconds: float = 0.35,
) -> int:
    """Scroll #divContainerVacations to the bottom until event count stabilizes."""
    last_count = -1
    stable = 0
    final_count = 0
    for round_i in range(max_rounds):
        info = page.evaluate(
            """(sel) => {
              const el = document.querySelector(sel);
              if (!el) return null;
              el.scrollTop = el.scrollHeight;
              return {
                scrollTop: el.scrollTop,
                scrollHeight: el.scrollHeight,
                clientHeight: el.clientHeight,
                count: el.querySelectorAll('[id$="_divEvent"]').length,
              };
            }""",
            CONTAINER_SELECTOR,
        )
        if not info:
            logger.warning("Vacation container missing during scroll")
            return 0
        count = int(info.get("count") or 0)
        final_count = count
        at_bottom = (
            int(info.get("scrollTop") or 0)
            + int(info.get("clientHeight") or 0)
            >= int(info.get("scrollHeight") or 0) - 2
        )
        if count == last_count and at_bottom:
            stable += 1
            if stable >= 3:
                logger.info(
                    "Vacation scroll complete | rounds=%s count=%s",
                    round_i + 1,
                    count,
                )
                break
        else:
            stable = 0
            last_count = count
        sleep(settle_seconds)
    else:
        logger.info(
            "Vacation scroll hit max rounds | count=%s",
            final_count,
        )
    return final_count


def extract_vacation_events(page: Page) -> list[dict[str, Any]]:
    raw = page.evaluate(_EXTRACT_JS)
    if not isinstance(raw, list):
        return []
    records: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("event_tag") or "").strip()
        if not tag:
            continue
        records.append(
            {
                "event_tag": tag,
                "ctl_index": item.get("ctl_index"),
                "css_class": str(item.get("css_class") or ""),
                "data_moment": str(item.get("data_moment") or ""),
                "title": str(item.get("title") or ""),
                "arrivee_depart": str(item.get("arrivee_depart") or ""),
                "personne": str(item.get("personne") or ""),
                "personne_id": str(item.get("personne_id") or ""),
                "personne_filtre_key": str(item.get("personne_filtre_key") or ""),
                "etablissement": str(item.get("etablissement") or ""),
                "etablissement_id": str(item.get("etablissement_id") or ""),
                "realise_par": str(item.get("realise_par") or ""),
                "ressource_fonction_id": str(item.get("ressource_fonction_id") or ""),
                "lieu": str(item.get("lieu") or ""),
                "is_canceled": int(item.get("is_canceled") or 0),
                "ressource_detail": {},
            }
        )
    return records


def _scroll_event_into_view(page: Page, event_tag: str) -> None:
    page.evaluate(
        """({sel, tag}) => {
          const root = document.querySelector(sel);
          if (!root) return;
          const card = root.querySelector('[tag="' + tag + '"]');
          if (!card) return;
          card.scrollIntoView({ block: 'center', inline: 'nearest' });
        }""",
        {"sel": CONTAINER_SELECTOR, "tag": event_tag},
    )
    sleep(0.15)


def _ressource_link_locator(page: Page, event_tag: str):
    return page.locator(
        f'{CONTAINER_SELECTOR} [tag="{event_tag}"] '
        f'a[id$="{RESSOURCE_LINK_SUFFIX}"]'
    ).first


def _close_ressource_dialog(page: Page, timeout_ms: int) -> None:
    close = page.locator(DIALOG_CLOSE).first
    if close.count() > 0:
        try:
            close.click(force=True, timeout=min(5_000, timeout_ms))
        except Exception:
            page.keyboard.press("Escape")
    else:
        page.keyboard.press("Escape")
    try:
        page.locator(DIALOG_VISIBLE).first.wait_for(
            state="hidden",
            timeout=min(10_000, timeout_ms),
        )
    except PlaywrightTimeoutError:
        page.evaluate(
            """() => {
              document.querySelectorAll('.ui-dialog').forEach((el) => {
                el.style.display = 'none';
              });
              document.querySelectorAll('.ui-widget-overlay').forEach((el) => {
                el.remove();
              });
            }"""
        )
    sleep(0.2)


def _extract_detail_from_open_dialog(page: Page, timeout_ms: int) -> dict[str, Any]:
    """Read key/values from the modal iframe (or dialog DOM fallback)."""
    page.locator(DIALOG_VISIBLE).first.wait_for(state="visible", timeout=timeout_ms)

    # Wait until identity field appears in any frame / main page.
    deadline_ms = timeout_ms
    step = 250
    waited = 0
    target_frame = None
    while waited <= deadline_ms:
        for frame in page.frames:
            try:
                if frame.locator(DETAIL_READY).count() > 0:
                    target_frame = frame
                    break
            except Exception:
                continue
        if target_frame is not None:
            break
        if page.locator(DETAIL_READY).count() > 0:
            break
        sleep(step / 1000)
        waited += step

    if target_frame is not None:
        try:
            target_frame.locator(DETAIL_READY).first.wait_for(
                state="visible",
                timeout=min(5_000, timeout_ms),
            )
        except PlaywrightTimeoutError:
            pass
        raw = target_frame.evaluate(_DETAIL_EXTRACT_JS)
    else:
        page.locator(DETAIL_READY).first.wait_for(
            state="visible",
            timeout=min(8_000, timeout_ms),
        )
        raw = page.evaluate(_DETAIL_EXTRACT_JS)

    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) if v is not None else "" for k, v in raw.items()}


def open_and_scrape_ressource_detail(
    page: Page,
    event_tag: str,
    *,
    timeout_ms: int = 30_000,
) -> dict[str, Any]:
    """Click realise_par link for one card, scrape modal key/values, then close."""
    _scroll_event_into_view(page, event_tag)
    link = _ressource_link_locator(page, event_tag)
    if link.count() == 0:
        logger.warning("No ressource link for event_tag=%s", event_tag)
        return {}

    link.wait_for(state="visible", timeout=timeout_ms)
    link.click(force=True)

    try:
        return _extract_detail_from_open_dialog(page, timeout_ms)
    finally:
        _close_ressource_dialog(page, timeout_ms)


def enrich_with_ressource_details(
    page: Page,
    records: list[dict[str, Any]],
    *,
    timeout_ms: int = 30_000,
) -> list[dict[str, Any]]:
    """
    For each vacation card, open Détail de la ressource, collect key/values,
    close the dialog. Cache by ressource_fonction_id to avoid duplicate opens.
    """
    cache: dict[str, dict[str, Any]] = {}
    total = len(records)
    opened = 0
    for idx, rec in enumerate(records, start=1):
        tag = str(rec.get("event_tag") or "")
        fid = str(rec.get("ressource_fonction_id") or "").strip()
        name = str(rec.get("realise_par") or "")
        ctl = rec.get("ctl_index")
        cache_key = fid or (f"name:{name}" if name else "")

        if cache_key and cache_key in cache:
            rec["ressource_detail"] = dict(cache[cache_key])
            if fid:
                rec["ressource_fonction_id"] = fid
            print(
                f"Ressource detail {idx}/{total} cached "
                f"| ctl={ctl} tag={tag} | {name}",
                flush=True,
            )
            continue

        print(
            f"Ressource detail {idx}/{total} open "
            f"| ctl={ctl} tag={tag} | {name}",
            flush=True,
        )
        logger.info(
            "Opening ressource detail | idx=%s/%s ctl=%s tag=%s fid=%s name=%s",
            idx,
            total,
            ctl,
            tag,
            fid,
            name,
        )
        try:
            detail = open_and_scrape_ressource_detail(
                page,
                tag,
                timeout_ms=timeout_ms,
            )
            opened += 1
        except Exception as exc:
            logger.warning(
                "Ressource detail failed | tag=%s reason=%s",
                tag,
                exc,
            )
            print(f"  ! failed for ctl={ctl}: {exc}", flush=True)
            try:
                _close_ressource_dialog(page, timeout_ms)
            except Exception:
                pass
            detail = {}

        if detail.get("_fonction_id"):
            rec["ressource_fonction_id"] = str(detail["_fonction_id"])
            fid = rec["ressource_fonction_id"]
        elif fid:
            rec["ressource_fonction_id"] = fid

        store_key = fid or (f"name:{name}" if name else tag)
        if store_key and detail:
            cache[store_key] = detail
            # Also alias by name so later cards with same label hit cache.
            if name:
                cache.setdefault(f"name:{name}", detail)

        rec["ressource_detail"] = detail

    logger.info(
        "Ressource details done | records=%s unique_opens=%s cache=%s",
        total,
        opened,
        len(cache),
    )
    print(
        f"Ressource details done: {total} records, {opened} modal opens "
        f"({len(cache)} unique keys)",
        flush=True,
    )
    return records


def read_agenda_date_from_page(page: Page) -> str:
    """Read selected agenda date from #ucChoixDeLaDate_VDCPeriodeData only."""
    raw = page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          if (!el) return { source: null, value: '' };
          const selected = (el.getAttribute('selectedvalue') || '').trim();
          const text = (el.textContent || '').replace(/\\s+/g, ' ').trim();
          return {
            source: sel,
            value: selected || text,
            selectedvalue: selected,
            text: text,
          };
        }""",
        AGENDA_DATE_SELECTOR,
    )
    value = ""
    source = None
    if isinstance(raw, dict):
        value = str(raw.get("value") or "").strip()
        source = raw.get("source")
    if not value:
        raise RuntimeError(
            "Selected agenda date not found on page "
            f"(expected {AGENDA_DATE_SELECTOR}[selectedvalue])"
        )
    normalized = _normalize_agenda_date(value)
    if not normalized:
        raise RuntimeError(
            f"Could not normalize agenda date from page value {value!r} "
            f"(source={source})"
        )
    logger.info(
        "Agenda date from page | source=%s raw=%s normalized=%s",
        source,
        value,
        normalized,
    )
    return normalized


def _normalize_agenda_date(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    # DD/MM/YYYY
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", text)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    # YYYY-MM-DD or YYYY/MM/DD
    m = re.fullmatch(r"(\d{4})[-/](\d{2})[-/](\d{2})", text)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    # YYYYMMDD
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", text)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    # DD-MM-YYYY
    m = re.fullmatch(r"(\d{2})-(\d{2})-(\d{4})", text)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return None


def scrape_and_store_vacations(
    page: Page,
    *,
    db_path: Path | None = None,
    json_path: Path | None = None,
    import_json_path: Path | None = None,
    agenda_code: str = "BRESSUIRE",
    agenda_label: str | None = None,
    agenda_date: str | None = None,
    display_name: str | None = None,
    timeout_ms: int = 30_000,
) -> tuple[int, Path, Path, Path]:
    """Scrape cards, save raw JSONL + Backend agenda-import JSON (same stamp)."""
    path = db_path or default_db_path()
    if json_path is None or import_json_path is None:
        _, paired_jsonl, paired_import = paired_run_output_paths()
        out_json = json_path or paired_jsonl
        out_import = import_json_path or paired_import
    else:
        out_json = json_path
        out_import = import_json_path

    label = (agenda_label or agenda_code or "").strip() or agenda_code
    selected_date = (agenda_date or "").strip() or read_agenda_date_from_page(page)

    logger.info("Waiting for vacation container | selector=%s", CONTAINER_SELECTOR)
    print(f"Waiting for {CONTAINER_SELECTOR}...", flush=True)
    try:
        page.locator(CONTAINER_SELECTOR).first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(
            f"Vacation container not found: {CONTAINER_SELECTOR}"
        ) from exc

    count_scrolled = scroll_vacations_to_end(page)
    print(f"Scrolled File d'attente to end ({count_scrolled} cards in DOM)", flush=True)

    records = extract_vacation_events(page)
    print(f"Extracted {len(records)} vacation cards from DOM", flush=True)

    enrich_with_ressource_details(page, records, timeout_ms=timeout_ms)

    saved = upsert_events(records, db_path=path)
    print(f"Saved {saved} vacation events -> {path}", flush=True)
    json_out = export_events_jsonl(records, db_path=path, json_path=out_json)
    print(f"Exported JSONL ({saved} lines) -> {json_out}", flush=True)

    payload, warnings = build_import_payload(
        records,
        agenda_code=agenda_code,
        agenda_label=label,
        agenda_date=selected_date,
        display_name=display_name,
    )
    for warning in warnings:
        logger.warning("Formatter warning | %s", warning)
        print(f"Formatter WARN: {warning}", flush=True)
    import_out = write_import_payload(payload, path=out_import)
    print(
        f"Exported agenda-import ({len(payload['appointments'])} appointments, "
        f"{len(payload['resources'])} resources) -> {import_out}",
        flush=True,
    )
    logger.info(
        "Vacations scraped | dom=%s saved=%s db=%s json=%s import=%s date=%s",
        count_scrolled,
        saved,
        path,
        json_out,
        import_out,
        selected_date,
    )
    return saved, path, json_out, import_out
