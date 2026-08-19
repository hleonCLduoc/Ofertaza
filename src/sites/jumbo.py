from . import _constructorio as cio

SITE_ID = "jumbo"

CATEGORIES = [
    "arroz",
    "aceite",
    "detergente",
    "papel higienico",
    "bebidas",
    "cecinas",
    "lacteos",
    "limpieza hogar",
]

KEY = "key_JopvNXKS61kwGkBe"
PAGE_SIZE = 40

session = cio.make_session()


def fetch_page(term, page):
    return cio.fetch_page(session, KEY, PAGE_SIZE, term, page)


def get_pagination(page_data):
    return cio.get_pagination(page_data, PAGE_SIZE)


def iter_products(page_data):
    yield from cio.iter_products(page_data, default_seller="Jumbo")
