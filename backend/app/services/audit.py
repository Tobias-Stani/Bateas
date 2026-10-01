"""Registro central de la plataforma: actividad (quién hizo qué y cuándo) y libro de pagos.

Vive en el registro, no en la base de cada disquería: eliminar una disquería no borra su historia ni sus pagos.
Solo se agrega: nada de esto se edita ni se borra desde la app.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from ..db import registry

log_ = logging.getLogger("uvicorn.error")


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(slug, actor, kind, **detail):
    """Anota un evento. Si falla, la acción de la persona igual sigue: el error queda en el log del servidor."""
    try:
        with registry() as con:
            con.execute("INSERT INTO events (at, slug, actor, kind, detail) VALUES (?, ?, ?, ?, ?)",
                        (stamp(), slug or "", actor, kind, json.dumps(detail, ensure_ascii=False, default=str)))
        con.close()
    except Exception:
        log_.exception("No se pudo registrar el evento %s de %s", kind, slug)


def record_payment(slug, order):
    """Copia (o actualiza) un pago en el libro central. La clave es el pago de Mercado Pago, no el pedido:
    un pedido puede tener un intento rechazado y otro aprobado, y los números de pedido se repiten si se recrea el slug."""
    try:
        with registry() as con:
            con.execute("""INSERT INTO payments (payment_id, slug, order_id, status, total, fee, mp_fee, net, payer, items, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(payment_id) DO UPDATE SET status = excluded.status, mp_fee = excluded.mp_fee,
                           net = excluded.net, payer = excluded.payer, updated_at = excluded.updated_at""",
                        (order["payment_id"], slug, order["id"], order["status"], order["total"], order["fee"], order.get("mp_fee"),
                         order.get("net"), order.get("payer") or "", json.dumps(order["items"], ensure_ascii=False), stamp(), stamp()))
        con.close()
    except Exception:
        log_.exception("No se pudo registrar el pago %s de %s", order.get("payment_id"), slug)


# --- consultas para el super admin ---

def events(slug="", kind="", before=0, limit=100):
    where, params = [], []
    for col, value in (("slug", slug), ("kind", kind)):
        if value:
            where.append(f"{col} = ?")
            params.append(value)
    if before:
        where.append("id < ?")
        params.append(before)
    sql = f"SELECT * FROM events {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY id DESC LIMIT ?"
    con = registry()
    rows = [{**dict(r), "detail": json.loads(r["detail"])} for r in con.execute(sql, [*params, min(max(limit, 1), 500)])]
    con.close()
    return rows


def payments(slug="", limit=1000):
    con = registry()
    rows = [{**dict(r), "items": json.loads(r["items"])} for r in con.execute(
        f"SELECT * FROM payments {'WHERE slug = ?' if slug else ''} ORDER BY created_at DESC LIMIT ?", [*([slug] if slug else []), limit])]
    con.close()
    return rows


def stats():
    """Totales de pagos aprobados: de siempre, de los últimos 30 días y por disquería."""
    month = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(timespec="seconds")
    sums = "COUNT(*) n, COALESCE(SUM(total), 0) total, COALESCE(SUM(fee), 0) fee, COALESCE(SUM(mp_fee), 0) mp_fee, COALESCE(SUM(net), 0) net"
    con = registry()
    res = {
        "all": dict(con.execute(f"SELECT {sums} FROM payments WHERE status = 'approved'").fetchone()),
        "month": dict(con.execute(f"SELECT {sums} FROM payments WHERE status = 'approved' AND created_at >= ?", (month,)).fetchone()),
        "by_slug": {r["slug"]: dict(r) for r in con.execute(f"SELECT slug, {sums} FROM payments WHERE status = 'approved' GROUP BY slug")},
        "problems": con.execute("SELECT COUNT(*) FROM payments WHERE status IN ('amount_mismatch', 'charged_back', 'refunded')").fetchone()[0],
        "events_day": con.execute("SELECT COUNT(*) FROM events WHERE at >= ?",
                                  ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds"),)).fetchone()[0],
        "kinds": [r[0] for r in con.execute("SELECT DISTINCT kind FROM events ORDER BY kind")],
    }
    con.close()
    return res
