"""Pluggable per-theme reference-image search for the vision step.

Given a short theme query (e.g. "dragon", "gothic cathedral"), fetch a few web
images so the generation/refinement agent can *simplify from real references*
instead of inventing form from primitives.

Default provider is key-free (DuckDuckGo via the ``ddgs`` package, the ``search``
extra). The provider is an interface, so a keyed API (Bing / SerpAPI / Google CSE)
can be dropped in later without touching callers. Everything degrades gracefully:
if search or download fails, an empty list is returned and the workflow proceeds.
"""

from __future__ import annotations

import io
import urllib.request
from typing import Protocol, runtime_checkable


@runtime_checkable
class ImageSearchProvider(Protocol):
    """Returns candidate image URLs for a query."""

    def search_image_urls(self, query: str, count: int) -> list[str]: ...


class DuckDuckGoProvider:
    """Key-free image search via the ``ddgs`` package (install the 'search' extra)."""

    def search_image_urls(self, query: str, count: int) -> list[str]:
        try:
            from ddgs import DDGS  # newer package name
        except Exception:
            from duckduckgo_search import DDGS  # older package name
        urls: list[str] = []
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=count):
                u = r.get("image") or r.get("image_url")
                if u:
                    urls.append(u)
        return urls


def default_provider() -> ImageSearchProvider | None:
    """The default key-free provider, or None if its dependency is missing."""
    try:
        import ddgs  # noqa: F401
    except Exception:
        try:
            import duckduckgo_search  # noqa: F401
        except Exception:
            return None
    return DuckDuckGoProvider()


def _download_as_png(url: str, *, max_px: int = 768, timeout: int = 15) -> bytes | None:
    """Download an image and normalize to a reasonably-sized PNG (or None on failure)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "printforge/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read()
        from PIL import Image

        img = Image.open(io.BytesIO(raw)).convert("RGB")
        if max(img.size) > max_px:
            scale = max_px / max(img.size)
            img = img.resize((int(img.width * scale), int(img.height * scale)))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def fetch_reference_images(
    query: str,
    *,
    count: int = 4,
    provider: ImageSearchProvider | None = None,
) -> list[bytes]:
    """Return up to ``count`` reference images (PNG bytes) for ``query``.

    Returns [] if no provider is available or nothing could be fetched.
    """
    provider = provider or default_provider()
    if provider is None or not query.strip():
        return []
    try:
        urls = provider.search_image_urls(query, max(count * 3, count))
    except Exception:
        return []
    images: list[bytes] = []
    for url in urls:
        png = _download_as_png(url)
        if png:
            images.append(png)
        if len(images) >= count:
            break
    return images
