from . import _constructorio as cio

SITE_ID = "easy"

CATEGORIES = [
    "taladro",
    "pintura interior",
    "cama europea 1.5 plazas",
    "cama europea 2 plazas",
    "cama king size",
    "cama",
    "frazadas",
    "sabanas",
    "tv",
]

KEY = "key_AimxrTjorsjiKQPy"
PAGE_SIZE = 40

session = cio.make_session()


def fetch_page(term, page):
    return cio.fetch_page(session, KEY, PAGE_SIZE, term, page)


def get_pagination(page_data):
    return cio.get_pagination(page_data, PAGE_SIZE)


def iter_products(page_data):
    yield from cio.iter_products(page_data, default_seller="Easy")
