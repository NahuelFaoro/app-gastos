from __future__ import annotations

import base64
import json
import mimetypes
import secrets
import socket
import tempfile
import threading
from calendar import monthrange
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .scanner import scan_document
from .work_calendar import week_end, week_start


class MobileServerError(RuntimeError):
    pass


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        sock.close()


def ensure_mobile_credentials(db) -> tuple[str, str]:
    token = db.get_setting("mobile_api_token", "").strip()
    code = db.get_setting("mobile_pair_code", "").strip()
    if not token:
        token = secrets.token_urlsafe(32)
        db.set_setting("mobile_api_token", token)
    if not (code.isdigit() and len(code) == 6):
        code = f"{secrets.randbelow(1_000_000):06d}"
        db.set_setting("mobile_pair_code", code)
    return token, code


def rotate_pair_code(db) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.set_setting("mobile_pair_code", code)
    return code


def _tx_for_mobile(row: dict) -> dict:
    row = dict(row or {})
    kind = row.get("kind") or "expense"
    category = row.get("category_display") or ("Transferencia" if kind == "transfer" else "Sin categoría")
    return {
        "id": row.get("id"), "kind": kind, "amount": float(row.get("amount") or 0),
        "tx_date": str(row.get("tx_date") or "")[:10],
        "description": row.get("description") or "", "note": row.get("note") or "", "tags": row.get("tags") or "",
        "display": row.get("display") or row.get("description") or category,
        "account_id": row.get("account_id"), "account_name": row.get("account_name") or "",
        "to_account_id": row.get("to_account_id"), "to_account_name": row.get("to_account_name") or "",
        "category_id": row.get("category_id"), "category": category,
        "parent_category_name": row.get("parent_category_name") or "",
        "category_color": row.get("category_effective_color") or "#63DAB7",
        "category_icon": row.get("category_effective_icon") or "other",
        "source": row.get("source") or "manual", "external_id": row.get("external_id"),
        "installment_plan_id": row.get("installment_plan_id"),
        "installment_number": row.get("installment_number"), "installment_total": row.get("installment_total"),
    }


def _history_for_mobile(row: dict) -> dict:
    row = dict(row or {})
    return {
        "id": row.get("id"), "kind": row.get("kind"), "amount": float(row.get("amount") or 0),
        "year": row.get("year"), "month": row.get("month"), "display": row.get("display") or row.get("category_display") or "Historial",
        "category_id": row.get("category_id"), "category": row.get("category_display") or "Historial",
        "category_color": row.get("category_effective_color") or "#8F9C97",
        "category_icon": row.get("category_effective_icon") or "other",
        "source": "legacy_excel", "precision": "month", "file_name": row.get("file_name") or "",
    }


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first, last


def _period_from_query(qs: dict) -> tuple[date, date, str]:
    today = date.today()
    mode = (qs.get("mode") or ["month"])[0]
    try:
        if mode == "day":
            target = date.fromisoformat((qs.get("date") or [today.isoformat()])[0][:10])
            return target, target, target.strftime("%d/%m/%Y")
        if mode == "week":
            anchor = date.fromisoformat((qs.get("date") or [today.isoformat()])[0][:10])
            start = week_start(anchor); end = week_end(start)
            return start, end, f"{start.strftime('%d/%m')} – {end.strftime('%d/%m/%Y')}"
        if mode == "year":
            year = int((qs.get("year") or [today.year])[0])
            return date(year, 1, 1), date(year, 12, 31), str(year)
        if mode == "period":
            start = date.fromisoformat((qs.get("from") or [today.replace(day=1).isoformat()])[0][:10])
            end = date.fromisoformat((qs.get("to") or [today.isoformat()])[0][:10])
            if end < start: start, end = end, start
            return start, end, f"{start.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}"
        year = int((qs.get("year") or [today.year])[0]); month = int((qs.get("month") or [today.month])[0])
        start, end = _month_bounds(year, month)
        return start, end, f"{month:02d}/{year}"
    except Exception:
        start, end = _month_bounds(today.year, today.month)
        return start, end, f"{today.month:02d}/{today.year}"


class _Handler(BaseHTTPRequestHandler):
    server_version = "AppGastosMobile/0.24"

    def log_message(self, fmt, *args):
        return

    @property
    def app_server(self):
        return self.server.app_server

    @property
    def db(self):
        return self.app_server.db

    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(data)

    def _read_json(self, max_bytes=20_000_000):
        try: length = int(self.headers.get("Content-Length", "0"))
        except Exception: length = 0
        if length <= 0: return {}
        if length > max_bytes: raise ValueError("El archivo o solicitud es demasiado grande.")
        raw = self.rfile.read(length)
        try: return json.loads(raw.decode("utf-8"))
        except Exception: return {}

    def _authorized(self) -> bool:
        token = self.headers.get("X-AppGastos-Token", "").strip()
        expected, _ = ensure_mobile_credentials(self.db)
        return bool(token and secrets.compare_digest(token, expected))

    def _need_auth(self):
        if self._authorized(): return False
        self._send_json({"ok": False, "error": "not_paired"}, HTTPStatus.UNAUTHORIZED); return True

    def _changed(self):
        if self.app_server.on_change:
            try: self.app_server.on_change()
            except Exception: pass

    def _serve_static(self, path: str):
        rel = path.lstrip("/") or "index.html"
        if rel == "mobile": rel = "index.html"
        root = self.app_server.web_root.resolve(); target = (root / rel).resolve()
        if root not in target.parents and target != root: self.send_error(404); return
        if not target.exists() or not target.is_file(): target = root / "index.html"
        try: data = target.read_bytes()
        except Exception: self.send_error(404); return
        mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") or mime in {"application/javascript", "application/json"} else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache" if target.name in {"service-worker.js", "manifest.webmanifest"} else "no-store")
        self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path); path = parsed.path; qs = parse_qs(parsed.query)
        if not path.startswith("/api/"): self._serve_static(path); return
        if path == "/api/ping": self._send_json({"ok": True, "name": "App Gastos", "version": "0.24.0"}); return
        if self._need_auth(): return
        try:
            routes = {
                "/api/bootstrap": self._get_bootstrap, "/api/transactions": self._get_transactions,
                "/api/transaction": self._get_transaction, "/api/accounts": self._get_accounts,
                "/api/account": self._get_account, "/api/categories": self._get_categories,
                "/api/installments": self._get_installments, "/api/installment": self._get_installment,
                "/api/installment-commitments": self._get_installment_commitments,
                "/api/flex": self._get_flex, "/api/flex-history": self._get_flex_history,
                "/api/analysis": self._get_analysis, "/api/review": self._get_review,
                "/api/calendar": self._get_calendar, "/api/card": self._get_card,
            }
            fn = routes.get(path)
            if not fn: self._send_json({"ok": False, "error": "not_found"}, 404); return
            fn(qs)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path); path = parsed.path
        try: body = self._read_json()
        except ValueError as exc: self._send_json({"ok": False, "error": str(exc)}, 413); return
        if path == "/api/pair":
            _, code = ensure_mobile_credentials(self.db); supplied = str(body.get("code") or "").strip()
            if supplied and secrets.compare_digest(supplied, code):
                token, _ = ensure_mobile_credentials(self.db); self._send_json({"ok": True, "token": token})
            else: self._send_json({"ok": False, "error": "Código incorrecto"}, HTTPStatus.FORBIDDEN)
            return
        if self._need_auth(): return
        try:
            routes = {
                "/api/transactions": self._post_transaction, "/api/transactions/duplicate": self._post_duplicate,
                "/api/accounts": self._post_account, "/api/accounts/toggle-balance": self._post_toggle_account,
                "/api/categories": self._post_category, "/api/flex/delivery": self._post_flex_delivery,
                "/api/flex/rate": self._post_flex_rate, "/api/review/category": self._post_review_category,
                "/api/review/accept": self._post_review_accept, "/api/review/ignore": self._post_review_ignore,
                "/api/review/accept-ready": self._post_review_accept_ready, "/api/review/clear": self._post_review_clear,
                "/api/scan": self._post_scan, "/api/installments/cancel": self._post_installment_cancel,
                "/api/installments/remove": self._post_installment_remove, "/api/card/payment": self._post_card_payment,
            }
            fn = routes.get(path)
            if not fn: self._send_json({"ok": False, "error": "not_found"}, 404); return
            fn(body)
        except ValueError as exc: self._send_json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc: self._send_json({"ok": False, "error": str(exc)}, 500)

    def do_PUT(self):
        parsed = urlparse(self.path); path = parsed.path
        try: body = self._read_json()
        except ValueError as exc: self._send_json({"ok": False, "error": str(exc)}, 413); return
        if self._need_auth(): return
        try:
            if path == "/api/transactions": self._put_transaction(body)
            elif path == "/api/accounts": self._put_account(body)
            elif path == "/api/categories": self._put_category(body)
            else: self._send_json({"ok": False, "error": "not_found"}, 404)
        except ValueError as exc: self._send_json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc: self._send_json({"ok": False, "error": str(exc)}, 500)

    def do_DELETE(self):
        parsed = urlparse(self.path); path = parsed.path; qs = parse_qs(parsed.query)
        if self._need_auth(): return
        try:
            obj_id = int((qs.get("id") or [0])[0])
            if path == "/api/transactions": self.db.delete_transaction(obj_id)
            elif path == "/api/accounts": self.db.delete_account(obj_id)
            elif path == "/api/categories": self.db.delete_category(obj_id)
            else: self._send_json({"ok": False, "error": "not_found"}, 404); return
            self._changed(); self._send_json({"ok": True})
        except Exception as exc: self._send_json({"ok": False, "error": str(exc)}, 400)

    # ---------- serializers ----------
    def _accounts(self):
        out = []
        for a in self.db.accounts_with_balances():
            item = dict(a)
            item.update({"balance": float(a.get("balance") or 0), "opening_balance": float(a.get("opening_balance") or 0),
                         "credit_limit": float(a.get("credit_limit") or 0), "include_in_balance": bool(a.get("include_in_balance", 1))})
            out.append(item)
        return out

    def _categories(self, kind: str):
        rows = self.db.categories(kind if kind in {"expense", "income"} else "expense")
        parents = {int(r["id"]): r for r in rows if r.get("parent_id") is None}; result=[]
        for r in rows:
            if r.get("parent_id") is None: continue
            p = parents.get(int(r.get("parent_id")))
            result.append({"id": r.get("id"), "name": r.get("name"), "parent_id": r.get("parent_id"), "parent": (p or {}).get("name") or "",
                           "label": f"{(p or {}).get('name')} / {r.get('name')}" if p else r.get("name"),
                           "color": r.get("color") or (p or {}).get("color") or "#63DAB7", "icon": r.get("icon") or (p or {}).get("icon") or "other"})
        child_parent_ids = {int(r.get("parent_id")) for r in rows if r.get("parent_id") is not None}
        for pid,p in parents.items():
            if pid not in child_parent_ids:
                result.append({"id":p.get("id"),"name":p.get("name"),"parent_id":None,"parent":"","label":p.get("name"),"color":p.get("color") or "#63DAB7","icon":p.get("icon") or "other"})
        return result

    # ---------- GET ----------
    def _get_bootstrap(self, qs):
        today=date.today()
        try: year=int((qs.get("year") or [today.year])[0]); month=int((qs.get("month") or [today.month])[0])
        except Exception: year,month=today.year,today.month
        summary=self.db.monthly_summary(year,month); recent=self.db.recent_transactions(10); expenses=self.db.expense_by_category(year,month,6)
        commitments=self.db.installment_monthly_commitments(today.year,today.month,2)
        self._send_json({"ok":True,"today":today.isoformat(),"period":{"year":year,"month":month},
            "summary":{"available_balance":float(self.db.available_balance()),"net_worth":float(self.db.net_worth()),
                       "income":float(summary.get("income") or 0),"expense":float(summary.get("expense") or 0),"net":float(summary.get("net") or 0)},
            "accounts":self._accounts(),"recent":[_tx_for_mobile(x) for x in recent],
            "expense_categories":[{"id":x.get("category_id"),"name":x.get("category") or x.get("name") or "Sin categoría","total":float(x.get("total") or 0),"color":x.get("color") or "#63DAB7","icon":x.get("icon") or "other"} for x in expenses],
            "categories":{"expense":self._categories("expense"),"income":self._categories("income")},
            "installments":{"active":len(self.db.installment_plans(active_only=True)),"current":commitments[0] if commitments else None,"next":commitments[1] if len(commitments)>1 else None},
            "pending":self.db.pending_import_counts(),
        })

    def _get_transactions(self, qs):
        def iv(name):
            try: return int((qs.get(name) or [0])[0]) or None
            except Exception: return None
        year=iv("year"); month=iv("month"); limit=max(1,min(iv("limit") or 120,400)); category_id=iv("category_id"); account_id=iv("account_id")
        kind=(qs.get("kind") or ["all"])[0]; search=(qs.get("search") or [""])[0]; date_from=(qs.get("from") or [None])[0]; date_to=(qs.get("to") or [None])[0]
        rows=self.db.transactions(year=year,month=month,kind=kind,account_id=account_id,category_id=category_id,search=search,limit=limit,date_from=date_from,date_to=date_to)
        history=[]
        if year and month and not date_from and not date_to:
            history=self.db.historical_entries(year=year,month=month,kind=kind,category_id=category_id,search=search,limit=300)
        self._send_json({"ok":True,"transactions":[_tx_for_mobile(x) for x in rows],"history":[_history_for_mobile(x) for x in history]})

    def _get_transaction(self, qs):
        tx_id=int((qs.get("id") or [0])[0]); tx=self.db.transaction(tx_id)
        if not tx: raise ValueError("Movimiento no encontrado.")
        enriched=dict(tx)
        account=self.db.account(int(tx.get("account_id") or 0))
        to_account=self.db.account(int(tx.get("to_account_id") or 0)) if tx.get("to_account_id") else None
        enriched["account_name"]=(account or {}).get("name") or ""; enriched["to_account_name"]=(to_account or {}).get("name") or ""
        if tx.get("kind")=="transfer":
            enriched.update({"category_display":"Transferencia","category_effective_color":"#63DAB7","category_effective_icon":"transfer","display":tx.get("description") or f"{enriched['account_name']} → {enriched['to_account_name']}"})
        else:
            cat=self.db.category(int(tx.get("category_id") or 0)) if tx.get("category_id") else None
            parent=self.db.category(int(cat.get("parent_id") or 0)) if cat and cat.get("parent_id") else None
            leaf=(cat or {}).get("name") or "Sin categoría"
            enriched["category_display"]=f"{parent['name']} / {leaf}" if parent else leaf
            enriched["category_effective_color"]=(cat or {}).get("color") or (parent or {}).get("color") or "#94A3B8"
            enriched["category_effective_icon"]=(cat or {}).get("icon") or (parent or {}).get("icon") or "other"
            enriched["display"]=tx.get("description") or enriched["category_display"]
        self._send_json({"ok":True,"transaction":_tx_for_mobile(enriched)})

    def _get_accounts(self, qs): self._send_json({"ok":True,"accounts":self._accounts()})
    def _get_account(self, qs):
        aid=int((qs.get("id") or [0])[0]); a=self.db.account(aid)
        if not a: raise ValueError("Cuenta no encontrada.")
        a=dict(a); a["balance"]=self.db.account_balance(aid); self._send_json({"ok":True,"account":a})
    def _get_categories(self, qs):
        kind=(qs.get("kind") or ["expense"])[0]; self._send_json({"ok":True,"categories":self._categories(kind),"raw":self.db.categories(kind)})
    def _get_installments(self, qs):
        active=(qs.get("active") or ["1"])[0] not in {"0","false","all"}; rows=self.db.installment_plans(active_only=active)
        for r in rows:
            total=max(1,int(r.get("installments") or 1)); current=max(int(r.get("current_number") or 0), min(total,int(r.get("next_number") or 1)-1)); r["progress"]=round(current/total*100,1); r["current_number"]=current; r["remaining"]=max(0,float(r.get("total_amount") or 0)-float(r.get("registered_amount") or 0))
        self._send_json({"ok":True,"plans":rows})
    def _get_installment(self, qs):
        pid=int((qs.get("id") or [0])[0]); p=self.db.installment_plan(pid)
        if not p: raise ValueError("Plan no encontrado.")
        txs=self.db.installment_transactions(pid); self._send_json({"ok":True,"plan":p,"transactions":txs})
    def _get_installment_commitments(self, qs):
        today=date.today(); months=max(1,min(int((qs.get("months") or [12])[0]),24)); year=int((qs.get("year") or [today.year])[0]); month=int((qs.get("month") or [today.month])[0])
        self._send_json({"ok":True,"months":self.db.installment_monthly_commitments(year,month,months)})
    def _get_flex(self, qs):
        start=(qs.get("week_start") or [week_start(date.today()).isoformat()])[0][:10]
        self._send_json({"ok":True,"summary":self.db.flex_week_summary(start),"zones":self.db.flex_zones(start,True),"income_link":self.db.flex_income_link(start)})
    def _get_flex_history(self, qs): self._send_json({"ok":True,"weeks":self.db.flex_week_history(20)})
    def _get_analysis(self, qs):
        start,end,label=_period_from_query(qs); kind=(qs.get("kind") or ["expense"])[0]
        if kind not in {"expense","income"}: kind="expense"
        summary=self.db.period_summary(start,end,include_history=True); cats=self.db.category_totals_period(kind,start,end,include_history=True); subs=self.db.subcategory_totals_period(kind,start,end,include_history=True)
        cat_id=None
        try: cat_id=int((qs.get("category_id") or [0])[0]) or None
        except Exception: pass
        if cat_id:
            root=self.db.category(cat_id)
            if root:
                if root.get("parent_id") is None: subs=[x for x in subs if int(x.get("category_id") or 0)==cat_id or str(x.get("parent_category") or "").casefold()==str(root.get("name") or "").casefold()]
                else: subs=[x for x in subs if int(x.get("category_id") or 0)==cat_id]
        self._send_json({"ok":True,"start":start.isoformat(),"end":end.isoformat(),"label":label,"kind":kind,"summary":summary,"categories":cats,"subcategories":subs})
    def _get_review(self, qs):
        source=(qs.get("source") or [None])[0]; rows=self.db.imported_movements("pending",source)
        limit=max(1,min(int((qs.get("limit") or [120])[0]),300)); rows=rows[:limit]
        out=[]
        for r in rows:
            out.append({"id":r.get("id"),"source":r.get("source"),"tx_date":r.get("tx_date"),"kind":r.get("kind"),"amount":float(r.get("amount") or 0),"description":r.get("description") or "Movimiento","account_id":r.get("account_id"),"account_name":r.get("account_name"),"category_id":r.get("category_id"),"category":r.get("category_display"),"color":r.get("category_color"),"icon":r.get("category_icon"),"transfer_hint":bool(r.get("transfer_hint")),"installment_current":r.get("scan_installment_current"),"installment_total":r.get("scan_installment_total")})
        self._send_json({"ok":True,"counts":self.db.pending_import_counts(),"items":out})
    def _get_calendar(self, qs):
        today=date.today(); year=int((qs.get("year") or [today.year])[0]); month=int((qs.get("month") or [today.month])[0]); self._send_json({"ok":True,"year":year,"month":month,"days":self.db.daily_totals(year,month)})
    def _get_card(self, qs):
        aid=int((qs.get("id") or [0])[0]); overview=self.db.card_overview(aid); self._send_json({"ok":True,"overview":overview})

    # ---------- write helpers ----------
    @staticmethod
    def _tx_payload(body):
        kind=str(body.get("kind") or "expense")
        try: amount=float(body.get("amount") or 0); account_id=int(body.get("account_id") or 0)
        except Exception: raise ValueError("Revisá importe y cuenta.")
        category_id=body.get("category_id"); to_id=body.get("to_account_id")
        return {"kind":kind,"amount":amount,"account_id":account_id,"to_account_id":int(to_id) if to_id else None,
                "category_id":int(category_id) if category_id else None,"tx_date":str(body.get("tx_date") or date.today().isoformat())[:10],
                "description":str(body.get("description") or "").strip(),"note":str(body.get("note") or "").strip(),"tags":str(body.get("tags") or "").strip(),
                "installments":max(1,int(body.get("installments") or 1))}
    def _post_transaction(self, body):
        tx_id=self.db.add_transaction(self._tx_payload(body),source="mobile"); self._changed(); self._send_json({"ok":True,"id":tx_id},201)
    def _put_transaction(self, body):
        tx_id=int(body.get("id") or 0); self.db.update_transaction(tx_id,self._tx_payload(body)); self._changed(); self._send_json({"ok":True,"id":tx_id})
    def _post_duplicate(self, body):
        tx_id=self.db.duplicate_transaction(int(body.get("id") or 0),str(body.get("tx_date") or date.today().isoformat())[:10]); self._changed(); self._send_json({"ok":True,"id":tx_id})
    def _post_account(self, body):
        aid=self.db.add_account(str(body.get("name") or "").strip(),str(body.get("type") or "Cuenta"),float(body.get("opening_balance") or 0),str(body.get("color") or "#63DAB7"),bool(body.get("include_in_balance",True)),float(body.get("credit_limit") or 0),body.get("closing_day"),body.get("due_day")); self._changed(); self._send_json({"ok":True,"id":aid},201)
    def _put_account(self, body):
        aid=int(body.get("id") or 0); self.db.update_account(aid,str(body.get("name") or "").strip(),str(body.get("type") or "Cuenta"),float(body.get("opening_balance") or 0),str(body.get("color") or "#63DAB7"),bool(body.get("include_in_balance",True)),float(body.get("credit_limit") or 0),body.get("closing_day"),body.get("due_day")); self._changed(); self._send_json({"ok":True})
    def _post_toggle_account(self, body): self.db.set_account_balance_inclusion(int(body.get("id") or 0),bool(body.get("included"))); self._changed(); self._send_json({"ok":True})
    def _post_category(self, body):
        cid=self.db.add_category(str(body.get("name") or "").strip(),str(body.get("kind") or "expense"),int(body["parent_id"]) if body.get("parent_id") else None,str(body.get("color") or "#63DAB7"),str(body.get("icon") or "other")); self._changed(); self._send_json({"ok":True,"id":cid},201)
    def _put_category(self, body):
        cid=int(body.get("id") or 0); self.db.update_category(cid,str(body.get("name") or "").strip(),str(body.get("kind") or "expense"),int(body["parent_id"]) if body.get("parent_id") else None,str(body.get("color") or "#63DAB7"),str(body.get("icon") or "other")); self._changed(); self._send_json({"ok":True})
    def _post_flex_delivery(self, body):
        action=str(body.get("action") or "add"); zid=int(body.get("zone_id") or 0); week=str(body.get("week_start") or week_start(date.today()).isoformat())[:10]
        if action=="remove": changed=self.db.remove_last_flex_delivery(zid,week)
        else: self.db.add_flex_delivery(zid,week,1,str(body.get("rate_date") or date.today().isoformat())[:10]); changed=True
        self._changed(); self._send_json({"ok":True,"changed":bool(changed)})
    def _post_flex_rate(self, body): self.db.set_flex_zone_rate(int(body.get("zone_id") or 0),float(body.get("price") or 0),str(body.get("effective_from") or date.today().isoformat())[:10]); self._changed(); self._send_json({"ok":True})
    def _post_review_category(self, body): self.db.update_import_category(int(body.get("id") or 0),int(body["category_id"]) if body.get("category_id") else None); self._changed(); self._send_json({"ok":True})
    def _post_review_accept(self, body):
        tx=self.db.accept_import(int(body.get("id") or 0),kind=body.get("kind"),category_id=int(body["category_id"]) if body.get("category_id") else None,description=body.get("description"),remember_rule=bool(body.get("remember_rule")),transfer_account_id=int(body["transfer_account_id"]) if body.get("transfer_account_id") else None); self._changed(); self._send_json({"ok":True,"transaction_id":tx})
    def _post_review_ignore(self, body): self.db.ignore_import(int(body.get("id") or 0)); self._changed(); self._send_json({"ok":True})
    def _post_review_accept_ready(self, body): count=self.db.accept_categorized_imports(); self._changed(); self._send_json({"ok":True,"count":count})
    def _post_review_clear(self, body): count=self.db.delete_pending_imports(str(body.get("group") or "all")); self._changed(); self._send_json({"ok":True,"count":count})
    def _post_installment_cancel(self, body): self.db.cancel_installment_plan(int(body.get("id") or 0)); self._changed(); self._send_json({"ok":True})
    def _post_installment_remove(self, body): count=self.db.remove_installment_plan(int(body.get("id") or 0),bool(body.get("delete_movements"))); self._changed(); self._send_json({"ok":True,"affected":count})
    def _post_card_payment(self, body):
        card_id=int(body.get("card_account_id") or 0); amount=float(body.get("amount") or 0); tx_date=str(body.get("tx_date") or date.today().isoformat())[:10]; mode=str(body.get("mode") or "external")
        if amount<=0: raise ValueError("Ingresá un importe mayor a cero.")
        card=self.db.account(card_id)
        if not card or card.get("type")!="Tarjeta": raise ValueError("La cuenta no es una tarjeta.")
        if mode=="external": self.db.add_account_adjustment(card_id,amount,tx_date,str(body.get("description") or f"Pago externo {card['name']}"),"card_payment_external")
        else:
            source=int(body.get("source_account_id") or 0)
            if not source or source==card_id: raise ValueError("Elegí otra cuenta desde donde pagar.")
            self.db.add_transaction({"kind":"transfer","amount":amount,"account_id":source,"to_account_id":card_id,"category_id":None,"tx_date":tx_date,"description":str(body.get("description") or f"Pago {card['name']}"),"note":"","tags":"pago tarjeta"},source="mobile")
        self._changed(); self._send_json({"ok":True})
    def _post_scan(self, body):
        filename=Path(str(body.get("filename") or "comprobante.jpg")).name; data=str(body.get("data") or "")
        if "," in data and data.startswith("data:"): data=data.split(",",1)[1]
        try: raw=base64.b64decode(data,validate=False)
        except Exception: raise ValueError("No pude leer el archivo seleccionado.")
        if not raw or len(raw)>15_000_000: raise ValueError("El comprobante debe pesar menos de 15 MB.")
        suffix=Path(filename).suffix.lower() or ".jpg"
        if suffix not in {".png",".jpg",".jpeg",".webp",".bmp",".tif",".tiff",".pdf"}: raise ValueError("Formato no soportado.")
        account_id=int(body.get("account_id") or 0); mode=str(body.get("mode") or "auto"); fallback=date.fromisoformat(str(body.get("fallback_date") or date.today().isoformat())[:10])
        with tempfile.TemporaryDirectory(prefix="appgastos_mobile_scan_") as tmp:
            path=Path(tmp)/("scan"+suffix); path.write_bytes(raw); result=scan_document(path,mode,fallback)
        movements=list(result.movements or [])
        source="receipt_scan" if result.mode=="ticket" else "statement_scan"; stage=self.db.stage_imported_movements(movements,source,account_id) if movements else {"inserted":0,"duplicates":0}
        self._changed(); self._send_json({"ok":True,"mode":result.mode,"detected":len(movements),"stage":stage,"warnings":result.warnings,"rejected":result.rejected_count})


class _HTTPServer(ThreadingHTTPServer):
    daemon_threads=True; allow_reuse_address=True


class MobileServer:
    def __init__(self, db, port: int=8765, on_change=None):
        self.db=db; self.port=int(port); self.on_change=on_change; self.web_root=Path(__file__).resolve().parent.parent/"web"; self._httpd=None; self._thread=None
    @property
    def running(self): return bool(self._thread and self._thread.is_alive() and self._httpd)
    @property
    def url(self): return f"http://{local_ip()}:{self.port}"
    def start(self):
        if self.running: return
        ensure_mobile_credentials(self.db)
        try: httpd=_HTTPServer(("0.0.0.0",self.port),_Handler)
        except OSError as exc: raise MobileServerError(f"No se pudo abrir el puerto {self.port}: {exc}") from exc
        httpd.app_server=self; self._httpd=httpd; self._thread=threading.Thread(target=httpd.serve_forever,name="AppGastosMobile",daemon=True); self._thread.start()
    def stop(self):
        httpd=self._httpd; self._httpd=None
        if httpd:
            try: httpd.shutdown(); httpd.server_close()
            except Exception: pass
        thread=self._thread; self._thread=None
        if thread and thread.is_alive(): thread.join(timeout=1.5)
