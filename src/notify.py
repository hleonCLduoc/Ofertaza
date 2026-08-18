import logging

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("notify")


def send_alert(text):
    """Envía un mensaje de Telegram si hay credenciales configuradas.
    Si no, solo lo deja en el log (útil mientras se prueba localmente)."""
    logger.warning("ALERTA: %s", text)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error("Fallo al enviar a Telegram: %s %s", resp.status_code, resp.text)
    except requests.RequestException as exc:
        logger.error("Error de red enviando a Telegram: %s", exc)
