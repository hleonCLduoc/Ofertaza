import logging
import math
import time
from datetime import datetime

import requests

import config
import db
from detect import detect_anomaly, detect_badge_discount
from notify import send_alert
from sites import SITES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("engine")


def _customer_price(prices):
    for price_type in ("internetPrice", "cmrPrice"):
        if price_type in prices:
            return price_type, prices[price_type]
    if prices:
        price_type = min(prices, key=prices.get)
        return price_type, prices[price_type]
    return None, None


def _reference_price(prices, exclude_type):
    if "normalPrice" in prices and "normalPrice" != exclude_type:
        return prices["normalPrice"]
    others = [v for k, v in prices.items() if k != exclude_type]
    return max(others) if others else None


SITE_LABELS = {
    "falabella": "Falabella",
    "ripley": "Ripley",
    "paris": "Paris",
    "theline": "The Line",
    "marathon": "Marathon",
    "sodimac": "Sodimac",
    "jumbo": "Jumbo",
    "hites": "Hites",
    "easy": "Easy",
    "santaisabel": "Santa Isabel",
    "abcdin": "ABCDIN",
    "preunic": "Preunic",
    "tricot": "Tricot",
    "kitchencenter": "Kitchen Center",
    "surprice": "Surprice",
}


def _money(value):
    return f"${value:,.0f}".replace(",", ".")


def _format_date(observed_at):
    # observed_at viene como "YYYY-MM-DD HH:MM:SS" (datetime('now') de SQLite).
    try:
        return datetime.strptime(observed_at[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return observed_at or ""


def _format_alert(site_id, reason, product, price_type, new_price, reference_price, history=None):
    site_label = SITE_LABELS.get(site_id, site_id.title())
    discount_pct = round((1 - new_price / reference_price) * 100) if reference_price else 0
    seller = product.get("seller_name") or "—"
    brand = product.get("brand")

    lines = [
        f"🔥 <b>-{discount_pct}%</b> · {site_label}",
        "",
        f"<b>{product['display_name']}</b>",
    ]
    if brand:
        lines.append(f"Marca: {brand}")
    lines += [
        "",
        f"<s>{_money(reference_price)}</s>",
        f"<b>{_money(new_price)}</b>",
    ]

    if history:
        lines.append("")
        lines.append("📊 Historial:")
        for price, observed_at in history:
            lines.append(f"{_format_date(observed_at)} - {_money(price)}")

    lines.append("")
    lines.append(f"🏪 Vendedor: {seller}")
    lines.append(f'👉 <a href="{product["url"]}">Ver oferta</a>')

    return "\n".join(lines)


def _process_page(conn, site_id, site_module, term, page_data):
    """Procesa una página ya descargada: guarda productos, detecta anomalías
    y notifica. Devuelve (productos_procesados, alertas)."""
    products_in_page = 0
    alerts_in_page = 0

    for product in site_module.iter_products(page_data):
        db.upsert_product(
            conn,
            site_id,
            product["sku_id"],
            product["product_id"],
            product["display_name"],
            product["brand"],
            product["seller_id"],
            product["seller_name"],
            product["url"],
            product["media_url"],
        )
        products_in_page += 1
        prices = product["prices"]

        # --- Detección instantánea: descuento declarado por el propio sitio ---
        badge_reason = detect_badge_discount(product.get("discount_percent"))
        if badge_reason:
            price_type, new_price = _customer_price(prices)
            reference_price = _reference_price(prices, price_type)
            if price_type and new_price is not None and reference_price:
                last_alerted = db.get_last_alert_price(conn, site_id, product["sku_id"], price_type)
                if last_alerted != new_price:
                    db.insert_alert(conn, site_id, product["sku_id"], price_type, new_price, reference_price, badge_reason)
                    dated_history = db.get_price_history_with_dates(conn, site_id, product["sku_id"], price_type)
                    send_alert(
                        _format_alert(site_id, badge_reason, product, price_type, new_price, reference_price, dated_history),
                        photo_url=product.get("media_url"),
                    )
                    alerts_in_page += 1

        # --- Detección histórica por tipo de precio ---
        for price_type, price in prices.items():
            price_history = db.get_price_history(conn, site_id, product["sku_id"], price_type)
            anomaly = detect_anomaly(price, price_history)
            if anomaly:
                reason, reference = anomaly
                last_alerted = db.get_last_alert_price(conn, site_id, product["sku_id"], price_type)
                if last_alerted != price:
                    db.insert_alert(conn, site_id, product["sku_id"], price_type, price, reference, reason)
                    dated_history = db.get_price_history_with_dates(conn, site_id, product["sku_id"], price_type)
                    send_alert(
                        _format_alert(site_id, reason, product, price_type, price, reference, dated_history),
                        photo_url=product.get("media_url"),
                    )
                    alerts_in_page += 1

            db.insert_observation(conn, site_id, product["sku_id"], price_type, price, term)

    return products_in_page, alerts_in_page


def run_site_term(conn, site_id, site_module, term):
    first_page = site_module.fetch_page(term, 1)
    if first_page is None:
        return 0, 0

    count, per_page = site_module.get_pagination(first_page)
    total_pages = max(1, math.ceil(count / per_page))
    if total_pages > config.MAX_PAGES_PER_TERM:
        logger.info(
            "[%s] %r: %s productos (%s páginas), se limita a %s páginas",
            site_id, term, count, total_pages, config.MAX_PAGES_PER_TERM,
        )
        total_pages = config.MAX_PAGES_PER_TERM
    else:
        logger.info("[%s] %r: %s productos en %s páginas", site_id, term, count, total_pages)

    total_products, total_alerts = _process_page(conn, site_id, site_module, term, first_page)

    for page in range(2, total_pages + 1):
        time.sleep(config.REQUEST_DELAY_SECONDS)
        page_data = site_module.fetch_page(term, page)
        if not page_data:
            continue
        products_in_page, alerts_in_page = _process_page(conn, site_id, site_module, term, page_data)
        if products_in_page == 0:
            # Página vacía: ya no hay más resultados (útil cuando el conteo
            # total reportado por el sitio es aproximado o desconocido).
            break
        total_products += products_in_page
        total_alerts += alerts_in_page

    return total_products, total_alerts


def run_cycle():
    db.init_db()
    logger.info("Sitios activos este ciclo (ACTIVE_SITES): %s", ", ".join(config.ACTIVE_SITES))
    with db.get_conn() as conn:
        grand_total_products = 0
        grand_total_alerts = 0
        for site_id in config.ACTIVE_SITES:
            site_module = SITES.get(site_id)
            if site_module is None:
                logger.warning("Sitio %r no está registrado en sites/__init__.py, se omite", site_id)
                continue
            for term in site_module.CATEGORIES:
                try:
                    products, alerts = run_site_term(conn, site_id, site_module, term)
                    grand_total_products += products
                    grand_total_alerts += alerts
                except requests.RequestException as exc:
                    logger.error("[%s] Error de red buscando %r: %s", site_id, term, exc)
                time.sleep(config.REQUEST_DELAY_SECONDS)
        logger.info(
            "Ciclo completo: %s productos revisados, %s alertas generadas",
            grand_total_products,
            grand_total_alerts,
        )


def main_loop():
    while True:
        start = time.time()
        try:
            run_cycle()
        except Exception:
            logger.exception("Error inesperado durante el ciclo")
        elapsed = time.time() - start
        sleep_for = max(0, config.CYCLE_INTERVAL_SECONDS - elapsed)
        logger.info("Durmiendo %.0f segundos hasta el próximo ciclo", sleep_for)
        time.sleep(sleep_for)
