"""Scrape File d'attente cards from #divContainerVacations into SQLite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from feature.agendas.vacations_db import default_db_path, upsert_events
from utils.logger import get_logger
from utils.timing import sleep

logger = get_logger("scrape_vacations")

CONTAINER_SELECTOR = "#divContainerVacations"

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
      lieu: clean(lieuEl ? lieuEl.innerText : ''),
      is_canceled: el.classList.contains('Canceled') ? 1 : 0,
    };
  });
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
                "lieu": str(item.get("lieu") or ""),
                "is_canceled": int(item.get("is_canceled") or 0),
            }
        )
    return records


def scrape_and_store_vacations(
    page: Page,
    *,
    db_path: Path | None = None,
    timeout_ms: int = 30_000,
) -> tuple[int, Path]:
    """Wait for list, scroll to end, extract all cards, save to SQLite."""
    path = db_path or default_db_path()
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
    saved = upsert_events(records, db_path=path)
    print(f"Saved {saved} vacation events -> {path}", flush=True)
    logger.info(
        "Vacations scraped | dom=%s saved=%s db=%s",
        count_scrolled,
        saved,
        path,
    )
    return saved, path
