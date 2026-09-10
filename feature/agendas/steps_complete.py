"""Verify and complete Agendas steps B1 / B2 / B3.

B1: Agenda multi-ressources = BRESSUIRE
B2: Ressource = Tout sélectionner (all resources)
B3: Vue = File d'attente

Also requires #glyphBtnFonctionnaliteEnCours.prev-calendar to be visible.

Returns True only when all three steps are done and the glyph is rendered.
If any step is missing, completes it and re-checks until success or attempts exhausted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from feature.agendas.agendas import UegarAgendasFeature

logger = get_logger("agendas.steps")

GLYPH_SELECTOR = "#glyphBtnFonctionnaliteEnCours.prev-calendar"


@dataclass(frozen=True)
class AgendasStepsStatus:
    b1_planning: bool
    b2_ressource: bool
    b3_vue: bool
    glyph_ready: bool

    @property
    def all_complete(self) -> bool:
        return (
            self.b1_planning
            and self.b2_ressource
            and self.b3_vue
            and self.glyph_ready
        )


def check_agendas_steps_status(feature: UegarAgendasFeature) -> AgendasStepsStatus:
    """Read-only check of B1/B2/B3 + calendar glyph."""
    return AgendasStepsStatus(
        b1_planning=feature.is_step1_planning_done(),
        b2_ressource=feature.is_step2_ressource_done(),
        b3_vue=feature.is_step3_vue_done(),
        glyph_ready=feature.is_calendar_glyph_ready(),
    )


def ensure_agendas_steps_complete(
    feature: UegarAgendasFeature,
    *,
    max_rounds: int = 3,
) -> bool:
    """Ensure B1+B2+B3+glyph are complete; retry missing steps. Returns bool."""
    for round_idx in range(1, max_rounds + 1):
        status = check_agendas_steps_status(feature)
        logger.info(
            "Agendas steps check | round=%s/%s b1=%s b2=%s b3=%s glyph=%s",
            round_idx,
            max_rounds,
            status.b1_planning,
            status.b2_ressource,
            status.b3_vue,
            status.glyph_ready,
        )
        print(
            f"Steps check round {round_idx}/{max_rounds}: "
            f"B1={status.b1_planning} B2={status.b2_ressource} "
            f"B3={status.b3_vue} glyph={status.glyph_ready}",
            flush=True,
        )
        if status.all_complete:
            logger.info("Agendas steps B1/B2/B3 complete")
            print("Agendas steps B1/B2/B3 complete", flush=True)
            return True

        if not status.b1_planning:
            print("Completing B1 (BRESSUIRE)...", flush=True)
            feature.ensure_step1_planning()
        if not status.b2_ressource:
            print("Completing B2 (Tout sélectionner)...", flush=True)
            feature.ensure_step2_ressource()
        if not status.b3_vue:
            print("Completing B3 (File d'attente)...", flush=True)
            feature.ensure_step3_vue()
        if not feature.is_calendar_glyph_ready():
            print("Waiting for calendar glyph...", flush=True)
            feature.wait_for_calendar_glyph()

    final = check_agendas_steps_status(feature)
    logger.info(
        "Agendas steps final | b1=%s b2=%s b3=%s glyph=%s all=%s",
        final.b1_planning,
        final.b2_ressource,
        final.b3_vue,
        final.glyph_ready,
        final.all_complete,
    )
    print(
        f"Steps final: B1={final.b1_planning} B2={final.b2_ressource} "
        f"B3={final.b3_vue} glyph={final.glyph_ready} -> {final.all_complete}",
        flush=True,
    )
    return final.all_complete
