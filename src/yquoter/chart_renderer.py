# yquoter/chart_renderer.py
"""Pluggable chart rendering backends for Yquoter reports.

Provides a :class:`ChartRenderer` protocol, a string-keyed registry,
and built-in renderers for matplotlib, SVG (pure Python), and Plotly.
"""

from __future__ import annotations

import logging
import math
from io import BytesIO
from typing import Dict, Protocol

import pandas as pd

__all__ = ["register_renderer", "get_renderer"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class ChartRenderer(Protocol):
    """Protocol for chart rendering backends.

    Each renderer produces a candlestick chart from a preprocessed
    DataFrame.  Two output modes are supported:

    * ``render()`` — static image bytes (PNG or SVG)
    * ``render_interactive()`` — HTML fragment string
    """

    name: str

    def render(self, df: pd.DataFrame, code: str, title: str, ylabel: str) -> bytes:
        """Render a static chart image.

        Returns:
            PNG bytes (matplotlib, plotly) or SVG bytes (svg backend).
        """
        ...

    def render_interactive(
        self, df: pd.DataFrame, code: str, title: str, ylabel: str
    ) -> str:
        """Render an interactive HTML fragment.

        Returns:
            HTML string (``<div id="...">`` with Plotly.js, or ``<svg>``).

        Raises:
            NotImplementedError: If this renderer does not support
                interactive output.
        """
        ...

    @staticmethod
    def is_available() -> bool:
        """Return ``True`` if the required libraries are importable."""
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_RENDERER_REGISTRY: Dict[str, ChartRenderer] = {}


def register_renderer(renderer: ChartRenderer) -> None:
    """Register a chart renderer backend.

    Args:
        renderer: A :class:`ChartRenderer` instance.
    """
    _RENDERER_REGISTRY[renderer.name] = renderer
    logger.info("Chart renderer registered: %s", renderer.name)


def get_renderer(name: str) -> ChartRenderer:
    """Look up a renderer by name.

    Args:
        name: Renderer name (e.g. ``"svg"``, ``"matplotlib"``).

    Returns:
        The ChartRenderer instance.

    Raises:
        KeyError: If the name is not registered.
    """
    return _RENDERER_REGISTRY[name]


def _resolve_backend(requested: str, fmt: str) -> str:
    """Resolve a backend name to an available renderer.

    Args:
        requested: Backend name (``"auto"``, ``"matplotlib"``, ``"svg"``,
            ``"plotly"``).
        fmt: Target format (``"markdown"`` or ``"html"``).

    Returns:
        Name of the resolved renderer.

    Raises:
        RuntimeError: If the requested backend is not installed or
            does not support the target format.
    """
    if requested != "auto":
        if requested not in _RENDERER_REGISTRY:
            raise RuntimeError(
                f"Unknown chart backend: '{requested}'. "
                f"Available: {sorted(_RENDERER_REGISTRY.keys())}"
            )
        r = _RENDERER_REGISTRY[requested]
        if fmt == "html":
            if not _supports_interactive(r):
                raise RuntimeError(
                    f"Backend '{requested}' does not support interactive "
                    f"HTML output. Choose 'plotly' or 'svg'."
                )
        return requested

    # "auto": pick the first available from the priority list.
    if fmt == "markdown":
        order = ["matplotlib", "svg"]
    else:
        order = ["plotly", "svg"]

    for name in order:
        if name in _RENDERER_REGISTRY and _RENDERER_REGISTRY[name].is_available():
            return name

    raise RuntimeError(
        "No chart backend is available. Install matplotlib "
        "(pip install yquoter[chart]) or plotly (pip install yquoter[plotly])."
    )


def _supports_interactive(renderer: ChartRenderer) -> bool:
    """Return True if *renderer* supports ``render_interactive()``.

    Checks for a ``_supports_interactive`` sentinel attribute set
    on interactive-capable renderer classes (e.g. PlotlyRenderer,
    SvgRenderer).

    Args:
        renderer: A :class:`ChartRenderer` instance.

    Returns:
        bool: ``True`` if the renderer supports interactive output.
    """
    return getattr(renderer, "_supports_interactive", False)


def _svg_tag(name, attrib=None, text=None, **extra):
    """Build an XML/HTML tag string.

    Args:
        name: Tag name (e.g., ``"line"``, ``"rect"``).
        attrib: Optional dictionary of attribute name-value pairs.
        text: Optional inner text content. If ``None``, the tag
            is self-closing.
        **extra: Additional attributes as keyword arguments.

    Returns:
        str: The constructed tag string.
    """
    a = {}
    if attrib:
        a.update(attrib)
    a.update(extra)
    parts = [f"<{name}"]
    for k, v in a.items():
        parts.append(f' {k}="{v}"')
    if text is not None:
        parts.append(f">{text}</{name}>")
    else:
        parts.append("/>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Built-in: Matplotlib + mplfinance
# ---------------------------------------------------------------------------

class MatplotlibRenderer:
    """Candlestick chart renderer using matplotlib + mplfinance.

    Produces high-quality PNG images.
    """

    name = "matplotlib"
    _supports_interactive = False

    @staticmethod
    def is_available() -> bool:
        try:
            import matplotlib.pyplot as plt  # noqa: F401
            import mplfinance as mpf  # noqa: F401
            return True
        except ImportError:
            return False

    def render(self, df: pd.DataFrame, code: str, title: str, ylabel: str) -> bytes:
        import matplotlib.pyplot as plt
        import mplfinance as mpf

        plt.rcParams['font.sans-serif'] = [
            'Microsoft YaHei', 'SimHei', 'Arial Unicode MS',
            'Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'sans-serif',
        ]
        plt.rcParams['axes.unicode_minus'] = False

        style = mpf.make_mpf_style(
            base_mpf_style='yahoo',
            gridstyle='-',
            rc={'font.family': ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']},
        )

        add_plots = []
        if 'MA20' in df.columns:
            add_plots.append(
                mpf.make_addplot(df['MA20'], color='b', secondary_y=False)
            )

        fig, _axes = mpf.plot(
            df, type='candle', style=style, title=title,
            ylabel=ylabel, volume=True, addplot=add_plots,
            figratio=(16, 9), figscale=0.8, returnfig=True,
        )

        buf = BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def render_interactive(
        self, df: pd.DataFrame, code: str, title: str, ylabel: str
    ) -> str:
        raise NotImplementedError(
            "Matplotlib does not support interactive HTML output."
        )


# ---------------------------------------------------------------------------
# Built-in: Pure-Python SVG
# ---------------------------------------------------------------------------

class SvgRenderer:
    """Candlestick chart renderer using only the Python standard library.

    Zero extra dependencies.  Always available.
    """

    name = "svg"
    _supports_interactive = True

    @staticmethod
    def is_available() -> bool:
        return True

    def render(self, df: pd.DataFrame, code: str, title: str, ylabel: str) -> bytes:
        svg_str = self._build_svg(df, code, title, ylabel)
        return svg_str.encode('utf-8')

    def render_interactive(
        self, df: pd.DataFrame, code: str, title: str, ylabel: str
    ) -> str:
        # SVG is static; for HTML format we return the SVG markup directly.
        return self._build_svg(df, code, title, ylabel)

    def _build_svg(
        self,
        df: pd.DataFrame,
        code: str,
        title: str = "",
        ylabel: str = "",
        width: int = 800,
        height: int = 520,
    ) -> str:
        n = len(df)
        if n == 0:
            return ""

        # ---- layout constants ----
        pad_left = 70
        pad_right = 20
        pad_top = 30
        pad_bottom = 25
        volume_ratio = 0.28
        gap = 10

        price_bottom = height - pad_bottom - int(
            (height - pad_top - pad_bottom - gap) * volume_ratio
        ) - gap
        price_top = pad_top
        price_h = price_bottom - price_top

        vol_top = price_bottom + gap
        vol_bottom = height - pad_bottom
        vol_h = vol_bottom - vol_top

        plot_width = width - pad_left - pad_right
        if plot_width < 10 or price_h < 20 or vol_h < 10:
            return ""

        candle_w = max(1, min(int(plot_width / n * 0.8), int(plot_width / n)))

        # ---- price scaling ----
        price_high = float(df['High'].max())
        price_low = float(df['Low'].min())
        price_range = price_high - price_low
        if price_range <= 0:
            price_range = price_high * 0.02 or 1.0
        price_low -= price_range * 0.05
        price_high += price_range * 0.05
        price_range = price_high - price_low

        def _price_y(v):
            return price_bottom - (v - price_low) / price_range * price_h

        # ---- volume scaling ----
        vol_max = float(df['Volume'].max())
        if vol_max <= 0:
            vol_max = 1.0

        def _vol_y(v):
            return vol_bottom - (v / vol_max) * vol_h

        # ---- X coordinates ----
        xs = [pad_left + int(plot_width * (i + 0.5) / n) for i in range(n)]

        lines: list[str] = []
        lines.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}">'
        )
        lines.append(f'<rect width="{width}" height="{height}" fill="#1a1a2e"/>')

        # ---- grid lines ----
        grid_count = 5
        for i in range(grid_count + 1):
            y = price_top + int(price_h * i / grid_count)
            lines.append(
                _svg_tag(
                    "line",
                    x1=str(pad_left), y1=str(y),
                    x2=str(width - pad_right), y2=str(y),
                    stroke="#2a2a4a", **{"stroke-width": "0.5"},
                )
            )

        # ---- title ----
        lines.append(
            _svg_tag(
                "text", x=str(width // 2), y="20", fill="#e0e0e0",
                **{"font-size": "13", "font-family": "sans-serif",
                   "text-anchor": "middle", "font-weight": "bold"},
                text=f"{code} {title}".strip(),
            )
        )

        # ---- ylabel ----
        lines.append(
            _svg_tag(
                "text", x="12", y=str(price_top + price_h // 2), fill="#888",
                **{"font-size": "10", "font-family": "sans-serif",
                   "text-anchor": "middle",
                   "transform": f"rotate(-90, 12, {price_top + price_h // 2})"},
                text=ylabel,
            )
        )

        # ---- price axis labels ----
        for i in range(grid_count, -1, -1):
            p = price_low + price_range * i / grid_count
            y = price_top + int(price_h * (grid_count - i) / grid_count)
            label = f"{p:.2f}"
            lines.append(
                _svg_tag(
                    "text", x=str(pad_left - 6), y=str(y + 4), fill="#888",
                    **{"font-size": "9", "font-family": "sans-serif",
                       "text-anchor": "end"},
                    text=label,
                )
            )

        # ---- volume axis labels ----
        for i in range(3):
            v = vol_max * i / 2
            y = vol_bottom - int(vol_h * i / 2)
            if v >= 1e6:
                label = f"{v/1e6:.1f}M"
            elif v >= 1e3:
                label = f"{v/1e3:.1f}K"
            else:
                label = f"{v:.0f}"
            lines.append(
                _svg_tag(
                    "text", x=str(pad_left - 6), y=str(y + 4), fill="#888",
                    **{"font-size": "9", "font-family": "sans-serif",
                       "text-anchor": "end"},
                    text=label,
                )
            )

        # ---- candlesticks ----
        for i in range(n):
            row = df.iloc[i]
            o, h, l, c = (
                float(row['Open']), float(row['High']),
                float(row['Low']), float(row['Close']),
            )
            x = xs[i]
            is_up = c >= o
            color = "#26a69a" if is_up else "#ef5350"
            body_top = _price_y(max(o, c))
            body_bot = _price_y(min(o, c))
            body_h = max(1, body_bot - body_top)

            # wick
            wick_top = _price_y(h)
            wick_bot = _price_y(l)
            lines.append(
                _svg_tag(
                    "line", x1=str(x), y1=str(wick_top),
                    x2=str(x), y2=str(wick_bot),
                    stroke=color, **{"stroke-width": "1"},
                )
            )

            # body
            if body_h <= 1:
                lines.append(
                    _svg_tag(
                        "line",
                        x1=str(x - candle_w // 2), y1=str(_price_y(c)),
                        x2=str(x + candle_w // 2), y2=str(_price_y(c)),
                        stroke=color, **{"stroke-width": "1"},
                    )
                )
            else:
                lines.append(
                    _svg_tag(
                        "rect",
                        x=str(x - candle_w // 2), y=str(body_top),
                        width=str(candle_w), height=str(body_h), fill=color,
                    )
                )

        # ---- MA20 overlay ----
        if 'MA20' in df.columns:
            ma_points = []
            for i in range(n):
                v = df.iloc[i].get('MA20')
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                ma_points.append(f"{xs[i]},{_price_y(float(v)):.1f}")
            if len(ma_points) >= 2:
                lines.append(
                    _svg_tag(
                        "polyline", points=" ".join(ma_points),
                        fill="none", stroke="#42a5f5",
                        **{"stroke-width": "1.2"},
                    )
                )

        # ---- volume bars ----
        for i in range(n):
            row = df.iloc[i]
            o, c = float(row['Open']), float(row['Close'])
            v = float(row['Volume'])
            x = xs[i]
            is_up = c >= o
            color = "#26a69a" if is_up else "#ef5350"
            bar_h = max(1, vol_bottom - _vol_y(v))
            y = vol_bottom - bar_h
            bar_w = max(1, candle_w)
            lines.append(
                _svg_tag(
                    "rect", x=str(x - bar_w // 2), y=str(y),
                    width=str(bar_w), height=str(bar_h),
                    fill=color, opacity="0.7",
                )
            )

        # ---- separator ----
        lines.append(
            _svg_tag(
                "line",
                x1=str(pad_left), y1=str(price_bottom),
                x2=str(width - pad_right), y2=str(price_bottom),
                stroke="#444", **{"stroke-width": "1"},
            )
        )

        # ---- x-axis date labels ----
        tick_count = min(6, n)
        step = max(1, n // tick_count)
        for i in range(0, n, step):
            idx = min(i, n - 1)
            try:
                ts = df.index[idx]
                if hasattr(ts, 'strftime'):
                    date_str = ts.strftime('%m-%d')
                else:
                    date_str = str(ts)[:5]
            except Exception:
                date_str = ""
            x = xs[idx]
            lines.append(
                _svg_tag(
                    "text", x=str(x), y=str(height - 8), fill="#888",
                    **{"font-size": "8", "font-family": "sans-serif",
                       "text-anchor": "middle"},
                    text=date_str,
                )
            )

        lines.append("</svg>")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Built-in: Plotly
# ---------------------------------------------------------------------------

class PlotlyRenderer:
    """Candlestick chart renderer using Plotly.

    Produces interactive HTML with hover/zoom/pan, and static PNG
    via kaleido.
    """

    name = "plotly"
    _supports_interactive = True

    @staticmethod
    def is_available() -> bool:
        try:
            import plotly.graph_objects as go  # noqa: F401
            return True
        except ImportError:
            return False

    def _build_figure(self, df: pd.DataFrame, code: str, title: str, ylabel: str):
        """Build and return a plotly figure (shared by render and render_interactive)."""
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
        )

        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'],
                name=code,
            ),
            row=1, col=1,
        )

        if 'MA20' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index, y=df['MA20'],
                    mode='lines', name='MA20',
                    line=dict(color='blue', width=1),
                ),
                row=1, col=1,
            )

        fig.add_trace(
            go.Bar(
                x=df.index, y=df['Volume'],
                name='Volume',
                marker=dict(color='rgba(128,128,128,0.5)'),
            ),
            row=2, col=1,
        )

        fig.update_layout(
            title=title,
            yaxis_title=ylabel,
            xaxis_rangeslider_visible=False,
            template='plotly_dark',
            height=520,
        )

        return fig

    def render(self, df: pd.DataFrame, code: str, title: str, ylabel: str) -> bytes:
        fig = self._build_figure(df, code, title, ylabel)

        try:
            return fig.to_image(format='png', scale=2)
        except ValueError:
            raise RuntimeError(
                "Plotly static image export requires kaleido. "
                "Install with: pip install kaleido"
            )

    def render_interactive(
        self, df: pd.DataFrame, code: str, title: str, ylabel: str
    ) -> str:
        fig = self._build_figure(df, code, title, ylabel)
        return fig.to_html(full_html=False, include_plotlyjs='cdn')


# ---------------------------------------------------------------------------
# Auto-register built-in renderers that are available
# ---------------------------------------------------------------------------

def _register_builtin_renderers() -> None:
    """Register all built-in renderers whose dependencies are satisfied."""
    builtins = [MatplotlibRenderer(), SvgRenderer(), PlotlyRenderer()]
    for r in builtins:
        if r.name not in _RENDERER_REGISTRY and r.is_available():
            _RENDERER_REGISTRY[r.name] = r
            logger.debug("Built-in chart renderer available: %s", r.name)

    if not _RENDERER_REGISTRY:
        logger.warning("No chart renderer backends are available.")


_register_builtin_renderers()
