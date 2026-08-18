import json
import logging
import math
import re
import time

import requests

import config
import db
from detect import detect_anomaly
from notify import send_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("scraper")

NEXT_DATA_RE = re.compile(
    r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)

session = requests.Session()
session.headers.update({"User-Agent": config.USER_AGENT})


def fetch_page(search_term, page):
    params = {"Ntt": search_term, "page": page}
    resp = session.get(config.BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    match = NEXT_DATA_RE.search(resp.text)
    if not match:
        logger.warning("No se encontró __NEXT_DATA__ para %r página %s", search_term, page)
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        logger.warning("__NEXT_DATA__ inválido para %r página %s", search_term, page)
        return None
    return data.get("props", {}).get("pageProps", {})


def parse_price(price_field):
    """price_field es una lista tipo ['789.990'] -> 789990 (int)."""
    if not price_field:
        return None
    raw = price_field[0]
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    return int(digits)


def iter_products(page_props):
    for product in page_props.get("results", []):
        sku_id = product.get("skuId") or product.get("productId")
        if not sku_id:
            continue
        prices = {}
        for entry in product.get("prices", []):
            price_type = entry.get("type")
            value = parse_price(entry.get("price"))
            if price_type and value is not None:
                prices[price_type] = value
        yield {
            "sku_id": str(sku_id),
            "product_id": str(product.get("productId", "")),
            "display_name": product.get("displayName", ""),
            "brand": product.get("brand", ""),
            "url": product.get("url", ""),
            "prices": prices,
        }


def run_search_term(conn, search_term):
    first_page = fetch_page(search_term, 1)
    if first_page is None:
        return 0, 0

    total_products = 0
    total_alerts = 0

    pagination = first_page.get("pagination", {})
    count = pagination.get("count", 0)
    per_page = pagination.get("perPage", 48) or 48
    total_pages = max(1, math.ceil(count / per_page))
    logger.info("%r: %s productos en %s páginas", search_term, count, total_pages)

    pages_props = [first_page]
    for page in range(2, total_pages + 1):
        time.sleep(config.REQUEST_DELAY_SECONDS)
        page_props = fetch_page(search_term, page)
        if page_props:
            pages_props.append(page_props)

    for page_props in pages_props:
        for product in iter_products(page_props):
            db.upsert_product(
                conn,
                product["sku_id"],
                product["product_id"],
                product["display_name"],
                product["brand"],
                product["url"],
            )
            total_products += 1

            for price_type, price in product["prices"].items():
                history = db.get_price_history(conn, product["sku_id"], price_type)
                anomaly = detect_anomaly(price, history)
                if anomaly:
                    reason, reference = anomaly
                    db.insert_alert(conn, product["sku_id"], price_type, price, reference, reason)
                    send_alert(
                        f"⚠️ Posible error de precio ({reason})\n"
                        f"{product['display_name']} [{price_type}]\n"
                        f"Precio nuevo: ${price:,} vs referencia histórica: ${reference:,.0f}\n"
                        f"{product['url']}".replace(",", ".")
                    )
                    total_alerts += 1

                db.insert_observation(conn, product["sku_id"], price_type, price, search_term)

    return total_products, total_alerts


def run_cycle():
    db.init_db()
    with db.get_conn() as conn:
        grand_total_products = 0
        grand_total_alerts = 0
        for term in config.SEARCH_TERMS:
            try:
                products, alerts = run_search_term(conn, term)
                grand_total_products += products
                grand_total_alerts += alerts
            except requests.RequestException as exc:
                logger.error("Error de red buscando %r: %s", term, exc)
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


if __name__ == "__main__":
    main_loop()
