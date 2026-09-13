from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
import time
from typing import Any
from zoneinfo import ZoneInfo

import requests

BASE_URL = "https://api.mercadopago.com"

REPORT_COLUMNS = [
    "TRANSACTION_DATE",
    "SOURCE_ID",
    "EXTERNAL_REFERENCE",
    "PAYMENT_METHOD_TYPE",
    "PAYMENT_METHOD",
    "TRANSACTION_TYPE",
    "TRANSACTION_AMOUNT",
    "TRANSACTION_CURRENCY",
    "FEE_AMOUNT",
    "SETTLEMENT_NET_AMOUNT",
    "SETTLEMENT_CURRENCY",
    "SETTLEMENT_DATE",
    "REAL_AMOUNT",
    "METADATA",
]


def _default_report_config(include_timezone: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "columns": [{"key": key} for key in REPORT_COLUMNS],
        "file_name_prefix": "app-gastos",
        "frequency": {"hour": 0, "value": 1, "type": "monthly"},
        "separator": ";",
        "report_translation": "es",
        "header_language": "es",
        "scheduled": False,
        "include_withdraw": True,
        "refund_detailed": False,
        "shipping_detail": False,
        "coupon_detailed": False,
        "show_chargeback_cancel": True,
        "show_fee_prevision": False,
    }
    # Argentina usa GMT-03. Algunas cuentas/API antiguas validan una lista
    # más limitada; por eso create_report_configuration reintenta sin este
    # campo si Mercado Pago lo rechaza.
    if include_timezone:
        payload["display_timezone"] = "GMT-03"
    return payload


@dataclass
class MercadoPagoAccessResult:
    ok: bool
    message: str
    configured: bool = False
    details: dict[str, Any] | None = None


@dataclass
class MercadoPagoSyncResult:
    ok: bool
    message: str
    file_name: str | None = None
    content: bytes | None = None
    details: dict[str, Any] | None = None
    pending: bool = False
    task_id: int | str | None = None


from .secure_store import get_token

def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _json_or_none(response) -> dict[str, Any] | list[Any] | None:
    try:
        parsed = response.json()
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass
    return None


def _api_error(response) -> str:
    data = _json_or_none(response)
    if isinstance(data, dict):
        msg = data.get("message") or data.get("error") or data.get("cause")
        if msg:
            return str(msg)
    text = (response.text or "").strip().replace("\n", " ")
    return text[:260] or f"HTTP {response.status_code}"


def create_report_configuration(token: str | None = None, timeout: int = 15) -> MercadoPagoAccessResult:
    """Crea la configuración inicial requerida por la API de reportes.

    Mercado Pago solo permite crearla una vez por cuenta. Si otra integración
    la creó entre medio y recibimos 409, volvemos a consultarla y lo tratamos
    como éxito.
    """
    token = (token or get_token() or "").strip()
    if not token:
        return MercadoPagoAccessResult(False, "Todavía no guardaste un Access Token.")

    def do_post(payload):
        try:
            return requests.post(
                f"{BASE_URL}/v1/account/settlement_report/config",
                headers=_headers(token), json=payload, timeout=timeout,
            )
        except requests.RequestException as exc:
            return exc

    response = do_post(_default_report_config(True))
    if isinstance(response, requests.RequestException):
        return MercadoPagoAccessResult(False, f"No pude crear la configuración de reportes: {response}")

    # Algunas variantes de la API pueden rechazar una zona horaria concreta.
    # El reporte sigue siendo utilizable con el valor por defecto, así que
    # hacemos un segundo intento conservador.
    if response.status_code in {400, 422} and "timezone" in _api_error(response).lower():
        response = do_post(_default_report_config(False))
        if isinstance(response, requests.RequestException):
            return MercadoPagoAccessResult(False, f"No pude crear la configuración de reportes: {response}")

    if response.status_code in {200, 201}:
        data = _json_or_none(response)
        return MercadoPagoAccessResult(
            True,
            "Mercado Pago quedó conectado y la configuración de reportes se creó correctamente.",
            configured=True,
            details=data if isinstance(data, dict) else None,
        )

    if response.status_code == 409:
        checked = test_report_access(token, timeout)
        if checked.ok and checked.configured:
            checked.message = "La configuración de reportes ya existía y está disponible para App Gastos."
            return checked

    data = _json_or_none(response)
    return MercadoPagoAccessResult(
        False,
        f"Mercado Pago no permitió crear la configuración. HTTP {response.status_code}: {_api_error(response)}",
        configured=False,
        details=data if isinstance(data, dict) else None,
    )


def ensure_report_configuration(token: str | None = None, timeout: int = 15) -> MercadoPagoAccessResult:
    """Verifica la configuración y la crea automáticamente si falta."""
    token = (token or get_token() or "").strip()
    if not token:
        return MercadoPagoAccessResult(False, "Todavía no guardaste un Access Token.")
    checked = test_report_access(token, timeout)
    if not checked.ok:
        return checked
    if checked.configured:
        checked.message = "Mercado Pago está conectado y la configuración de reportes está lista."
        return checked
    created = create_report_configuration(token, timeout)
    return created


def test_report_access(token: str | None = None, timeout: int = 12) -> MercadoPagoAccessResult:
    token = (token or get_token() or "").strip()
    if not token:
        return MercadoPagoAccessResult(False, "Todavía no guardaste un Access Token.")
    try:
        response = requests.get(
            f"{BASE_URL}/v1/account/settlement_report/config",
            headers=_headers(token), timeout=timeout,
        )
    except requests.RequestException as exc:
        return MercadoPagoAccessResult(False, f"No pude comunicarme con Mercado Pago: {exc}")

    data = _json_or_none(response)
    details = data if isinstance(data, dict) else None
    if response.status_code == 200:
        return MercadoPagoAccessResult(
            True,
            "La API respondió correctamente y el reporte 'Todas las transacciones' está disponible para este token.",
            configured=True,
            details=details,
        )
    if response.status_code in {400, 404, 409}:
        return MercadoPagoAccessResult(
            True,
            "El token llegó correctamente a Mercado Pago, pero la cuenta no devolvió una configuración de reportes. "
            f"Detalle: {_api_error(response)}",
            configured=False,
            details=details,
        )
    if response.status_code in {401, 403}:
        return MercadoPagoAccessResult(False, "Mercado Pago rechazó el token o esta cuenta no tiene permiso para ese recurso.", details=details)
    return MercadoPagoAccessResult(False, f"Mercado Pago respondió HTTP {response.status_code}: {_api_error(response)}", details=details)


def _utc_report_bounds(start_day: date, end_day: date) -> tuple[str, str]:
    """Convierte días de Argentina a límites UTC para no cortar movimientos por el huso horario."""
    try:
        tz = ZoneInfo("America/Argentina/Buenos_Aires")
    except Exception:
        tz = timezone(timedelta(hours=-3))
    start_local = datetime.combine(start_day, dtime.min, tzinfo=tz)
    end_local = datetime.combine(end_day + timedelta(days=1), dtime.min, tzinfo=tz) - timedelta(milliseconds=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    def fmt(dt: datetime) -> str:
        return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return fmt(start_utc), fmt(end_utc)


def _parse_api_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _same_bound(a: Any, b: Any, tolerance_seconds: float = 2.0) -> bool:
    da, db = _parse_api_datetime(a), _parse_api_datetime(b)
    if da is None or db is None:
        return str(a or "") == str(b or "")
    if da.tzinfo is None:
        da = da.replace(tzinfo=timezone.utc)
    if db.tzinfo is None:
        db = db.replace(tzinfo=timezone.utc)
    return abs((da.astimezone(timezone.utc) - db.astimezone(timezone.utc)).total_seconds()) <= tolerance_seconds


def _download_report_file(file_name: str, token: str, request_timeout: int, details: dict[str, Any] | None = None) -> MercadoPagoSyncResult:
    try:
        download = requests.get(
            f"{BASE_URL}/v1/account/settlement_report/{file_name}",
            headers=_headers(token), timeout=max(request_timeout, 30),
        )
    except requests.RequestException as exc:
        return MercadoPagoSyncResult(False, f"El reporte se generó, pero no pude descargarlo: {exc}", details=details)
    if download.status_code != 200:
        return MercadoPagoSyncResult(
            False,
            f"No pude descargar el reporte. HTTP {download.status_code}: {_api_error(download)}",
            details=details,
        )
    return MercadoPagoSyncResult(True, "Reporte descargado correctamente.", str(file_name), download.content, details)


def query_report_task(task_id: int | str, token: str | None = None, request_timeout: int = 20) -> MercadoPagoSyncResult:
    """Consulta una tarea ya creada y descarga el archivo cuando está listo."""
    token = (token or get_token() or "").strip()
    if not token:
        return MercadoPagoSyncResult(False, "No hay un Access Token guardado.")
    try:
        task = requests.get(
            f"{BASE_URL}/v1/account/settlement_report/task/{task_id}",
            headers=_headers(token), timeout=request_timeout,
        )
    except requests.RequestException as exc:
        return MercadoPagoSyncResult(False, f"No pude consultar la tarea del reporte: {exc}", task_id=task_id)
    if task.status_code != 200:
        return MercadoPagoSyncResult(
            False,
            f"No pude consultar la tarea del reporte. HTTP {task.status_code}: {_api_error(task)}",
            details=_json_or_none(task) if isinstance(_json_or_none(task), dict) else None,
            task_id=task_id,
        )
    payload = _json_or_none(task)
    if not isinstance(payload, dict):
        return MercadoPagoSyncResult(False, "Mercado Pago devolvió un estado de tarea inválido.", task_id=task_id)
    status = str(payload.get("status") or "").lower()
    file_name = payload.get("file_name")
    if status == "processed" and file_name:
        return _download_report_file(str(file_name), token, request_timeout, payload)
    if status in {"failed", "error", "cancelled", "canceled"}:
        return MercadoPagoSyncResult(False, f"Mercado Pago marcó la generación como '{status}'.", details=payload, task_id=task_id)
    return MercadoPagoSyncResult(
        False,
        "Mercado Pago todavía está preparando el reporte.",
        details=payload,
        pending=True,
        task_id=payload.get("id") or task_id,
    )


def find_existing_report_entry(
    begin_date: str,
    end_date: str,
    token: str | None = None,
    request_timeout: int = 20,
) -> dict[str, Any] | None:
    """Busca una tarea existente para el mismo rango.

    Esto evita crear un reporte nuevo cada vez que el usuario toca Sincronizar.
    También permite que v0.9 recupere una tarea creada por v0.8, aunque esa
    versión todavía no guardaba el ID localmente.
    """
    token = (token or get_token() or "").strip()
    if not token:
        return None
    try:
        response = requests.get(
            f"{BASE_URL}/v1/account/settlement_report/list",
            headers=_headers(token), timeout=request_timeout,
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    payload = _json_or_none(response)
    if isinstance(payload, dict):
        # Algunas respuestas envuelven los elementos en results/content.
        payload = payload.get("results") or payload.get("content") or payload.get("data") or []
    if not isinstance(payload, list):
        return None
    candidates = []
    for item in payload:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        status = str(item.get("status") or "").lower()
        if status in {"failed", "error", "cancelled", "canceled"}:
            continue
        if _same_bound(item.get("begin_date"), begin_date) and _same_bound(item.get("end_date"), end_date):
            candidates.append(item)
    if not candidates:
        return None
    # La API suele devolver primero los más recientes, pero ordenamos por
    # last_modified/generation_date por si cambia ese comportamiento.
    def sort_key(item: dict[str, Any]):
        return str(item.get("last_modified") or item.get("generation_date") or item.get("id") or "")
    candidates.sort(key=sort_key, reverse=True)
    return candidates[0]


def find_existing_report_task(
    begin_date: str,
    end_date: str,
    token: str | None = None,
    request_timeout: int = 20,
) -> int | str | None:
    """Compatibilidad: devuelve sólo el ID de la entrada encontrada."""
    item = find_existing_report_entry(begin_date, end_date, token, request_timeout)
    return item.get("id") if item else None


def _result_from_report_entry(item: dict[str, Any], token: str, request_timeout: int) -> MercadoPagoSyncResult:
    status = str(item.get("status") or "").lower()
    task_id = item.get("id")
    file_name = item.get("file_name")
    if status == "processed" and not file_name and item.get("report_id"):
        # En algunas variantes de /list el reporte ya figura procesado pero
        # el file_name no viene incluido. El endpoint /search sí permite
        # recuperar el reporte por report_id, sin depender de /task/{id}.
        try:
            response = requests.get(
                f"{BASE_URL}/v1/account/settlement_report/search",
                headers=_headers(token), params={"id": item.get("report_id")}, timeout=request_timeout,
            )
            if response.status_code == 200:
                payload = _json_or_none(response)
                candidates = payload if isinstance(payload, list) else (
                    payload.get("results") or payload.get("content") or payload.get("data") or [payload]
                    if isinstance(payload, dict) else []
                )
                if isinstance(candidates, dict):
                    candidates = [candidates]
                if isinstance(candidates, list):
                    found = next((x for x in candidates if isinstance(x, dict) and x.get("file_name")), None)
                    if found:
                        file_name = found.get("file_name")
                        item = {**item, **found}
        except requests.RequestException:
            pass
    if status == "processed" and file_name:
        result = _download_report_file(str(file_name), token, request_timeout, item)
        result.task_id = task_id
        return result
    if status in {"failed", "error", "cancelled", "canceled"}:
        return MercadoPagoSyncResult(False, f"Mercado Pago marcó la generación como '{status}'.", details=item, task_id=task_id)
    return MercadoPagoSyncResult(
        False,
        "Mercado Pago todavía está preparando el reporte.",
        details=item,
        pending=True,
        task_id=task_id,
    )


def _invalid_task_result(result: MercadoPagoSyncResult) -> bool:
    text = (result.message or "").lower()
    return (
        "invalid taskid" in text
        or "invalid task-id" in text
        or "invalid_parameter" in text
        or "task_not_found_for_user" in text
        or "tarea no encontrada" in text
        or "not found" in text
        or "http 404" in text
    )


def _wait_for_task(
    task_id: int | str,
    token: str,
    *,
    request_timeout: int,
    wait_seconds: int,
    poll_interval: float,
) -> MercadoPagoSyncResult:
    deadline = time.monotonic() + max(1, wait_seconds)
    last_result: MercadoPagoSyncResult | None = None
    while True:
        result = query_report_task(task_id, token, request_timeout)
        last_result = result
        if result.ok or not result.pending:
            return result
        if time.monotonic() >= deadline:
            return MercadoPagoSyncResult(
                False,
                "Mercado Pago sigue procesando el reporte. App Gastos va a revisar esta misma tarea automáticamente, sin crear otra.",
                details=result.details,
                pending=True,
                task_id=result.task_id or task_id,
            )
        time.sleep(max(0.5, poll_interval))


def download_range_report(
    start_day: date,
    end_day: date,
    token: str | None = None,
    *,
    request_timeout: int = 20,
    wait_seconds: int = 35,
    poll_interval: float = 2.0,
    existing_task_id: int | str | None = None,
) -> MercadoPagoSyncResult:
    """Genera o reutiliza un reporte y lo descarga cuando esté listo.

    A diferencia de v0.8, esta versión no crea tareas repetidas al reintentar.
    Primero reanuda el task_id persistido y, si no existe, busca en Mercado
    Pago una tarea previa con el mismo rango. Sólo crea una nueva si realmente
    no encuentra ninguna reutilizable.
    """
    token = (token or get_token() or "").strip()
    if not token:
        return MercadoPagoSyncResult(False, "No hay un Access Token guardado.")
    if end_day < start_day:
        return MercadoPagoSyncResult(False, "El rango de fechas no es válido.")

    config = ensure_report_configuration(token, timeout=min(request_timeout, 15))
    if not config.ok or not config.configured:
        return MercadoPagoSyncResult(False, config.message, details=config.details)

    begin_date, end_date = _utc_report_bounds(start_day, end_day)

    # 1) La lista de reportes es la fuente más robusta para reanudar tareas.
    # En algunas cuentas Mercado Pago responde "Invalid taskID" al endpoint
    # /task/{id}, aunque ese mismo reporte aparece correctamente en /list.
    # Si ya está procesado, además podemos descargarlo sin consultar /task.
    reusable_entry = find_existing_report_entry(begin_date, end_date, token, request_timeout)
    if reusable_entry:
        return _result_from_report_entry(reusable_entry, token, request_timeout)

    # 2) Si ya hay una tarea local y todavía no apareció en /list, NO usamos
    # /task/{id}. En algunas cuentas argentinas ese endpoint responde
    # "Invalid taskID" aunque la tarea sea válida. La lista es nuestra fuente
    # de verdad; el próximo chequeo volverá a buscar el mismo rango.
    if existing_task_id:
        return MercadoPagoSyncResult(
            False,
            "Mercado Pago todavía está preparando el reporte. App Gastos lo seguirá buscando en la lista de reportes.",
            pending=True,
            task_id=existing_task_id,
        )

    # 3) Crear una tarea nueva únicamente cuando no existe una reutilizable.
    try:
        created = requests.post(
            f"{BASE_URL}/v1/account/settlement_report",
            headers=_headers(token),
            json={"begin_date": begin_date, "end_date": end_date},
            timeout=request_timeout,
        )
    except requests.RequestException as exc:
        return MercadoPagoSyncResult(False, f"No pude crear el reporte: {exc}")

    if created.status_code not in {200, 201, 202}:
        return MercadoPagoSyncResult(
            False,
            "Mercado Pago no pudo crear el reporte. "
            f"HTTP {created.status_code}: {_api_error(created)}",
            details=_json_or_none(created) if isinstance(_json_or_none(created), dict) else None,
        )
    payload = _json_or_none(created)
    if not isinstance(payload, dict) or not payload.get("id"):
        return MercadoPagoSyncResult(False, "Mercado Pago creó el reporte pero no devolvió el ID de la tarea.")

    # No forzamos inmediatamente /task/{id}. Guardamos la tarea y dejamos que
    # los reintentos consulten /list; evita el error Invalid taskID observado
    # en cuentas argentinas y sigue el estado asíncrono de la API.
    return _result_from_report_entry(payload, token, request_timeout)
