"""
Full-dataset benchmark — processes ALL 3,830 time windows.

Expected runtime on RTX 4050 + Intel i7-13700H:
  - CPU feature engineering : ~40–60 minutes
  - GPU pipeline            : ~5–10 minutes
  - Total end-to-end        : ~45–70 minutes

This script replaces the "projected estimate" in §3.2.4 with real data.

Usage (run from project root):
    python blank/run_full_benchmark.py

The results are saved to ``blank/full_benchmark_results.json`` for use
by plot.py and the experiment report.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so ``import blank`` works.
_proj_root = Path(__file__).resolve().parent.parent
if str(_proj_root) not in sys.path:
    sys.path.insert(0, str(_proj_root))

import json
import logging
import time
from typing import List

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("full_benchmark")

OUT_DIR = Path(__file__).resolve().parent
PARQUET_PATH = str(OUT_DIR / "dataset" / "book_train.parquet")
N_SLICES = 10  # default; pass --all for full dataset


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Full-dataset benchmark")
    parser.add_argument("--all", action="store_true",
                        help="Process all 3830 windows (takes ~1 hour)")
    parser.add_argument("--workers", type=int, default=6,
                        help="CPU parallel workers (default 6)")
    parser.add_argument("--k", type=int, default=8,
                        help="SVD rank (default 8)")
    parser.add_argument("--walk-length", type=int, default=100)
    parser.add_argument("--walks-per-node", type=int, default=20)
    args = parser.parse_args()

    from blank.data_loader import discover_time_ids, discover_stock_ids

    # --- pre-scan ---
    all_time_ids = discover_time_ids(PARQUET_PATH)
    stock_ids = discover_stock_ids(PARQUET_PATH)
    n_stocks = len(stock_ids)
    n_total = len(all_time_ids)

    if args.all:
        time_ids = all_time_ids
    else:
        n = min(N_SLICES, n_total)
        time_ids = all_time_ids[:n]

    n_windows = len(time_ids)
    logger.info("Benchmark: %d / %d windows, %d stocks", n_windows, n_total, n_stocks)

    # --- Phase 1: CPU pipeline ---
    logger.info("Phase 1: CPU feature engineering...")
    t_wall_start = time.perf_counter()

    t_cpu_start = time.perf_counter()

    # Try parallel first; fall back to serial
    try:
        from blank.cpu_parallel import run_parallel_cpu_pipeline
        logger.info("Using multiprocessing with %d workers", args.workers)
        slices = run_parallel_cpu_pipeline(
            parquet_path=PARQUET_PATH,
            subset_time_ids=time_ids,
            n_workers=args.workers,
        )
    except Exception:
        logger.warning("Parallel failed, falling back to serial", exc_info=True)
        from blank.pipeline_runner import run_cpu_pipeline
        slices = run_cpu_pipeline(
            parquet_path=PARQUET_PATH,
            time_ids_subset=time_ids,
        )

    cpu_time = time.perf_counter() - t_cpu_start
    logger.info("CPU phase done: %.1f s (%.1f windows/s)",
                cpu_time, n_windows / cpu_time if cpu_time > 0 else float("inf"))

    # --- Phase 2: GPU pipeline ---
    logger.info("Phase 2: GPU low-rank graph + random walk...")
    t_gpu_start = time.perf_counter()

    from blank.pipeline_manager import run_pipeline

    centralities, gpu_timing = run_pipeline(
        slices,
        k=args.k,
        walk_length=args.walk_length,
        num_walks_per_node=args.walks_per_node,
    )

    gpu_time = time.perf_counter() - t_gpu_start
    wall_time = time.perf_counter() - t_wall_start

    logger.info("GPU phase done: %.1f s", gpu_time)

    # --- Phase 3: summary ---
    logger.info("=" * 60)
    logger.info("BENCHMARK COMPLETE")
    logger.info("=" * 60)
    logger.info("Windows processed : %d", n_windows)
    logger.info("Stocks            : %d", n_stocks)
    logger.info("CPU time          : %.1f s", cpu_time)
    logger.info("GPU time          : %.1f s", gpu_time)
    logger.info("Wall time         : %.1f s", wall_time)
    logger.info("Per-slice CPU     : %.1f ms", cpu_time / n_windows * 1000)
    logger.info("Per-slice GPU     : %.1f ms", gpu_time / n_windows * 1000)
    logger.info("CPU throughput    : %.1f windows/s",
                n_windows / cpu_time if cpu_time > 0 else float("inf"))

    # --- Save results ---
    results = {
        "n_windows": n_windows,
        "n_stocks": n_stocks,
        "n_total_available": n_total,
        "cpu_time_s": cpu_time,
        "gpu_time_s": gpu_time,
        "wall_time_s": wall_time,
        "per_slice_cpu_ms": cpu_time / n_windows * 1000,
        "per_slice_gpu_ms": gpu_time / n_windows * 1000,
        "cpu_throughput_wps": n_windows / cpu_time if cpu_time > 0 else float("inf"),
        "gpu_timing": gpu_timing,
        "centrality_sample": centralities[0][:10].tolist() if centralities else [],
    }

    out_path = OUT_DIR / "full_benchmark_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=float)
    logger.info("Results saved to %s", out_path)


if __name__ == "__main__":
    main()
