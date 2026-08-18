import os

# Términos de búsqueda a monitorear (categoría "tecnología" para partir)
SEARCH_TERMS = [
    "notebook",
    "celular",
    "smartphone",
    "computador",
]

# Cuántas observaciones históricas se guardan como referencia por SKU antes
# de empezar a detectar anomalías (evita alertar con muy poco historial).
MIN_HISTORY_FOR_ALERT = 3

# Caída porcentual vs. la mediana histórica que se considera sospechosa.
DROP_THRESHOLD = 0.55  # 55%

# Tolerancia para detectar "falta un dígito" (precio = 1/10 o 1/100 del histórico)
DIGIT_ERROR_TOLERANCE = 0.05  # 5%

BASE_URL = "https://www.falabella.com/falabella-cl/search"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Pausa entre requests para no golpear el sitio agresivamente (segundos)
REQUEST_DELAY_SECONDS = float(os.environ.get("REQUEST_DELAY_SECONDS", "2.5"))

# Cada cuánto correr un ciclo completo de scraping (segundos). 1800 = 30 min.
CYCLE_INTERVAL_SECONDS = int(os.environ.get("CYCLE_INTERVAL_SECONDS", "1800"))

DB_PATH = os.environ.get("DB_PATH", "/data/precios.db")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
