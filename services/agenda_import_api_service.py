"""Upload agenda-import JSON to Backend POST /api/internal/imports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from utils.logger import get_logger

logger = get_logger("agenda_import_api")

LOGIN_PATH = "/api/auth/login"
IMPORT_PATH = "/api/internal/imports"


class AgendaImportApiError(RuntimeError):
    """Raised when login or import upload fails."""


@dataclass(frozen=True)
class AgendaImportApiResult:
    import_id: str
    partial: bool
    warning_count: int
    summary: dict[str, Any]
    record_errors: list[Any]
    raw: dict[str, Any]


class AgendaImportApiService:
    """Login as UEGAR BOT SERVICE_ACCOUNT, then POST agenda-import JSON."""

    def __init__(
        self,
        *,
        base_url: str,
        bot_email: str,
        bot_password: str,
        timeout_seconds: float = 120.0,
        enabled: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._bot_email = bot_email.strip()
        self._bot_password = bot_password
        self._timeout = timeout_seconds
        self._enabled = enabled
        self._session = requests.Session()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def upload_file(self, json_path: Path) -> AgendaImportApiResult | None:
        if not self._enabled:
            logger.info("Agenda import API upload skipped | enabled=False")
            print("Agenda import API upload skipped (BACKEND_IMPORT_ENABLED=false)", flush=True)
            return None
        if not json_path.is_file():
            raise AgendaImportApiError(f"Import JSON not found: {json_path}")
        token = self._login()
        return self._post_import(json_path, token)

    def _login(self) -> str:
        url = f"{self._base_url}{LOGIN_PATH}"
        logger.info("Backend BOT login | url=%s email=%s", url, self._bot_email)
        print(f"Backend login: {self._bot_email} @ {self._base_url}", flush=True)
        try:
            response = self._session.post(
                url,
                json={"email": self._bot_email, "password": self._bot_password},
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise AgendaImportApiError(f"Backend login request failed: {exc}") from exc

        if response.status_code != 200:
            raise AgendaImportApiError(
                f"Backend login failed HTTP {response.status_code}: {response.text[:500]}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise AgendaImportApiError("Backend login returned non-JSON") from exc
        if not body.get("success"):
            err = body.get("error") or {}
            raise AgendaImportApiError(
                f"Backend login rejected: {err.get('code')} {err.get('message')}"
            )
        token = ((body.get("data") or {}).get("accessToken") or "").strip()
        if not token:
            raise AgendaImportApiError("Backend login missing accessToken")
        logger.info("Backend BOT login OK")
        return token

    def _post_import(self, json_path: Path, access_token: str) -> AgendaImportApiResult:
        url = f"{self._base_url}{IMPORT_PATH}"
        raw = json_path.read_bytes()
        logger.info(
            "Uploading agenda-import JSON | url=%s path=%s bytes=%s",
            url,
            json_path,
            len(raw),
        )
        print(f"Uploading agenda-import JSON ({len(raw)} bytes) -> {url}", flush=True)
        try:
            response = self._session.post(
                url,
                data=raw,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise AgendaImportApiError(f"Agenda import upload failed: {exc}") from exc

        if response.status_code != 200:
            raise AgendaImportApiError(
                f"Agenda import failed HTTP {response.status_code}: {response.text[:800]}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise AgendaImportApiError("Agenda import returned non-JSON") from exc
        if not body.get("success"):
            err = body.get("error") or {}
            raise AgendaImportApiError(
                f"Agenda import rejected: {err.get('code')} {err.get('message')}"
            )
        data = body.get("data") or {}
        result = AgendaImportApiResult(
            import_id=str(data.get("importId") or ""),
            partial=bool(data.get("partial")),
            warning_count=int(data.get("warningCount") or 0),
            summary=dict(data.get("summary") or {}),
            record_errors=list(data.get("recordErrors") or []),
            raw=body,
        )
        logger.info(
            "Agenda import OK | importId=%s partial=%s warnings=%s summary=%s",
            result.import_id,
            result.partial,
            result.warning_count,
            result.summary,
        )
        print(
            f"Agenda import OK | importId={result.import_id} "
            f"summary={json.dumps(result.summary, ensure_ascii=False)}",
            flush=True,
        )
        return result
