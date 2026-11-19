# """URL rules: what is in scope, and one canonical form per URL."""
# from urllib.parse import urldefrag, urlparse

# SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".mp4", ".mp3",
#             ".css", ".js", ".xml", ".ico", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")


# def strip_www(host: str) -> str:
#     host = host.lower()
#     return host[4:] if host.startswith("www.") else host


# def _under(path: str, prefix: str) -> bool:
#     path, prefix = path.lower(), prefix.lower()
#     return path == prefix or path.startswith(prefix + "/")


# class Scope:
#     def __init__(self, start_url: str, include: str = "", exclude: list[str] | None = None):
#         p = urlparse(start_url)
#         self.scheme, self.netloc = p.scheme, p.netloc
#         self.site = strip_www(p.netloc)  # 'emiratesnbd.com' for both www and non-www
#         inc = include.strip("/")
#         self.include = "/" + inc if inc else ""
#         self.exclude = ["/" + e.strip("/") for e in (exclude or []) if e.strip("/")]

#     def normalize(self, url: str) -> str:
#         """Drop #fragment and ?query, drop trailing slash, unify www / non-www."""
#         url, _ = urldefrag(url)
#         p = urlparse(url)
#         if strip_www(p.netloc) == self.site:
#             p = p._replace(scheme=self.scheme, netloc=self.netloc)
#         return p._replace(path=p.path.rstrip("/"), params="", query="").geturl()

#     def is_page(self, url: str) -> bool:
#         """HTML page on the main site, inside include, outside exclude."""
#         p = urlparse(url)
#         path = p.path or "/"
#         if p.scheme not in ("http", "https") or strip_www(p.netloc) != self.site:
#             return False
#         if path.lower().endswith(".pdf") or path.lower().endswith(SKIP_EXT):
#             return False
#         if self.include and not _under(path, self.include):
#             return False
#         return not any(_under(path, e) for e in self.exclude)

#     def is_pdf(self, url: str) -> bool:
#         """PDF on the main site or one of its subdomains (e.g. cdn.)."""
#         p = urlparse(url)
#         host = strip_www(p.netloc)
#         if p.scheme not in ("http", "https") or not p.path.lower().endswith(".pdf"):
#             return False
#         if not (host == self.site or host.endswith("." + self.site)):
#             return False
#         return not any(_under(p.path, e) for e in self.exclude)



#  chatgpt code


"""URL rules: what is in scope, and one canonical form per URL."""

from urllib.parse import urldefrag, urljoin, urlparse

SKIP_EXT = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip",
    ".mp4", ".mp3", ".css", ".js", ".xml", ".ico", ".doc",
    ".docx", ".xls", ".xlsx", ".ppt", ".pptx"
)


def strip_www(host: str) -> str:
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _under(path: str, prefix: str) -> bool:
    path, prefix = path.lower(), prefix.lower()
    return path == prefix or path.startswith(prefix + "/")


class Scope:
    def __init__(self, start_url: str, include: str = "", exclude: list[str] | None = None):
        p = urlparse(start_url)

        self.scheme = p.scheme.lower()
        self.netloc = p.netloc.lower()
        self.site = strip_www(p.netloc)

        inc = include.strip("/")
        self.include = "/" + inc if inc else ""

        self.exclude = [
            "/" + e.strip("/")
            for e in (exclude or [])
            if e.strip("/")
        ]

    def normalize(self, url: str) -> str:
        """Resolve relative URLs and remove fragments, queries and trailing slashes."""

        url = urljoin(f"{self.scheme}://{self.netloc}/", url)
        url, _ = urldefrag(url)
        p = urlparse(url)

        if strip_www(p.netloc) == self.site:
            p = p._replace(scheme=self.scheme, netloc=self.netloc)

        path = p.path.rstrip("/") or "/"

        return p._replace(
            path=path,
            params="",
            query="",
            fragment=""
        ).geturl()

    def is_page(self, url: str) -> bool:
        """Check whether URL is an allowed HTML page on the main site."""

        p = urlparse(url)
        path = p.path or "/"

        if p.scheme.lower() not in ("http", "https"):
            return False

        if strip_www(p.netloc) != self.site:
            return False

        if path.lower().endswith(".pdf"):
            return False

        if path.lower().endswith(SKIP_EXT):
            return False

        if self.include and not _under(path, self.include):
            return False

        if any(_under(path, prefix) for prefix in self.exclude):
            return False

        return True

    def is_pdf(self, url: str) -> bool:
        """Check whether URL is a PDF on the main site or its subdomains."""

        p = urlparse(url)
        host = strip_www(p.netloc)

        if p.scheme.lower() not in ("http", "https"):
            return False

        if not p.path.lower().endswith(".pdf"):
            return False

        if not (host == self.site or host.endswith("." + self.site)):
            return False

        if any(_under(p.path, prefix) for prefix in self.exclude):
            return False

        return True
