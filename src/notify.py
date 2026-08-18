import logging

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("notify")


def send_alert(text, photo_url=None):
    """Envía la alerta a Telegram (con foto si hay una disponible).
    Si no hay credenciales configuradas, solo queda en el log."""
    logger.warning("ALERTA: %s", text.replace("\n", " | "))

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    if photo_url:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": text[:1024],
            "parse_mode": "HTML",
            "photo": photo_url,
        }
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error("Fallo al enviar a Telegram: %s %s", resp.status_code, resp.text)
            if photo_url:
                # La foto puede fallar (url rota, formato no soportado) sin perder la alerta
                _send_text_fallback(text)
    except requests.RequestException as exc:
        logger.error("Error de red enviando a Telegram: %s", exc)


def _send_text_fallback(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.error("Error de red en fallback de texto: %s", exc)
