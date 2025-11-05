import sys
from pathlib import Path
import unittest
from unittest import mock

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ctxpy import CtxApiError  # noqa: E402
from epacomp_tox.resources.base import BaseResource  # noqa: E402
from epacomp_tox.resources.chemical import ChemicalResource  # noqa: E402
from epacomp_tox.resources.exposure import ExposureResource  # noqa: E402
from epacomp_tox.resources.hazard import HazardResource  # noqa: E402


class TestChemicalResource(unittest.TestCase):
    @mock.patch("epacomp_tox.resources.chemical.ctx.Chemical")
    def test_batch_get_details_normalizes_list(self, mock_client_cls: mock.MagicMock) -> None:
        mock_client = mock_client_cls.return_value
        def _details_side_effect(*args, **kwargs):
            mock_client.last_metadata = {"status": 200, "request_id": "req-1"}
            return [{"id": 1}]
        mock_client.details.side_effect = _details_side_effect

        resource = ChemicalResource(api_key="fake")
        result = resource.batch_get_chemical_details(
            identifiers=["DTXSID1", "DTXSID2"],
            id_type="dtxsid",
            subset="all",
        )

        mock_client.details.assert_called_once_with(
            by="batch",
            word=["DTXSID1", "DTXSID2"],
            subset="all",
        )
        self.assertIsInstance(result, list)
        self.assertEqual(result, [{"id": 1}])
        self.assertEqual(resource.get_last_metadata(), {"status": 200, "request_id": "req-1"})

    @mock.patch("epacomp_tox.resources.chemical.ctx.Chemical")
    def test_search_msready_mass_range(self, mock_client_cls: mock.MagicMock) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.last_metadata = {"status": 200}
        mock_client.msready.return_value = [{"mass": 123.4}]

        resource = ChemicalResource(api_key="fake")
        result = resource.search_msready(
            search_type="mass-range",
            mass_start=100.0,
            mass_end=150.0,
        )

        mock_client.msready.assert_called_once_with(by="mass", start=100.0, end=150.0)
        self.assertEqual(result, [{"mass": 123.4}])


class TestExposureResource(unittest.TestCase):
    @mock.patch("epacomp_tox.resources.exposure.ctx.Exposure")
    def test_search_cpdat_handles_multiple_ids(self, mock_client_cls: mock.MagicMock) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.search_cpdat.side_effect = (
            [{"dtxsid": "DTX1"}],
            [{"dtxsid": "DTX2"}],
        )
        mock_client.last_metadata = {"status": 200, "request_id": "req-2"}

        resource = ExposureResource(api_key="fake")
        result = resource.search_cpdat(vocab_name="fc", dtxsids=["DTX1", "DTX2"])

        self.assertEqual(mock_client.search_cpdat.call_count, 2)
        self.assertEqual(result, [{"dtxsid": "DTX1"}, {"dtxsid": "DTX2"}])
        self.assertEqual(resource.get_last_metadata(), {"status": 200, "request_id": "req-2"})

    @mock.patch("epacomp_tox.resources.exposure.ctx.Exposure")
    def test_search_exposures_requires_identifier(self, mock_client_cls: mock.MagicMock) -> None:
        resource = ExposureResource(api_key="fake")
        with self.assertRaises(ValueError):
            resource.search_exposures(data_type="pathways", dtxsids=[])


class TestHazardResource(unittest.TestCase):
    @mock.patch("epacomp_tox.resources.hazard.ctx.Hazard")
    def test_batch_search_hazard_normalizes_values(self, mock_client_cls: mock.MagicMock) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.batch_search.return_value = {"DTX1": {"score": 1}}

        resource = HazardResource(api_key="fake")
        result = resource.batch_search_hazard(
            data_type="all",
            dtxsids=["DTX1"],
            summary=True,
        )

        self.assertEqual(result, {"DTX1": [{"score": 1}]})


class DummyResource(BaseResource):
    name = "dummy"
    description = "dummy desc"

    def __init__(self):
        super().__init__(api_key="fake")
        self.client = mock.Mock()

    def get_tools(self):
        return []

    def execute_tool(self, tool_name, parameters):
        raise NotImplementedError


class TestBaseResourceRetry(unittest.TestCase):
    @mock.patch("epacomp_tox.resources.base.time.sleep")
    def test_retry_on_retryable_error(self, mock_sleep: mock.MagicMock) -> None:
        resource = DummyResource()
        calls = {"count": 0}

        def flaky_call():
            calls["count"] += 1
            if calls["count"] == 1:
                raise CtxApiError(status=503, message="temporary")
            resource.client.last_metadata = {"status": 200}
            return "ok"

        result = resource._with_retry(flaky_call, retries=3, base_delay=0)
        self.assertEqual(result, "ok")
        self.assertEqual(calls["count"], 2)
        self.assertEqual(resource.get_last_metadata(), {"status": 200})
        mock_sleep.assert_called_once()

    @mock.patch("epacomp_tox.resources.base.time.sleep")
    def test_no_retry_on_non_retryable_error(self, mock_sleep: mock.MagicMock) -> None:
        resource = DummyResource()

        with self.assertRaises(CtxApiError):
            resource._with_retry(
                lambda: (_ for _ in ()).throw(CtxApiError(status=400, message="bad input")),
                retries=2,
                base_delay=0,
            )
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
