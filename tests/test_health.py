import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from epacomp_tox.health import check_ctx_health


class TestCheckCtxHealth(unittest.TestCase):
    def setUp(self) -> None:
        # Patch env resolution helpers so tests do not rely on real env vars.
        patcher_key = mock.patch(
            "epacomp_tox.health.get_api_key", return_value="fake-key"
        )
        patcher_base = mock.patch(
            "epacomp_tox.health.get_base_url",
            return_value="https://example.com/ctx-api",
        )
        self.addCleanup(patcher_key.stop)
        self.addCleanup(patcher_base.stop)
        patcher_key.start()
        patcher_base.start()

    @mock.patch("urllib.request.urlopen")
    def test_health_check_success_on_200(self, mock_urlopen: mock.MagicMock) -> None:
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        mock_urlopen.return_value = response

        result = check_ctx_health()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 200)
        self.assertIn("url", result)
        mock_urlopen.assert_called_once()

    @mock.patch("urllib.request.urlopen")
    def test_health_check_treats_404_as_ok(self, mock_urlopen: mock.MagicMock) -> None:
        error = urllib.error.HTTPError(
            url="https://example.com/ctx-api/health",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )
        mock_urlopen.side_effect = error

        result = check_ctx_health()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], 404)
        self.assertIn("url", result)
        mock_urlopen.assert_called_once()

    @mock.patch("urllib.request.urlopen")
    def test_health_check_raises_on_repeated_failure(
        self, mock_urlopen: mock.MagicMock
    ) -> None:
        failures = [
            urllib.error.HTTPError(
                url="https://example.com/ctx-api/health",
                code=503,
                msg="Service Unavailable",
                hdrs=None,
                fp=None,
            ),
            urllib.error.URLError("temporary DNS failure"),
            urllib.error.HTTPError(
                url="https://example.com/ctx-api",
                code=502,
                msg="Bad Gateway",
                hdrs=None,
                fp=None,
            ),
        ]
        mock_urlopen.side_effect = failures

        with self.assertRaises(RuntimeError):
            check_ctx_health()

        self.assertEqual(mock_urlopen.call_count, 3)


if __name__ == "__main__":
    unittest.main()
