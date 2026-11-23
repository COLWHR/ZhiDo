from __future__ import annotations

import json
import threading
import time
from typing import Dict, Iterable, Tuple

from app.core.config import settings


# path prefix -> (max requests, window seconds)
DEFAULT_RULES: Dict[str, Tuple[int, int]] = {
    "/api/v1/auth/login": (10, 60),
    "/api/v1/auth/register": (5, 60),
    "/api/v1/auth/refresh": (20, 60),
    "/api/v1/users/": (20, 60),
    "/api/v1/upload": (20, 60),
    "/api/v1/agents/chat": (30, 60),
    "/api/v1/duxin": (60, 60),
    "/api/v1/skills/sync": (2, 300),
}


class SlidingWindowLimiter:
    """Tiny in-process limiter.

    It is deliberately per-process: good enough to stop accidental abuse and
    runaway loops. For multi-worker deployments put a real gateway limiter in
    front of the app.
    """

    def __init__(self, rules: Dict[str, Tuple[int, int]] | None = None) -> None:
        self.rules = dict(rules or DEFAULT_RULES)
        self._hits: Dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def _match(self, path: str) -> Tuple[str, int, int] | None:
        for prefix, (limit, window) in self.rules.items():
            if path.startswith(prefix):
                return prefix, limit, window
        return None

    def check(self, path: str, client_key: str) -> Tuple[bool, int, int]:
        """Return (allowed, remaining, retry_after_seconds)."""
        matched = self._match(path)
        if matched is None:
            return True, 0, 0
        prefix, limit, window = matched
        now = time.monotonic()
        bucket = f"{prefix}:{client_key}"

        with self._lock:
            self._sweep(now)
            hits = [stamp for stamp in self._hits.get(bucket, []) if now - stamp < window]
            if len(hits) >= limit:
                retry_after = max(1, int(window - (now - hits[0])))
                self._hits[bucket] = hits
                return False, 0, retry_after
            hits.append(now)
            self._hits[bucket] = hits
            return True, max(0, limit - len(hits)), 0

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < 60:
            return
        self._last_sweep = now
        for key in list(self._hits.keys()):
            window = 60
            for prefix, (_, w) in self.rules.items():
                if key.startswith(prefix):
                    window = w
                    break
            if all(now - stamp >= window for stamp in self._hits[key]):
                self._hits.pop(key, None)


limiter = SlidingWindowLimiter()


class RateLimitMiddleware:
    """Pure ASGI middleware so streaming responses are not buffered."""

    def __init__(self, app, rules: Dict[str, Tuple[int, int]] | None = None, enabled: bool | None = None):
        self.app = app
        self.limiter = SlidingWindowLimiter(rules) if rules else limiter
        self._enabled_override = enabled

    @property
    def enabled(self) -> bool:
        if self._enabled_override is not None:
            return self._enabled_override
        return bool(settings.RATE_LIMIT_ENABLED)

    async def __call__(self, scope, receive, send):
        if not self.enabled or scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        client = scope.get("client") or ("unknown", 0)
        client_key = str(client[0])

        if settings.TRUST_PROXY_HEADERS:
            for name, value in scope.get("headers", []):
                if name == b"x-forwarded-for":
                    client_key = value.decode("latin-1").split(",")[0].strip()

        allowed, remaining, retry_after = self.limiter.check(path, client_key)
        if not allowed:
            headers = [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"retry-after", str(retry_after).encode()),
                (b"x-ratelimit-remaining", b"0"),
            ]
            body = json.dumps(
                {"code": 429, "detail": "请求过于频繁，请稍后再试", "message": "请求过于频繁，请稍后再试", "data": None},
                ensure_ascii=False,
            ).encode("utf-8")
            await send({"type": "http.response.start", "status": 429, "headers": headers})
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return

        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Attach defensive headers to every response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def _send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                existing = {name.lower() for name, _ in headers}
                defaults: Iterable[Tuple[bytes, bytes]] = (
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"SAMEORIGIN"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                )
                for name, value in defaults:
                    if name not in existing:
                        headers.append((name, value))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, _send)
