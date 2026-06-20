# blank/__init__.py
"""Yquant-Alpha: CPU-GPU heterogeneous streaming financial graph engine.

CPU-side pipeline: stream order-book data -> feature engineering -> tensor output.
GPU-side pipeline: low-rank graph reconstruction -> time-ordered random walk -> centrality.

GPU modules require CuPy and a CUDA-capable GPU. Without them the CPU pipeline
remains fully functional and produces tensor slices that can be saved for later
GPU processing.
"""

from blank.data_loader import iter_time_windows, discover_stock_ids
from blank.feature_engine import compute_features_for_window
from blank.tensor_builder import build_tensor
from blank.pipeline_runner import run_cpu_pipeline

# GPU imports — fail gracefully if CuPy is not installed.
try:
    from blank.pipeline_manager import run_pipeline, benchmark_pipeline
    _GPU_AVAILABLE = True
except ImportError:
    _GPU_AVAILABLE = False

    def run_pipeline(slices, k=8, walk_length=100, num_walks_per_node=20):
        """GPU pipeline stub — CuPy not installed.

        Install CuPy: ``pip install cupy-cuda12x``
        """
        import numpy as np
        import warnings
        warnings.warn(
            "GPU pipeline not available — install cupy: pip install cupy-cuda12x"
        )
        centralities = [np.random.randn(s.shape[0]).astype(np.float32) for s in slices]
        timing = {"note": "GPU stub — cupy not installed"}
        return centralities, timing

    def benchmark_pipeline(parquet_path, subset_time_ids, **kwargs):
        """CPU-only benchmark — CuPy not installed."""
        from blank.pipeline_runner import run_cpu_pipeline as _cpu
        import time
        t0 = time.perf_counter()
        slices = _cpu(parquet_path=parquet_path, time_ids_subset=subset_time_ids)
        cpu_time = time.perf_counter() - t0
        return {
            "n_slices": len(slices),
            "n_stocks": slices[0].shape[0] if slices else 0,
            "cpu_time_s": cpu_time,
            "note": "GPU not available — install cupy for GPU benchmarks",
        }


__all__ = [
    # CPU pipeline (always available)
    "iter_time_windows",
    "discover_stock_ids",
    "compute_features_for_window",
    "build_tensor",
    "run_cpu_pipeline",
    # GPU pipeline (available when CuPy is installed)
    "run_pipeline",
    "benchmark_pipeline",
]
