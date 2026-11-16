"""Small JSON-over-HTTPS helper used by the public API clients.

The project deliberately uses the Python standard library instead of a third-
party HTTP package. Requests carry a descriptive User-Agent, a timeout, and no
credentials: Open-Meteo and Frankfurter are free and keyless.

All failures are translated into project exceptions so callers never need to
handle ``urllib`` details.
"""

from __future__ import annotations

import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .errors import APIConnectionError, APIResponseError, APITimeoutError, UpstreamAPIError

DEFAULT_TIMEOUT_SECONDS = 10.0
USER_AGENT = "B9-RealTime-Information-Assistant/1.0 (+educational project)"


def _read_error_detail(error: HTTPError) -> str:
    """Return a short, safe error message from an HTTP error response."""

    try:
        raw = error.read()
    except Exception:  # pragma: no cover - defensive only
        return ""
    try:
        text = raw.decode("utf-8", errors="replace").strip()
    except Exception:  # pragma: no cover - defensive only
        return ""
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text[:300]
    if isinstance(payload, dict):
        for key in ("message", "error", "detail", "reason"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:300]
    return text[:300]


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Fetch a URL and decode its JSON body.

    Raises:
        UpstreamAPIError: the server returned an HTTP error status.
        APITimeoutError: the request timed out.
        APIConnectionError: the server could not be reached.
        APIResponseError: the body was not valid JSON.
    """

    if params:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        full_url = f"{url}?{query}" if query else url
    else:
        full_url = url

    request = Request(
        full_url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        raise UpstreamAPIError(exc.code, _read_error_detail(exc)) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise APITimeoutError(
            "The request timed out. Check the connection and try again."
        ) from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise APITimeoutError(
                "The request timed out. Check the connection and try again."
            ) from exc
        raise APIConnectionError(
            "The service could not be reached. Check the internet connection and try again."
        ) from exc
    except OSError as exc:
        raise APIConnectionError(
            "The service could not be reached. Check the internet connection and try again."
        ) from exc

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise APIResponseError("The API returned a response that was not valid UTF-8.") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise APIResponseError("The API returned a response that was not valid JSON.") from exc
