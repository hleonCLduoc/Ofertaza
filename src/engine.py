import logging
import math
import time

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


def _format_alert(site_id, reason, product, price_type, new_price, reference_price):
    reference_txt = f"${reference_price:,.0f}".replace(",", ".")
    new_txt = f"${new_price:,}".replace(",", ".")
    seller = product.get("seller_name") or "—"
    return (
        f"⚠️ <b>Posible error de precio</b> ({reason})\n"
        f"Sitio: {site_id}\n"
        f"{product['display_name']}\n"
        f"Vendedor: {seller}\n"
        f"Tipo de precio: {price_type}\n"
        f"Precio anterior/referencia: {reference_txt}\n"
        f"Precio actual: {new_txt}\n"
        f'<a href="{product["url"]}">Ver producto</a>'
    )


def run_site_term(conn, site_id, site_module, term):
    first_page = site_module.fetch_page(term, 1)
    if first_page is None:
        return 0, 0

    total_products = 0
    total_alerts = 0

    count, per_page = site_module.get_pagination(first_page)
    total_pages = max(1, math.ceil(count / per_page))
    logger.info("[%s] %r: %s productos en %s páginas", site_id, term, count, total_pages)

    pages_data = [first_page]
    for page in range(2, total_pages + 1):
        time.sleep(config.REQUEST_DELAY_SECONDS)
        page_data = site_module.fetch_page(term, page)
        if page_data:
            pages_data.append(page_data)

    for page_data in pages_data:
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
            total_products += 1
            prices = product["prices"]

            # --- Detección instantánea: descuento declarado por el propio sitio ---
            badge_reason = detect_badge_discount(product.get("discount_percent"))
            if badge_reason:
                price_type, new_price = _customer_price(prices)
                reference_price = _reference_price(prices, price_type)
                if price_type and new_price is not None and reference_price:
                    db.insert_alert(conn, site_id, product["sku_id"], price_type, new_price, reference_price, badge_reason)
                    send_alert(
                        _format_alert(site_id, badge_reason, product, price_type, new_price, reference_price),
                        photo_url=product.get("media_url"),
                    )
                    total_alerts += 1

            # --- Detección histórica por tipo de precio ---
            for price_type, price in prices.items():
                history = db.get_price_history(conn, site_id, product["sku_id"], price_type)
                anomaly = detect_anomaly(price, history)
                if anomaly:
                    reason, reference = anomaly
                    db.insert_alert(conn, site_id, product["sku_id"], price_type, price, reference, reason)
                    send_alert(
                        _format_alert(site_id, reason, product, price_type, price, reference),
                        photo_url=product.get("media_url"),
                    )
                    total_alerts += 1

                db.insert_observation(conn, site_id, product["sku_id"], price_type, price, term)

    return total_products, total_alerts


def run_cycle():
    db.init_db()
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
