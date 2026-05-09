"""Tests for report generation (reporting.py)."""

import pytest

from yquoter.reporting import _generate_stock_report
from yquoter.datasource import _SOURCE_REGISTRY
from tests.conftest import MockDataSource


@pytest.fixture(autouse=True)
def _register_mock():
    _SOURCE_REGISTRY["report_mock"] = MockDataSource()
    yield
    _SOURCE_REGISTRY.pop("report_mock", None)


class TestReport:
    def test_report_structure(self):
        report = _generate_stock_report(
            market="cn",
            code="MOCK",
            start="20260501",
            end="20260503",
            source="report_mock",
            language="en",
        )
        assert isinstance(report, str)
        assert len(report) > 100

        # Should contain key section headers.
        assert "##" in report  # markdown headers

    def test_report_chinese(self):
        report = _generate_stock_report(
            market="cn",
            code="MOCK",
            start="20260501",
            end="20260503",
            source="report_mock",
            language="cn",
        )
        assert isinstance(report, str)
        assert len(report) > 100

    def test_report_with_llm_provider(self):
        """LLM provider is optional; without keys it should skip gracefully."""
        report = _generate_stock_report(
            market="cn",
            code="MOCK",
            start="20260501",
            end="20260503",
            source="report_mock",
            language="en",
            llm_provider="deepseek",
        )
        assert isinstance(report, str)
