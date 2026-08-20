from . import abcdin, easy, falabella, hites, jumbo, kitchencenter, marathon, paris, preunic, ripley, santaisabel, sodimac, surprice, theline, tricot

# Registro de sitios disponibles. Cada módulo debe exponer:
#   SITE_ID: str
#   CATEGORIES: list[str]
#   fetch_page(term, page) -> dict | None   (datos ya parseados de esa página)
#   iter_products(page_data) -> generador de dicts normalizados
#   get_pagination(page_data) -> (count, per_page)
SITES = {
    falabella.SITE_ID: falabella,
    ripley.SITE_ID: ripley,
    paris.SITE_ID: paris,
    theline.SITE_ID: theline,
    marathon.SITE_ID: marathon,
    sodimac.SITE_ID: sodimac,
    jumbo.SITE_ID: jumbo,
    hites.SITE_ID: hites,
    easy.SITE_ID: easy,
    santaisabel.SITE_ID: santaisabel,
    abcdin.SITE_ID: abcdin,
    preunic.SITE_ID: preunic,
    tricot.SITE_ID: tricot,
    kitchencenter.SITE_ID: kitchencenter,
    surprice.SITE_ID: surprice,
}
