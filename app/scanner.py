from __future__ import annotations

import hashlib
import re
import statistics
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
PDF_EXTENSIONS = {".pdf"}


class ScannerUnavailable(RuntimeError):
    pass


@dataclass
class ScanResult:
    text: str
    lines: list[str]
    movements: list[dict]
    mode: str
    warnings: list[str] = field(default_factory=list)
    rejected_count: int = 0


# En resúmenes bancarios/tarjetas exigimos año. Esto evita confundir "C. 07/12"
# (cuota 7 de 12) con una fecha, que era uno de los errores graves de v0.16.
STATEMENT_DATE_RE = re.compile(
    r"(?<!\d)(0?[1-9]|[12]\d|3[01])[./-](0?[1-9]|1[0-2])[./-](20\d{2}|\d{2})(?!\d)"
)
FLEX_DATE_RE = re.compile(
    r"(?<!\d)(0?[1-9]|[12]\d|3[01])[./-](0?[1-9]|1[0-2])(?:[./-](20\d{2}|\d{2}))?(?!\d)"
)
INSTALLMENT_RE = re.compile(r"\bC\.?\s*(\d{1,2})\s*/\s*(\d{1,2})\b", re.I)

# Montos impresos en un resumen: exigimos centavos. De esta forma referencias como
# 960004390064101, 20439, códigos de autorización, etc. nunca pueden ser dinero.
STRICT_MONEY_RE = re.compile(
    r"(?<![\d./])(?P<amount>[-(]?(?:ARS\s*)?\$?\s*"
    r"(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d{2}|\.\d{2})\)?-?)(?![\d./])",
    re.I,
)


def _clean_line(value: str) -> str:
    value = (value or "").replace("\u00a0", " ").strip()
    value = re.sub(r"\s+", " ", value)
    return value


def _bbox(box):
    try:
        points = list(box)
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def _rapidocr_items(image_path: str | Path) -> list[dict]:
    """Extrae texto + geometría.

    La geometría es clave para resúmenes: visualmente son tablas sin bordes y el OCR
    suele devolver la descripción y el importe como bloques separados. v0.16 tiraba
    las coordenadas y luego trataba cada bloque como una fila completa, por eso una
    referencia larga podía terminar interpretada como importe.
    """
    try:
        from rapidocr import RapidOCR
    except Exception as exc:  # pragma: no cover - depende del entorno del usuario
        raise ScannerUnavailable(
            "Falta el motor OCR local. Cerrá la app y ejecutá start.bat para que repare o instale las dependencias."
        ) from exc

    try:
        engine = RapidOCR()
        result = engine(str(image_path))
    except Exception as exc:  # pragma: no cover
        raise ScannerUnavailable(f"El motor OCR no pudo analizar la imagen: {exc}") from exc

    items: list[dict] = []

    # RapidOCR 3.x: RapidOCROutput con .txts/.boxes/.scores.
    texts = getattr(result, "txts", None)
    boxes = getattr(result, "boxes", None)
    scores = getattr(result, "scores", None)
    if texts is not None and len(texts):
        texts = list(texts)
        boxes = list(boxes) if boxes is not None else [None] * len(texts)
        scores = list(scores) if scores is not None else [None] * len(texts)
        for i, txt in enumerate(texts):
            text = _clean_line(str(txt or ""))
            if not text:
                continue
            bounds = _bbox(boxes[i]) if i < len(boxes) and boxes[i] is not None else None
            score = None
            try:
                score = float(scores[i]) if i < len(scores) and scores[i] is not None else None
            except Exception:
                pass
            items.append({"text": text, "bounds": bounds, "score": score})
        return items

    # Compatibilidad RapidOCR anterior: (payload, elapsed), payload=[box,text,score].
    if isinstance(result, tuple) and result:
        payload = result[0]
        if isinstance(payload, (list, tuple)):
            for entry in payload:
                if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                    continue
                text = _clean_line(str(entry[1] or ""))
                if not text:
                    continue
                bounds = _bbox(entry[0])
                score = None
                try:
                    score = float(entry[2]) if len(entry) >= 3 else None
                except Exception:
                    pass
                items.append({"text": text, "bounds": bounds, "score": score})
    return items


def _items_to_lines(items: list[dict]) -> list[str]:
    boxed = [x for x in items if x.get("bounds")]
    if not boxed:
        return [x["text"] for x in items if x.get("text")]
    return [row["text"] for row in _group_ocr_rows(boxed)]


def _group_ocr_rows(items: list[dict]) -> list[dict]:
    """Reconstruye filas usando la coordenada Y y ordena cada fila por X."""
    enriched = []
    heights = []
    for item in items:
        b = item.get("bounds")
        if not b:
            continue
        x1, y1, x2, y2 = map(float, b)
        h = max(1.0, y2 - y1)
        heights.append(h)
        enriched.append({**item, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "cx": (x1+x2)/2, "cy": (y1+y2)/2, "h": h})
    if not enriched:
        return []

    median_h = statistics.median(heights) if heights else 12.0
    tolerance = max(4.0, min(18.0, median_h * 0.72))
    enriched.sort(key=lambda x: (x.get("page", 0), x["cy"], x["x1"]))

    groups: list[list[dict]] = []
    for item in enriched:
        target = None
        for group in reversed(groups[-4:]):
            if group and group[0].get("page", 0) != item.get("page", 0):
                continue
            avg_cy = sum(g["cy"] for g in group) / len(group)
            # Centros cercanos o solapamiento vertical apreciable.
            overlap = max(0.0, min(max(g["y2"] for g in group), item["y2"]) - max(min(g["y1"] for g in group), item["y1"]))
            min_h = min(max(g["h"] for g in group), item["h"])
            if abs(avg_cy - item["cy"]) <= tolerance or overlap >= min_h * 0.35:
                target = group
                break
        if target is None:
            groups.append([item])
        else:
            target.append(item)

    rows = []
    for group in groups:
        group.sort(key=lambda x: x["x1"])
        text = _clean_line(" ".join(x["text"] for x in group))
        rows.append({
            "items": group,
            "text": text,
            "y": sum(x["cy"] for x in group) / len(group),
            "page": group[0].get("page", 0),
        })
    rows.sort(key=lambda r: (r.get("page", 0), r["y"]))
    return rows


def _pdf_document(path: Path) -> tuple[list[str], list[dict]]:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # pragma: no cover
        raise ScannerUnavailable(
            "Para leer PDF falta PyMuPDF. Cerrá la app y ejecutá start.bat para que repare o instale las dependencias."
        ) from exc

    all_lines: list[str] = []
    all_items: list[dict] = []
    try:
        document = fitz.open(str(path))
    except Exception as exc:
        raise ScannerUnavailable(f"No pude abrir el PDF: {exc}") from exc

    with document:
        for page_number, page in enumerate(document):
            native = page.get_text("text") or ""
            native_lines = [_clean_line(x) for x in native.splitlines() if _clean_line(x)]
            if len(" ".join(native_lines)) >= 80:
                all_lines.extend(native_lines)
                continue

            with tempfile.TemporaryDirectory(prefix="appgastos_ocr_") as tmp:
                img = Path(tmp) / f"page_{page_number + 1}.png"
                # 3x ayuda mucho con tipografías pequeñas de resúmenes bancarios.
                pix = page.get_pixmap(matrix=fitz.Matrix(3.0, 3.0), alpha=False)
                pix.save(str(img))
                page_items = _rapidocr_items(img)
                for item in page_items:
                    item = dict(item)
                    item["page"] = page_number
                    all_items.append(item)
                all_lines.extend(_items_to_lines(page_items))
    return all_lines, all_items


def _extract_document(path: str | Path) -> tuple[list[str], list[dict]]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        items = _rapidocr_items(path)
        return _items_to_lines(items), items
    if suffix in PDF_EXTENSIONS:
        return _pdf_document(path)
    raise ScannerUnavailable("Formato no soportado. Usá PNG, JPG, WEBP, TIFF o PDF.")


def extract_text(path: str | Path) -> list[str]:
    lines, _ = _extract_document(path)
    return lines


def _parse_amount(token: str):
    raw = (token or "").strip().upper()
    if not raw:
        return None
    negative = raw.startswith("-") or raw.endswith("-") or (raw.startswith("(") and raw.endswith(")"))
    raw = raw.replace("$", "").replace("ARS", "").replace(" ", "")
    raw = raw.strip("()-+")
    raw = re.sub(r"[^0-9,.]", "", raw)
    if not raw or not re.search(r"\d", raw):
        return None

    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        tail = raw.rsplit(",", 1)[1]
        raw = raw.replace(".", "")
        raw = raw.replace(",", ".") if len(tail) in {1, 2} else raw.replace(",", "")
    elif "." in raw:
        tail = raw.rsplit(".", 1)[1]
        if len(tail) == 3 and raw.count(".") >= 1:
            raw = raw.replace(".", "")
        elif raw.count(".") > 1:
            parts = raw.split(".")
            if len(parts[-1]) == 2:
                raw = "".join(parts[:-1]) + "." + parts[-1]
            else:
                raw = "".join(parts)
    try:
        value = float(raw)
    except Exception:
        return None
    if value <= 0:
        return None
    return -value if negative else value


def _extract_amount_at_end(line: str):
    # Parser flexible para tickets. Los resúmenes usan STRICT_MONEY_RE.
    match = re.search(r"(?P<amount>[-(]?(?:ARS\s*)?\$?\s*\d[\d.]*(?:,\d{1,2})?\)?-?)\s*$", line, re.I)
    if not match:
        match = re.search(r"(?P<amount>[-(]?\$?\s*\d[\d,]*(?:\.\d{2})\)?-?)\s*$", line, re.I)
    if not match:
        return None, None
    value = _parse_amount(match.group("amount"))
    if value is None:
        return None, None
    return value, match.span("amount")


def _strict_money_matches(text: str):
    out = []
    for m in STRICT_MONEY_RE.finditer(text or ""):
        value = _parse_amount(m.group("amount"))
        if value is not None:
            out.append((value, m.group("amount"), m.span("amount")))
    return out


def _date_from_text(text: str, fallback: date) -> date:
    matches = list(FLEX_DATE_RE.finditer(text or ""))
    if not matches:
        return fallback
    m = matches[0]
    day = int(m.group(1)); month = int(m.group(2)); year_raw = m.group(3)
    if year_raw:
        year = int(year_raw)
        if year < 100:
            year += 2000
    else:
        year = fallback.year
        if month > fallback.month + 6:
            year -= 1
    try:
        return date(year, month, day)
    except ValueError:
        return fallback


def _statement_date(text: str):
    m = STATEMENT_DATE_RE.search(text or "")
    if not m:
        return None, None
    raw = m.group(0)
    d, mo, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if yr < 100:
        yr += 2000
    try:
        return date(yr, mo, d), m.span()
    except ValueError:
        return None, None


def _line_date(line: str, fallback: date):
    m = FLEX_DATE_RE.search(line or "")
    if not m:
        return fallback, None
    return _date_from_text(m.group(0), fallback), m.span()


IGNORE_TICKET_WORDS = {
    "total", "subtotal", "iva", "neto", "gravado", "exento", "cuit", "cuil", "cai", "cae",
    "vuelto", "cambio", "efectivo", "debito", "débito", "credito", "crédito", "tarjeta", "visa",
    "mastercard", "maestro", "mercadopago", "mercado pago", "pago", "saldo", "descuento", "ahorro",
    "importe", "factura", "ticket", "consumidor final", "total a pagar", "redondeo",
}


def _looks_ignored_ticket_line(description: str) -> bool:
    normalized = re.sub(r"[^a-záéíóúüñ0-9 ]+", " ", description.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if len(normalized) < 2 or normalized.isdigit():
        return True
    return any(word in normalized for word in IGNORE_TICKET_WORDS)


def _clean_statement_description(text: str, amount_token: str | None = None) -> tuple[str, tuple[int, int] | None]:
    body = _clean_line(text)
    # Fecha impresa (dd.mm.yy / dd-mm-yy / dd/mm/yy).
    body = STATEMENT_DATE_RE.sub(" ", body, count=1)
    # Código de operación al comienzo: 000872*, 883903*, etc.
    body = re.sub(r"^\s*\d{4,8}\s*\*?\s+", "", body)
    installment = None
    im = INSTALLMENT_RE.search(body)
    if im:
        try:
            current, total = int(im.group(1)), int(im.group(2))
            if 1 <= current <= total <= 60:
                installment = (current, total)
        except Exception:
            pass
        body = INSTALLMENT_RE.sub(" ", body)
    if amount_token:
        # Quita una sola aparición desde la derecha, para no tocar números que sí formen parte del comercio.
        pos = body.rfind(amount_token.strip())
        if pos >= 0:
            body = body[:pos] + " " + body[pos + len(amount_token.strip()):]
    # Referencias / autorizaciones largas. Mantenemos números cortos como "COTO SUCURSAL 188".
    body = re.sub(r"\b\d{5,}\b", " ", body)
    # Moneda extranjera y tokens residuales de columnas auxiliares.
    body = re.sub(r"\bUSD\b", " ", body, flags=re.I)
    body = re.sub(r"\s+", " ", body).strip(" ·-|*")
    return body, installment


def _statement_movements_from_items(items: list[dict], fallback: date, file_hash: str):
    rows = _group_ocr_rows([x for x in items if x.get("bounds")])
    if not rows:
        return [], [], 0

    max_x = max((float(x["bounds"][2]) for x in items if x.get("bounds")), default=1.0)
    movements = []
    warnings: list[str] = []
    rejected = 0

    for row_index, row in enumerate(rows):
        row_text = row["text"]
        tx_date, _ = _statement_date(row_text)
        if not tx_date:
            continue

        candidates = []
        for item in row["items"]:
            matches = _strict_money_matches(item["text"])
            if not matches:
                continue
            x1, _, x2, _ = item["bounds"]
            ratio = ((float(x1) + float(x2)) / 2.0) / max_x
            for value, token, span in matches:
                candidates.append({
                    "value": value, "token": token, "ratio": ratio,
                    "item": item, "span": span,
                })

        # Si un OCR item abarca toda la fila, el centro geométrico no representa al importe.
        # Igual lo aceptamos si el monto aparece al final del texto del item.
        for c in candidates:
            txt = c["item"]["text"]
            if c["ratio"] < 0.50 and txt.rstrip().endswith(c["token"].strip()):
                c["ratio"] = 0.76

        if not candidates:
            rejected += 1
            continue

        row_upper = row_text.upper()
        # Preferimos columna ARS (normalmente 55%-88% del ancho). La columna USD suele quedar al extremo derecho.
        ars = [c for c in candidates if 0.50 <= c["ratio"] <= 0.89]
        if ars:
            selected = max(ars, key=lambda c: c["ratio"])
        else:
            selected = max(candidates, key=lambda c: c["ratio"])
            if "USD" in row_upper and selected["ratio"] > 0.89:
                rejected += 1
                warnings.append(f"{tx_date.isoformat()}: consumo en USD omitido por ahora ({row_text[:90]}).")
                continue

        amount = float(selected["value"])
        if abs(amount) <= 0.01 or abs(amount) > 1_000_000_000:
            rejected += 1
            warnings.append(f"{tx_date.isoformat()}: importe descartado por ser inverosímil: {selected['token']}")
            continue

        description, installment = _clean_statement_description(row_text, selected["token"])
        # Cuando el row_text incluye varios bloques, puede haber quedado otro monto auxiliar; retiramos montos estrictos residuales.
        description = STRICT_MONEY_RE.sub(" ", description)
        description = re.sub(r"\s+", " ", description).strip(" ·-|")
        if len(description) < 2:
            rejected += 1
            continue

        score_values = [x.get("score") for x in row["items"] if isinstance(x.get("score"), (int, float))]
        avg_score = sum(score_values) / len(score_values) if score_values else None

        # Signo negativo impreso = crédito/devolución.
        kind = "income" if amount < 0 else "expense"
        value = abs(amount)
        external = hashlib.sha1(
            f"{file_hash}|statement-v2|{row.get('page',0)}|{row_index}|{tx_date}|{description}|{value}".encode("utf-8")
        ).hexdigest()
        raw = {
            "line": row_text,
            "scan_type": "statement",
            "row_number": row_index + 1,
            "document_hash": file_hash,
            "parser": "statement-layout-v2",
            "ocr_score": avg_score,
        }
        if installment:
            raw["installment_current"] = installment[0]
            raw["installment_total"] = installment[1]
        movements.append({
            "external_id": f"scan:{external}",
            "tx_date": tx_date.isoformat(),
            "kind": kind,
            "amount": value,
            "description": description[:180],
            "raw": raw,
        })
    return movements, warnings, rejected


def _statement_movements(lines: Iterable[str], fallback: date, file_hash: str):
    """Fallback sin geometría (por ejemplo PDF con texto nativo).

    Es deliberadamente estricto: fecha con año + importe con 2 decimales. Preferimos
    omitir una fila dudosa antes que inventar un gasto.
    """
    movements = []
    warnings = []
    rejected = 0
    for index, raw in enumerate(lines):
        line = _clean_line(raw)
        tx_date, date_span = _statement_date(line)
        if not tx_date or not date_span:
            continue
        money = _strict_money_matches(line)
        if not money:
            rejected += 1
            continue
        amount, token, span = money[-1]
        if abs(amount) > 1_000_000_000:
            rejected += 1
            continue
        if "USD" in line.upper() and span[0] > len(line) * 0.75 and len(money) == 1:
            rejected += 1
            warnings.append(f"{tx_date.isoformat()}: consumo en USD omitido por ahora.")
            continue
        description, installment = _clean_statement_description(line, token)
        description = STRICT_MONEY_RE.sub(" ", description)
        description = re.sub(r"\s+", " ", description).strip(" ·-|")
        if len(description) < 2:
            rejected += 1
            continue
        kind = "income" if amount < 0 else "expense"
        value = abs(float(amount))
        external = hashlib.sha1(f"{file_hash}|statement-v2-line|{index}|{tx_date}|{description}|{value}".encode("utf-8")).hexdigest()
        raw_meta = {
            "line": line, "scan_type": "statement", "line_number": index + 1,
            "document_hash": file_hash, "parser": "statement-line-v2",
        }
        if installment:
            raw_meta["installment_current"] = installment[0]
            raw_meta["installment_total"] = installment[1]
        movements.append({
            "external_id": f"scan:{external}", "tx_date": tx_date.isoformat(), "kind": kind,
            "amount": value, "description": description[:180], "raw": raw_meta,
        })
    return movements, warnings, rejected


def _ticket_movements(lines: Iterable[str], fallback: date, file_hash: str) -> list[dict]:
    lines = [_clean_line(x) for x in lines if _clean_line(x)]
    whole_text = "\n".join(lines)
    receipt_date = _date_from_text(whole_text, fallback)
    candidates = []
    for index, line in enumerate(lines):
        amount, span = _extract_amount_at_end(line)
        if amount is None or span is None or amount < 0:
            continue
        description = line[:span[0]].strip(" ·-|")
        description = re.sub(r"^\s*\d{5,16}\s+", "", description)
        description = re.sub(r"^\s*\d+(?:[xX*]\d+(?:[,.]\d+)?)?\s+", "", description)
        description = re.sub(r"\s+", " ", description).strip()
        if _looks_ignored_ticket_line(description):
            continue
        value = abs(amount)
        if value <= 0.01:
            continue
        candidates.append((index, description, value, line))

    if len(candidates) >= 3:
        values = [x[2] for x in candidates]
        max_i = max(range(len(values)), key=values.__getitem__)
        max_value = values[max_i]
        other_sum = sum(values) - max_value
        if other_sum > 0 and abs(max_value - other_sum) / max_value < 0.025:
            candidates.pop(max_i)

    movements = []
    for index, description, value, line in candidates:
        external = hashlib.sha1(f"{file_hash}|ticket|{index}|{receipt_date}|{description}|{value}".encode("utf-8")).hexdigest()
        movements.append({
            "external_id": f"scan:{external}",
            "tx_date": receipt_date.isoformat(),
            "kind": "expense",
            "amount": value,
            "description": description[:180],
            "raw": {
                "line": line, "scan_type": "ticket", "line_number": index + 1,
                "document_hash": file_hash, "parser": "ticket-v1",
            },
        })
    return movements


def _guess_mode(lines: list[str]) -> str:
    dated_money_lines = 0
    money_lines = 0
    for line in lines:
        strict = _strict_money_matches(line)
        flexible, _ = _extract_amount_at_end(line)
        if strict or flexible is not None:
            money_lines += 1
            if STATEMENT_DATE_RE.search(line):
                dated_money_lines += 1
    if dated_money_lines >= 2:
        return "statement"
    if money_lines >= 2:
        return "ticket"
    return "statement"


def scan_document(path: str | Path, mode: str = "auto", fallback_date: date | None = None) -> ScanResult:
    path = Path(path)
    fallback_date = fallback_date or date.today()
    lines, items = _extract_document(path)
    if not lines and not items:
        return ScanResult(text="", lines=[], movements=[], mode=mode if mode != "auto" else "unknown")

    raw_bytes = path.read_bytes()
    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    final_mode = _guess_mode(lines) if mode == "auto" else mode
    warnings: list[str] = []
    rejected = 0
    if final_mode == "ticket":
        movements = _ticket_movements(lines, fallback_date, file_hash)
    else:
        if any(x.get("bounds") for x in items):
            movements, warnings, rejected = _statement_movements_from_items(items, fallback_date, file_hash)
            # Si el layout no produjo nada, probamos texto reconstruido como fallback estricto.
            if not movements:
                movements, warnings2, rejected2 = _statement_movements(lines, fallback_date, file_hash)
                warnings.extend(warnings2); rejected += rejected2
        else:
            movements, warnings, rejected = _statement_movements(lines, fallback_date, file_hash)

    return ScanResult(
        text="\n".join(lines), lines=lines, movements=movements, mode=final_mode,
        warnings=warnings, rejected_count=rejected,
    )
