"""Tests for chart_renderer.py"""

import pandas as pd
import pytest

from yquoter.chart_renderer import (
    register_renderer,
    get_renderer,
    _resolve_backend,
    _RENDERER_REGISTRY,
    MatplotlibRenderer,
    SvgRenderer,
    PlotlyRenderer,
)


# ---------------------------------------------------------------------------
# Sample preprocessed DataFrame
# ---------------------------------------------------------------------------

@pytest.fixture
def chart_df():
    """A preprocessed DataFrame ready for chart rendering."""
    dates = pd.date_range("2026-05-01", periods=5, freq="B")
    df = pd.DataFrame(
        {
            "Open": [100, 102, 101, 103, 102],
            "High": [105, 106, 104, 107, 105],
            "Low": [99, 100, 100, 102, 101],
            "Close": [102, 101, 103, 102, 104],
            "Volume": [1000, 1200, 1100, 1300, 1150],
            "MA20": [101, 101.5, 102, 102.5, 103],
        },
        index=dates,
    )
    return df


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_register_and_get(self):
        class DummyRenderer:
            name = "dummy_test"

            def render(self, df, code, title, ylabel):
                return b"png_data"

            def render_interactive(self, df, code, title, ylabel):
                raise NotImplementedError

            @staticmethod
            def is_available():
                return True

        r = DummyRenderer()
        register_renderer(r)
        assert get_renderer("dummy_test") is r
        # cleanup
        _RENDERER_REGISTRY.pop("dummy_test", None)

    def test_get_unknown_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_renderer("nonexistent_renderer_xyz")

    def test_register_overwrites(self):
        class R1:
            name = "overwrite_test"

            def render(self, df, code, title, ylabel):
                return b"v1"

            def render_interactive(self, df, code, title, ylabel):
                raise NotImplementedError

            @staticmethod
            def is_available():
                return True

        class R2:
            name = "overwrite_test"

            def render(self, df, code, title, ylabel):
                return b"v2"

            def render_interactive(self, df, code, title, ylabel):
                raise NotImplementedError

            @staticmethod
            def is_available():
                return True

        register_renderer(R1())
        register_renderer(R2())
        assert get_renderer("overwrite_test").render(None, "", "", "") == b"v2"
        _RENDERER_REGISTRY.pop("overwrite_test", None)


# ---------------------------------------------------------------------------
# SVG renderer tests (always available)
# ---------------------------------------------------------------------------

class TestSvgRenderer:
    def test_is_available(self):
        assert SvgRenderer.is_available()

    def test_render_returns_bytes(self, chart_df):
        r = SvgRenderer()
        result = r.render(chart_df, "TEST", "Test Chart", "Price")
        assert isinstance(result, bytes)
        assert result.startswith(b"<svg")

    def test_render_interactive_returns_svg_string(self, chart_df):
        r = SvgRenderer()
        result = r.render_interactive(chart_df, "TEST", "Test Chart", "Price")
        assert isinstance(result, str)
        assert result.startswith("<svg")

    def test_render_empty_df(self):
        r = SvgRenderer()
        df = pd.DataFrame({"Open": [], "High": [], "Low": [], "Close": [], "Volume": []})
        result = r.render(df, "T", "T", "Y")
        assert result == b""

    def test_render_without_ma20(self):
        r = SvgRenderer()
        dates = pd.date_range("2026-05-01", periods=3, freq="B")
        df = pd.DataFrame(
            {
                "Open": [100, 101, 102],
                "High": [105, 106, 104],
                "Low": [99, 100, 100],
                "Close": [101, 102, 103],
                "Volume": [1000, 1100, 1200],
            },
            index=dates,
        )
        result = r.render(df, "T", "T", "Y")
        assert b"<svg" in result

    def test_code_appears_in_svg_output(self, chart_df):
        """The code parameter should appear in the SVG title."""
        r = SvgRenderer()
        result = r.render(chart_df, "600519", "K-Line Chart", "Price")
        assert b"600519" in result


# ---------------------------------------------------------------------------
# Matplotlib renderer tests
# ---------------------------------------------------------------------------

class TestMatplotlibRenderer:
    def test_is_available(self):
        available = MatplotlibRenderer.is_available()
        assert isinstance(available, bool)

    @pytest.mark.skipif(
        not MatplotlibRenderer.is_available(),
        reason="matplotlib/mplfinance not installed",
    )
    def test_render_returns_bytes(self, chart_df):
        r = MatplotlibRenderer()
        result = r.render(chart_df, "TEST", "Test Chart", "Price")
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_render_interactive_raises(self, chart_df):
        r = MatplotlibRenderer()
        with pytest.raises(NotImplementedError):
            r.render_interactive(chart_df, "T", "T", "Y")


# ---------------------------------------------------------------------------
# Plotly renderer tests
# ---------------------------------------------------------------------------

class TestPlotlyRenderer:
    def test_is_available(self):
        available = PlotlyRenderer.is_available()
        assert isinstance(available, bool)

    @pytest.mark.skipif(
        not PlotlyRenderer.is_available(),
        reason="plotly not installed",
    )
    def test_render_interactive_returns_html(self, chart_df):
        r = PlotlyRenderer()
        result = r.render_interactive(chart_df, "TEST", "Test Chart", "Price")
        assert isinstance(result, str)
        assert "plotly" in result.lower() or "<div" in result


# ---------------------------------------------------------------------------
# Auto-resolution tests
# ---------------------------------------------------------------------------

class TestAutoResolution:
    def test_auto_markdown_resolves(self):
        name = _resolve_backend("auto", "markdown")
        assert name in ("matplotlib", "svg")
        assert name in _RENDERER_REGISTRY

    def test_auto_html_resolves(self):
        name = _resolve_backend("auto", "html")
        assert name in ("plotly", "svg")
        assert name in _RENDERER_REGISTRY

    def test_explicit_svg_resolves(self):
        name = _resolve_backend("svg", "markdown")
        assert name == "svg"

    def test_explicit_backend_not_installed(self):
        if "matplotlib" not in _RENDERER_REGISTRY:
            with pytest.raises(RuntimeError, match="Unknown chart backend"):
                _resolve_backend("matplotlib", "markdown")

    def test_explicit_unknown_backend(self):
        with pytest.raises(RuntimeError, match="Unknown chart backend"):
            _resolve_backend("nonexistent_xyz", "markdown")

    def test_matplotlib_html_raises(self):
        if "matplotlib" in _RENDERER_REGISTRY:
            with pytest.raises(RuntimeError, match="does not support interactive"):
                _resolve_backend("matplotlib", "html")


# ---------------------------------------------------------------------------
# __all__ exports test
# ---------------------------------------------------------------------------

class TestPublicAPI:
    def test_all_exports(self):
        from yquoter.chart_renderer import __all__
        assert "register_renderer" in __all__
        assert "get_renderer" in __all__

    def test_private_names_not_exported(self):
        from yquoter.chart_renderer import __all__
        assert "_RENDERER_REGISTRY" not in __all__
        assert "_resolve_backend" not in __all__
        assert "_supports_interactive" not in __all__
