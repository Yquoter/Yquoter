"""Tests for report generation (reporting.py)."""

import os
import tempfile

import pandas as pd
import pytest

from yquoter.reporting import (
    _generate_stock_report,
    prepare_chart_data,
    render_chart,
    ReportConfig,
)
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

    def test_report_with_config_default(self):
        """ReportConfig with all defaults should work identically to no config."""
        report = _generate_stock_report(
            market="cn",
            code="MOCK",
            start="20260501",
            end="20260503",
            source="report_mock",
            config=ReportConfig(),
        )
        assert isinstance(report, str)
        assert len(report) > 100
        assert "##" in report

    def test_report_with_config_html(self):
        """HTML output format should produce an HTML document."""
        report = _generate_stock_report(
            market="cn",
            code="MOCK",
            start="20260501",
            end="20260503",
            source="report_mock",
            config=ReportConfig(output_format="html", chart_backend="svg"),
        )
        assert isinstance(report, str)
        assert "<!DOCTYPE html>" in report
        assert "<svg" in report

    def test_report_with_config_custom_output_dir(self):
        """Config output_dir should be respected."""
        with tempfile.TemporaryDirectory() as tmp:
            report = _generate_stock_report(
                market="cn",
                code="MOCK",
                start="20260501",
                end="20260503",
                source="report_mock",
                config=ReportConfig(output_dir=tmp),
            )
            files = os.listdir(tmp)
            assert len(files) == 1
            assert files[0].endswith(".md")


class TestRenderChart:
    @pytest.fixture
    def chart_df(self):
        dates = pd.date_range("2026-05-01", periods=5, freq="B")
        return pd.DataFrame(
            {
                "Open": [100, 102, 101, 103, 102],
                "High": [105, 106, 104, 107, 105],
                "Low": [99, 100, 100, 102, 101],
                "Close": [102, 101, 103, 102, 104],
                "Volume": [1000, 1200, 1100, 1300, 1150],
            },
            index=dates,
        )

    def test_render_chart_markdown_default(self, chart_df):
        result = render_chart(chart_df, "TEST", title="T", ylabel="Y")
        assert result is not None
        assert result.startswith("data:image/")

    def test_render_chart_markdown_explicit_svg(self, chart_df):
        result = render_chart(
            chart_df, "TEST", backend="svg", fmt="markdown",
            title="T", ylabel="Y",
        )
        assert result is not None
        assert result.startswith("data:image/svg+xml;base64,")

    def test_render_chart_html_svg(self, chart_df):
        result = render_chart(
            chart_df, "TEST", backend="svg", fmt="html",
            title="T", ylabel="Y",
        )
        assert result is not None
        assert result.startswith("<svg")

    def test_render_chart_unknown_backend(self, chart_df):
        result = render_chart(
            chart_df, "TEST", backend="nonexistent_xyz",
            title="T", ylabel="Y",
        )
        assert result is None

    def test_prepare_chart_data(self):
        df = MockDataSource._history_df()
        df_plot, err = prepare_chart_data(df, "TEST")
        assert err is None
        assert df_plot is not None
        assert "Open" in df_plot.columns
        assert "MA20" in df_plot.columns
