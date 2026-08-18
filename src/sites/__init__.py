from . import falabella

# Registro de sitios disponibles. Cada módulo debe exponer:
#   SITE_ID: str
#   CATEGORIES: list[str]
#   fetch_page(term, page) -> dict | None   (datos ya parseados de esa página)
#   iter_products(page_data) -> generador de dicts normalizados
#   get_pagination(page_data) -> (count, per_page)
SITES = {
    falabella.SITE_ID: falabella,
}
