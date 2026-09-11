"""Open Agendas from the left palette after login.

Flow:
1. Wait for #repeaterPalette_ctl01_btnDiv.
2. Screenshot before click.
3. Click Agendas and wait until page finished loading.
4. Screenshot after Agendas load.
5. Step 1: ensure planning dropdown is BRESSUIRE, wait calendar glyph, screenshot.
6. Step 2: ensure Ressource "Tout sélectionner" is checked, wait calendar glyph,
   screenshot.
7. Step 3: ensure view is "File d'attente", wait calendar glyph, screenshot.
8. When B1/B2/B3 complete: scrape vacations → SQLite + raw JSONL + agenda-import JSON.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config.settings import Settings
from utils.logger import get_logger
from utils.timing import sleep

logger = get_logger("agendas")


class AgendasNavigationError(RuntimeError):
    """Raised when Agendas cannot be opened."""


class UegarAgendasFeature:
    def __init__(
        self,
        page: Page,
        settings: Settings,
        screenshot: Callable[..., Path],
        action_pause: Callable[[], None] | None = None,
    ) -> None:
        self._page = page
        self._settings = settings
        self._screenshot = screenshot
        self._action_pause = action_pause or (lambda: None)
        self._timeout_ms = int(settings.browser.ready_timeout_ms)
        after = settings.login.after_login
        if after.agendas is None:
            raise AgendasNavigationError("after_login.agendas is not configured")
        self._agendas = after.agendas
        self._loading = after.loading_hidden_selector

    def run(
        self, stem_prefix: str = "uegar"
    ) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
        button = self._agendas.button
        logger.info("Waiting for Agendas button | selector=%s", button)
        print(f"Waiting for Agendas: {button}...", flush=True)
        try:
            self._page.locator(button).first.wait_for(
                state="visible",
                timeout=self._timeout_ms,
            )
        except PlaywrightTimeoutError as exc:
            raise AgendasNavigationError(
                f"Agendas button not found: {button}"
            ) from exc

        before = self._screenshot(
            f"{stem_prefix}_before_agendas",
            wait_ready=False,
            settle_seconds=0.5,
        )
        print(f"Before-Agendas screenshot: {before}", flush=True)
        logger.info("Before-Agendas screenshot | path=%s", before)

        self._action_pause()
        logger.info("Clicking Agendas")
        print("Clicking Agendas...", flush=True)
        try:
            self._page.locator(button).first.click()
        except Exception as exc:
            raise AgendasNavigationError(f"Failed to click Agendas: {exc}") from exc

        self._wait_agendas_loaded()

        after = self._screenshot(
            f"{stem_prefix}_after_agendas",
            wait_ready=False,
            settle_seconds=0.5,
        )
        print(f"After-Agendas screenshot: {after}", flush=True)
        logger.info("After-Agendas screenshot | path=%s", after)

        self._ensure_planning_bressuire()
        planning = self._screenshot(
            f"{stem_prefix}_after_planning_bressuire",
            wait_ready=False,
            settle_seconds=0.5,
        )
        print(f"After-BRESSUIRE screenshot: {planning}", flush=True)
        logger.info("After-BRESSUIRE screenshot | path=%s", planning)

        self._ensure_ressource_select_all()
        ressource = self._screenshot(
            f"{stem_prefix}_after_ressource_all",
            wait_ready=False,
            settle_seconds=0.5,
        )
        print(f"After-Ressource-All screenshot: {ressource}", flush=True)
        logger.info("After-Ressource-All screenshot | path=%s", ressource)

        self._ensure_vue_file_attente()
        vue = self._screenshot(
            f"{stem_prefix}_after_vue_file_attente",
            wait_ready=False,
            settle_seconds=0.5,
        )
        print(f"After-File-d'attente screenshot: {vue}", flush=True)
        logger.info("After-File-d'attente screenshot | path=%s", vue)

        from feature.agendas.scrape_vacations import scrape_and_store_vacations
        from feature.agendas.steps_complete import ensure_agendas_steps_complete

        if not ensure_agendas_steps_complete(self):
            raise AgendasNavigationError(
                "Agendas steps B1/B2/B3 (or calendar glyph) not complete"
            )

        try:
            planning_cfg = self._agendas.planning
            agenda_label = (
                planning_cfg.option_label if planning_cfg is not None else "BRESSUIRE"
            )
            saved, db_path, json_path, import_path = scrape_and_store_vacations(
                self._page,
                timeout_ms=self._timeout_ms,
                agenda_code=agenda_label,
                agenda_label=agenda_label,
            )
        except RuntimeError as exc:
            raise AgendasNavigationError(str(exc)) from exc
        logger.info(
            "Vacations stored after steps complete | saved=%s db=%s json=%s import=%s",
            saved,
            db_path,
            json_path,
            import_path,
        )
        return before, after, planning, ressource, vue, db_path, json_path, import_path

    def is_step1_planning_done(self) -> bool:
        planning = self._agendas.planning
        if planning is None:
            return False
        return self._is_planning_selected(
            planning.option,
            planning.selected_value,
            planning.option_label,
            control_id="DDLChoixPlanningData",
        )

    def is_step2_ressource_done(self) -> bool:
        ressource = self._agendas.ressource
        if ressource is None:
            return False
        if self._is_ressource_select_all_checked(ressource.select_all):
            return True
        # Button often shows "N éléments sélectionnés" when all are selected.
        try:
            btn = self._page.locator(ressource.dropdown_button).first
            text = (btn.inner_text() or btn.get_attribute("valtitle") or "").casefold()
            normalized = (
                text.replace("é", "e")
                .replace("è", "e")
                .replace("ê", "e")
            )
            if "elements selectionnes" in normalized:
                return True
        except Exception:
            pass
        try:
            hidden = self._page.locator(
                "#DDLChoixRessourceMultipleData_hiddenFieldSelectedValues"
            )
            if hidden.count():
                value = hidden.first.get_attribute("value") or ""
                # All selected => multiple GUIDs separated by comma/semicolon.
                parts = [p for p in value.replace(";", ",").split(",") if p.strip()]
                if len(parts) > 1:
                    return True
        except Exception:
            pass
        return False

    def is_step3_vue_done(self) -> bool:
        vue = self._agendas.vue
        if vue is None:
            return False
        return self._is_planning_selected(
            vue.option,
            vue.selected_value,
            vue.option_label,
            control_id="ucChoixDesVues_DDLChoixVue",
        )

    def is_calendar_glyph_ready(self) -> bool:
        try:
            loc = self._page.locator(
                "#glyphBtnFonctionnaliteEnCours.prev-calendar"
            ).first
            return loc.is_visible()
        except Exception:
            return False

    def ensure_step1_planning(self) -> None:
        self._ensure_planning_bressuire()

    def ensure_step2_ressource(self) -> None:
        self._ensure_ressource_select_all()

    def ensure_step3_vue(self) -> None:
        self._ensure_vue_file_attente()

    def wait_for_calendar_glyph(self) -> None:
        ready = "#glyphBtnFonctionnaliteEnCours.prev-calendar"
        if self._agendas.vue is not None:
            ready = self._agendas.vue.ready_after_select
        elif self._agendas.planning is not None:
            ready = self._agendas.planning.ready_after_select
        self._wait_for_calendar_ready(ready, context="glyph")

    def _ensure_planning_bressuire(self) -> None:
        planning = self._agendas.planning
        if planning is None:
            raise AgendasNavigationError("after_login.agendas.planning is not configured")

        label = planning.option_label
        logger.info("Step1 planning dropdown | want=%s", label)
        print(f"Step1: checking planning selection: {label}...", flush=True)

        if self._is_planning_selected(
            planning.option,
            planning.selected_value,
            label,
            control_id="DDLChoixPlanningData",
        ):
            logger.info("Planning already selected | label=%s", label)
            print(f"Already selected: {label}", flush=True)
        else:
            self._select_dropdown_option(planning.dropdown_button, planning.option)

        self._wait_for_calendar_ready(planning.ready_after_select, context="planning")

    def _ensure_vue_file_attente(self) -> None:
        vue = self._agendas.vue
        if vue is None:
            raise AgendasNavigationError("after_login.agendas.vue is not configured")

        label = vue.option_label
        logger.info("Step3 vue dropdown | want=%s", label)
        print(f"Step3: checking vue selection: {label}...", flush=True)
        self._close_open_dropdowns()

        if self._is_planning_selected(
            vue.option,
            vue.selected_value,
            label,
            control_id="ucChoixDesVues_DDLChoixVue",
        ):
            logger.info("Vue already selected | label=%s", label)
            print(f"Already selected: {label}", flush=True)
        else:
            self._select_dropdown_option(vue.dropdown_button, vue.option)

        self._wait_for_calendar_ready(vue.ready_after_select, context="vue")

    def _close_open_dropdowns(self) -> None:
        """Dismiss tooltips / panels that otherwise intercept later clicks."""
        try:
            self._page.keyboard.press("Escape")
            sleep(0.2)
            self._page.keyboard.press("Escape")
            sleep(0.2)
        except Exception:
            pass
        try:
            self._page.evaluate(
                """() => {
                  const tip = document.getElementById('divToolTip');
                  if (tip) {
                    tip.style.display = 'none';
                    tip.style.pointerEvents = 'none';
                  }
                }"""
            )
        except Exception:
            pass

    def _ensure_ressource_select_all(self) -> None:
        ressource = self._agendas.ressource
        if ressource is None:
            raise AgendasNavigationError(
                "after_login.agendas.ressource is not configured"
            )

        logger.info("Step2 ressource dropdown | select_all=%s", ressource.select_all)
        print("Step2: checking Ressource 'Tout sélectionner'...", flush=True)

        if self._is_ressource_select_all_checked(ressource.select_all):
            logger.info("Ressource 'Tout sélectionner' already checked")
            print("Already selected: Tout sélectionner", flush=True)
        else:
            self._check_ressource_select_all(
                ressource.dropdown_button,
                ressource.select_all,
            )
            # Site debounces ressource change by ~1000ms.
            sleep(max(1.0, float(ressource.change_debounce_seconds)))

        self._wait_for_calendar_ready(
            ressource.ready_after_select,
            context="ressource",
        )
        self._close_open_dropdowns()

    def _is_ressource_select_all_checked(self, select_all: str) -> bool:
        try:
            box = self._page.locator(select_all).first
            if self._page.locator(select_all).count() == 0:
                return False
            if box.is_checked():
                return True
        except Exception:
            pass
        # Fallback: every item checkbox under the list is checked.
        try:
            item_boxes = self._page.locator(
                "input[id^='DDLChoixRessourceMultipleData_ctl'][id$='_chkSelectionner']"
            )
            total = item_boxes.count()
            if total == 0:
                return False
            checked = 0
            for i in range(total):
                if item_boxes.nth(i).is_checked():
                    checked += 1
            return checked == total
        except Exception:
            return False

    def _check_ressource_select_all(self, dropdown_button: str, select_all: str) -> None:
        timeout = self._timeout_ms
        logger.info("Opening ressource dropdown | button=%s", dropdown_button)
        print("Opening Ressource dropdown...", flush=True)
        try:
            self._page.locator(dropdown_button).first.wait_for(
                state="visible",
                timeout=timeout,
            )
            self._action_pause()
            self._page.locator(dropdown_button).first.click()
            box = self._page.locator(select_all).first
            box.wait_for(state="visible", timeout=timeout)
            self._action_pause()
            if box.is_checked():
                logger.info("Tout sélectionner already checked after open")
                print("Tout sélectionner already checked", flush=True)
                self._close_open_dropdowns()
                return
            logger.info("Checking Tout sélectionner | selector=%s", select_all)
            print("Checking Tout sélectionner...", flush=True)
            # Tooltips can sit on top of the checkbox and block pointer events.
            self._page.evaluate(
                """() => {
                  const tip = document.getElementById('divToolTip');
                  if (tip) {
                    tip.style.display = 'none';
                    tip.style.pointerEvents = 'none';
                  }
                }"""
            )
            # Prefer label click (custom checkbox UI); force bypasses leftover overlays.
            label = self._page.locator(
                "label[for='DDLChoixRessourceMultipleData_chkAll']"
            )
            if label.count() > 0:
                label.first.click(force=True)
            else:
                box.check(force=True)
            # Toggle the same button to close the multi-select panel.
            try:
                self._page.locator(dropdown_button).first.click(force=True)
            except Exception:
                pass
            self._close_open_dropdowns()
        except PlaywrightTimeoutError as exc:
            raise AgendasNavigationError(
                f"Could not check Ressource select-all: {exc}"
            ) from exc
        except Exception as exc:
            raise AgendasNavigationError(
                f"Ressource dropdown interaction failed: {exc}"
            ) from exc

    def _is_planning_selected(
        self,
        option_selector: str,
        selected_value: str,
        label: str,
        *,
        control_id: str,
    ) -> bool:
        try:
            option = self._page.locator(option_selector)
            if option.count() > 0:
                first = option.first
                if first.get_attribute("selected") in {"true", "selected"} or (
                    "SelectedItem" in (first.get_attribute("class") or "")
                ):
                    return True
                if first.get_attribute("valeur") == selected_value and (
                    "SelectedItem" in (first.get_attribute("class") or "")
                ):
                    return True
        except Exception:
            pass
        try:
            hidden = self._page.locator(f"#{control_id}")
            if hidden.count() and hidden.first.get_attribute("value") == selected_value:
                return True
        except Exception:
            pass
        try:
            btn = self._page.locator(
                f'button.drop-down[control-id="{control_id}"]'
            ).first
            selected = (btn.get_attribute("selectedvalue") or "").strip()
            if selected == selected_value:
                return True
            title = (btn.get_attribute("valtitle") or btn.inner_text() or "").strip()
            # valtitle may contain HTML icons; match plain label text.
            if label.casefold() in title.casefold().replace("&lt;", "<").replace(
                "&gt;", ">"
            ):
                return True
            if label.casefold() in (btn.inner_text() or "").casefold():
                return True
        except Exception:
            pass
        return False

    def _select_dropdown_option(self, dropdown_button: str, option: str) -> None:
        timeout = self._timeout_ms
        logger.info("Opening dropdown | button=%s", dropdown_button)
        print("Opening dropdown...", flush=True)
        try:
            self._close_open_dropdowns()
            btn = self._page.locator(dropdown_button).first
            btn.wait_for(state="visible", timeout=timeout)
            self._action_pause()
            control_id = (btn.get_attribute("control-id") or "").strip()
            # Prefer site API so overlays cannot block opening the list.
            opened = False
            if control_id:
                opened = bool(
                    self._page.evaluate(
                        """(cid) => {
                          if (typeof __ValDropDownList_DropDown === 'function') {
                            __ValDropDownList_DropDown(cid);
                            return true;
                          }
                          return false;
                        }""",
                        control_id,
                    )
                )
            if not opened:
                btn.click(force=True)

            option_loc = self._page.locator(option).first
            try:
                option_loc.wait_for(state="visible", timeout=min(15000, timeout))
            except PlaywrightTimeoutError:
                # List stayed hidden; select via site handler on attached node.
                if control_id:
                    selected = self._page.evaluate(
                        """({ optionId, cid }) => {
                          const el = document.getElementById(optionId);
                          if (!el) return false;
                          if (typeof __ValDropDownList_SelectItem === 'function') {
                            __ValDropDownList_SelectItem(el, cid);
                            return true;
                          }
                          el.click();
                          return true;
                        }""",
                        {
                            "optionId": option.lstrip("#"),
                            "cid": control_id,
                        },
                    )
                    if selected:
                        logger.info(
                            "Selected dropdown option via JS API | selector=%s",
                            option,
                        )
                        print(f"Selecting {option} (JS)...", flush=True)
                        return
                raise

            self._action_pause()
            logger.info("Selecting dropdown option | selector=%s", option)
            print(f"Selecting {option}...", flush=True)
            option_loc.click(force=True)
        except PlaywrightTimeoutError as exc:
            raise AgendasNavigationError(
                f"Could not select dropdown option {option}: {exc}"
            ) from exc
        except Exception as exc:
            raise AgendasNavigationError(
                f"Dropdown interaction failed: {exc}"
            ) from exc

    def _wait_for_calendar_ready(self, ready_selector: str, *, context: str) -> None:
        timeout = self._timeout_ms
        logger.info(
            "Waiting for calendar ready | context=%s ready=%s",
            context,
            ready_selector,
        )
        print(
            f"Waiting for {ready_selector} after {context}...",
            flush=True,
        )
        try:
            if self._loading and self._page.locator(self._loading).count() > 0:
                sleep(0.5)
                try:
                    self._page.locator(self._loading).first.wait_for(
                        state="hidden",
                        timeout=timeout,
                    )
                except PlaywrightTimeoutError:
                    pass
            self._page.locator(ready_selector).first.wait_for(
                state="visible",
                timeout=timeout,
            )
            poll = 0.5
            elapsed = 0.0
            max_wait = min(60.0, timeout / 1000.0)
            while elapsed < max_wait:
                spinner = self._page.locator(".typing-loader:visible")
                loading_vis = False
                if self._loading:
                    try:
                        loading_vis = self._page.locator(
                            self._loading
                        ).first.is_visible()
                    except Exception:
                        loading_vis = False
                if spinner.count() == 0 and not loading_vis:
                    break
                sleep(poll)
                elapsed += poll
        except PlaywrightTimeoutError as exc:
            raise AgendasNavigationError(
                f"{context} did not finish loading ({ready_selector}): {exc}"
            ) from exc
        logger.info("%s ready | url=%s", context, self._page.url)
        print(f"{context} ready: {self._page.url}", flush=True)

    def _wait_agendas_loaded(self) -> None:
        timeout = self._timeout_ms
        needle = self._agendas.url_contains
        ready = self._agendas.after_ready_selector
        logger.info(
            "Waiting for Agendas page | url_contains=%s ready=%s",
            needle,
            ready,
        )
        print("Waiting for Agendas page to load...", flush=True)
        try:
            if needle:
                try:
                    self._page.wait_for_url(f"**/*{needle}*", timeout=timeout)
                except PlaywrightTimeoutError:
                    pass

            if self._loading and self._page.locator(self._loading).count() > 0:
                sleep(0.5)
                self._page.locator(self._loading).first.wait_for(
                    state="hidden",
                    timeout=timeout,
                )

            self._page.locator(ready).first.wait_for(
                state="visible",
                timeout=timeout,
            )

            poll = 0.5
            elapsed = 0.0
            max_wait = timeout / 1000.0
            while elapsed < max_wait:
                selected = self._page.locator(
                    "#repeaterPalette_ctl01_btnDiv.SelectedItem"
                )
                title = ""
                try:
                    title = (
                        self._page.locator("#ctl00_lbTitreFonctionnalite").inner_text()
                        or ""
                    ).strip()
                except Exception:
                    pass
                spinner = self._page.locator(".typing-loader:visible")
                loading_vis = False
                if self._loading:
                    try:
                        loading_vis = self._page.locator(self._loading).first.is_visible()
                    except Exception:
                        loading_vis = False
                planning_label = self._page.locator("#lbChoixPlanning")
                if (
                    (
                        selected.count() > 0
                        or "agenda" in title.lower()
                        or planning_label.count() > 0
                    )
                    and spinner.count() == 0
                    and not loading_vis
                ):
                    break
                sleep(poll)
                elapsed += poll
            else:
                raise PlaywrightTimeoutError("Agendas page still loading")
        except PlaywrightTimeoutError as exc:
            raise AgendasNavigationError(
                f"Agendas page did not finish loading: {exc}"
            ) from exc
        logger.info("Agendas page ready | url=%s", self._page.url)
        print(f"Agendas ready: {self._page.url}", flush=True)
