import os

# Qué sitios están activos en este ciclo (claves del registro en sites/__init__.py)
ACTIVE_SITES = os.environ.get("ACTIVE_SITES", "falabella").split(",")

# --- Detección basada en historial ---
MIN_HISTORY_FOR_ALERT = 3
DROP_THRESHOLD = 0.55  # caída vs. mediana histórica que se considera sospechosa
DIGIT_ERROR_TOLERANCE = 0.05  # tolerancia para "falta un dígito" (precio = 1/10 o 1/100)

# --- Detección instantánea (sin historial) ---
# Si el propio sitio declara un descuento igual o mayor a este %, se alerta al toque.
BADGE_DISCOUNT_THRESHOLD = 80

# Tope de páginas a recorrer por término de búsqueda, para que catálogos enormes
# (ej. Ripley trae miles de resultados para "notebook") no disparen el tiempo de ciclo.
MAX_PAGES_PER_TERM = int(os.environ.get("MAX_PAGES_PER_TERM", "40"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Pausa entre requests a un mismo sitio, para no golpearlo agresivamente (segundos)
REQUEST_DELAY_SECONDS = float(os.environ.get("REQUEST_DELAY_SECONDS", "2.5"))

# Cada cuánto correr un ciclo completo de scraping (segundos). 1800 = 30 min.
CYCLE_INTERVAL_SECONDS = int(os.environ.get("CYCLE_INTERVAL_SECONDS", "1800"))

DB_PATH = os.environ.get("DB_PATH", "/data/precios.db")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
