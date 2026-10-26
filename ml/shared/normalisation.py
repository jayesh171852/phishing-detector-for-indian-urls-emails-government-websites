from urllib.parse import urlparse


def norm(url):
    p = urlparse(str(url).strip())
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = "" if p.path in ("", "/") else p.path
    return netloc + path + (("?" + p.query) if p.query else "")
