import statistics

from config import (
    BADGE_DISCOUNT_THRESHOLD,
    DIGIT_ERROR_TOLERANCE,
    DROP_THRESHOLD,
    MIN_HISTORY_FOR_ALERT,
)


def detect_badge_discount(discount_percent):
    """Descuento declarado por el propio sitio (sin necesitar historial).
    discount_percent: entero positivo, ej. 21 para '-21%'."""
    if discount_percent is None:
        return None
    if discount_percent >= BADGE_DISCOUNT_THRESHOLD:
        return "descuento_declarado_80mas"
    return None


def detect_anomaly(new_price, history):
    """
    history: precios anteriores del mismo site+sku_id+price_type, más reciente primero.
    Devuelve (reason, reference_price) o None si no hay anomalía.
    """
    if len(history) < MIN_HISTORY_FOR_ALERT:
        return None

    reference = statistics.median(history)
    if reference <= 0:
        return None

    ratio = new_price / reference

    # Heurística 1: caída brusca vs. la mediana histórica
    if ratio <= (1 - DROP_THRESHOLD):
        return ("caida_historica", reference)

    # Heurística 2: precio = ~1/10 o ~1/100 del histórico (típico error de dígito)
    for divisor in (10, 100):
        expected = reference / divisor
        if expected > 0 and abs(new_price - expected) / expected <= DIGIT_ERROR_TOLERANCE:
            return (f"posible_error_digito_div{divisor}", reference)

    return None
