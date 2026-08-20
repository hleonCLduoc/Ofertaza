from . import _constructorio as cio

SITE_ID = "santaisabel"

CATEGORIES = [
    "arroz",
    "aceite",
    "detergente",
    "papel higienico",
    "bebidas",
    "cecinas",
    "lacteos",
    "limpieza hogar",
    "conservas",
    "cereales",
    "galletas",
    "chocolates",
    "snacks",
    "pastas",
    "salsas",
    "congelados",
    "helados",
    "yogurt",
    "vinos",
    "cervezas",
]

KEY = "key_c73M3GMIWJ8AcNnd"
PAGE_SIZE = 40

session = cio.make_session()


def fetch_page(term, page):
    return cio.fetch_page(session, KEY, PAGE_SIZE, term, page)


def get_pagination(page_data):
    return cio.get_pagination(page_data, PAGE_SIZE)


def iter_products(page_data):
    for product in cio.iter_products(page_data, default_seller="Santa Isabel"):
        # La API devuelve las URLs con el dominio legado sisa.cl, que ya
        # no sirve las páginas de producto (404). El sitio real es
        # santaisabel.cl, mismo path.
        if product["url"] and "sisa.cl" in product["url"]:
            product["url"] = product["url"].replace("sisa.cl", "santaisabel.cl")
        yield product
