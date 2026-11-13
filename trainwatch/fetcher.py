from __future__ import annotations

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


class FetchError(Exception):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _retry_after(resp: httpx.Response) -> float | None:
    v = resp.headers.get("Retry-After")
    try:
        return float(v) if v else None
    except ValueError:
        return None


class Fetcher:
    """Один httpx-клиент на весь процесс: keep-alive + сохранение cookie (PHPSESSID, WAF)."""

    def __init__(self, timeout: float):
        self._warmed_up = False
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=15),
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,kk;q=0.8,en;q=0.7",
            },
        )

    async def get(self, url: str) -> str:
        # Язык хранится в PHP-сессии: _locale=ru переключает его начиная со СЛЕДУЮЩЕГО ответа.
        # Парсер от языка не зависит, это только для читаемых названий в уведомлениях.
        if "_locale=" not in url:
            url += ("&" if "?" in url else "?") + "_locale=ru"
        if not self._warmed_up:
            self._warmed_up = True
            try:
                await self._client.get(url)
            except httpx.HTTPError:
                pass
        try:
            resp = await self._client.get(url)
        except httpx.TimeoutException as e:
            raise FetchError(f"таймаут запроса: {e.__class__.__name__}") from e
        except httpx.HTTPError as e:
            raise FetchError(f"сетевая ошибка: {e.__class__.__name__}: {e}") from e

        if resp.status_code in (429, 503):
            raise FetchError(f"сайт ограничил запросы (HTTP {resp.status_code})", _retry_after(resp))
        if resp.status_code != 200:
            raise FetchError(f"HTTP {resp.status_code}")
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype:
            raise FetchError(f"неожиданный content-type: {ctype}")
        return resp.text

    async def aclose(self) -> None:
        await self._client.aclose()
