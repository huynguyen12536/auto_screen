"""Upload agenda-import JSON to Backend POST /api/internal/imports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from utils.logger import get_logger
from utils.paths import DATA_DIR, ensure_runtime_dirs

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
    response_path: Path | None = None


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

        response: requests.Response | None = None
        request_error: str | None = None
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
            request_error = str(exc)

        response_path = self._write_response_file(
            json_path=json_path,
            url=url,
            response=response,
            request_error=request_error,
        )
        self._print_response(response, response_path, request_error)

        if request_error is not None:
            raise AgendaImportApiError(
                f"Agenda import upload failed: {request_error} "
                f"(response saved: {response_path})"
            )
        assert response is not None

        body, body_text = self._parse_body(response)
        if response.status_code != 200:
            raise AgendaImportApiError(
                f"Agenda import failed HTTP {response.status_code}: "
                f"{(body_text or str(body))[:800]} "
                f"(response saved: {response_path})"
            )
        if not isinstance(body, dict):
            raise AgendaImportApiError(
                f"Agenda import returned non-JSON (response saved: {response_path})"
            )
        if not body.get("success"):
            err = body.get("error") or {}
            raise AgendaImportApiError(
                f"Agenda import rejected: {err.get('code')} {err.get('message')} "
                f"(response saved: {response_path})"
            )

        data = body.get("data") or {}
        result = AgendaImportApiResult(
            import_id=str(data.get("importId") or ""),
            partial=bool(data.get("partial")),
            warning_count=int(data.get("warningCount") or 0),
            summary=dict(data.get("summary") or {}),
            record_errors=list(data.get("recordErrors") or []),
            raw=body,
            response_path=response_path,
        )
        logger.info(
            "Agenda import OK | importId=%s partial=%s warnings=%s summary=%s response=%s",
            result.import_id,
            result.partial,
            result.warning_count,
            result.summary,
            response_path,
        )
        print(
            f"Agenda import OK | importId={result.import_id} "
            f"summary={json.dumps(result.summary, ensure_ascii=False)}",
            flush=True,
        )
        print(f"Backend import response file: {response_path}", flush=True)
        return result

    def _response_out_path(self, json_path: Path) -> Path:
        ensure_runtime_dirs()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = json_path.stem  # e.g. agenda-import_20260910_2315
        return DATA_DIR / f"{stem}.response_{stamp}.json"

    def _write_response_file(
        self,
        *,
        json_path: Path,
        url: str,
        response: requests.Response | None,
        request_error: str | None,
    ) -> Path:
        out = self._response_out_path(json_path)
        body, body_text = (None, None)
        if response is not None:
            body, body_text = self._parse_body(response)

        payload: dict[str, Any] = {
            "savedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "request": {
                "method": "POST",
                "url": url,
                "importJsonPath": str(json_path),
            },
            "ok": bool(
                response is not None
                and response.status_code == 200
                and isinstance(body, dict)
                and body.get("success") is True
            ),
            "requestError": request_error,
            "statusCode": response.status_code if response is not None else None,
            "reason": response.reason if response is not None else None,
            "headers": dict(response.headers) if response is not None else None,
            "body": body,
            "bodyText": body_text if body is None else None,
        }
        out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info(
            "Backend import response saved | path=%s status=%s ok=%s",
            out,
            payload["statusCode"],
            payload["ok"],
        )
        return out

    @staticmethod
    def _parse_body(
        response: requests.Response,
    ) -> tuple[Any | None, str | None]:
        text = response.text
        try:
            return response.json(), text
        except ValueError:
            return None, text

    @staticmethod
    def _print_response(
        response: requests.Response | None,
        response_path: Path,
        request_error: str | None,
    ) -> None:
        print(f"Backend import response saved: {response_path}", flush=True)
        if request_error is not None:
            print(f"Backend import request error: {request_error}", flush=True)
            return
        assert response is not None
        print(f"Backend import HTTP {response.status_code}", flush=True)
        try:
            pretty = json.dumps(response.json(), ensure_ascii=False, indent=2)
        except ValueError:
            pretty = response.text
        print("--- Backend import response body ---", flush=True)
        print(pretty, flush=True)
        print("--- end response ---", flush=True)
