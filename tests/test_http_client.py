"""Offline tests for the shared HTTP helper (no network access)."""

from __future__ import annotations

import io
import json
import socket
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.errors import (  # noqa: E402
    APIConnectionError,
    APIResponseError,
    APITimeoutError,
    UpstreamAPIError,
)
from src.http_client import get_json  # noqa: E402


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def http_error(status: int, body: bytes) -> HTTPError:
    return HTTPError("https://example.test", status, "error", hdrs=None, fp=io.BytesIO(body))


class GetJsonTests(unittest.TestCase):
    def test_decodes_valid_json_and_sends_query(self) -> None:
        with patch("src.http_client.urlopen", return_value=FakeResponse(b'{"ok": true}')) as mocked:
            result = get_json("https://example.test/data", {"q": "Berlin", "count": 1})
        self.assertEqual(result, {"ok": True})
        request = mocked.call_args.args[0]
        self.assertIn("q=Berlin", request.full_url)
        self.assertIn("count=1", request.full_url)

    def test_http_error_becomes_upstream_error_with_detail(self) -> None:
        error = http_error(422, b'{"message": "invalid currency: XYZ"}')
        with patch("src.http_client.urlopen", side_effect=error):
            with self.assertRaises(UpstreamAPIError) as context:
                get_json("https://example.test/data")
        self.assertEqual(context.exception.status_code, 422)
        self.assertIn("invalid currency: XYZ", str(context.exception))

    def test_timeout_becomes_timeout_error(self) -> None:
        with patch("src.http_client.urlopen", side_effect=URLError(socket.timeout("timed out"))):
            with self.assertRaises(APITimeoutError):
                get_json("https://example.test/data")

    def test_connection_error_becomes_connection_error(self) -> None:
        with patch("src.http_client.urlopen", side_effect=URLError("name resolution failed")):
            with self.assertRaises(APIConnectionError):
                get_json("https://example.test/data")

    def test_invalid_json_becomes_response_error(self) -> None:
        with patch("src.http_client.urlopen", return_value=FakeResponse(b"not json")):
            with self.assertRaises(APIResponseError):
                get_json("https://example.test/data")

    def test_invalid_utf8_becomes_response_error(self) -> None:
        with patch("src.http_client.urlopen", return_value=FakeResponse(b"\xff\xfe")):
            with self.assertRaises(APIResponseError):
                get_json("https://example.test/data")

    def test_json_body_is_parsed_not_returned_raw(self) -> None:
        payload = [{"date": "2026-11-16", "base": "USD", "quote": "EUR", "rate": 0.9}]
        with patch(
            "src.http_client.urlopen",
            return_value=FakeResponse(json.dumps(payload).encode("utf-8")),
        ):
            result = get_json("https://example.test/data")
        self.assertEqual(result, payload)


if __name__ == "__main__":
    unittest.main()
