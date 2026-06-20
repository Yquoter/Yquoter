# blank/verify_pipeline.py
"""End-to-end verification: CPU pipeline -> GPU pipeline, 10 + 20 windows."""

import sys
from pathlib import Path

# Add project root to sys.path so `import blank` works
_proj_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_proj_root))

import logging
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from blank.data_loader import discover_time_ids
from blank.pipeline_runner import run_cpu_pipeline
from blank.pipeline_manager import run_pipeline, benchmark_pipeline

PARQUET_PATH = str(
    Path(__file__).resolve().parent / "dataset" / "book_train.parquet"
)


def main():
    # Discover actual time_ids from data
    all_time_ids = discover_time_ids(PARQUET_PATH)
    test_ids_10 = all_time_ids[:10]
    test_ids_20 = all_time_ids[:20]

    # --- Phase 1: CPU pipeline on 10 windows ---
    print("=" * 60)
    print(f"Phase 1: CPU pipeline ({len(test_ids_10)} time windows)")
    print("=" * 60)
    slices = run_cpu_pipeline(parquet_path=PARQUET_PATH, time_ids_subset=test_ids_10)

    assert len(slices) > 0, "No slices produced!"
    N, F, T = slices[0].shape
    assert F == 4, f"Expected 4 features, got {F}"
    assert slices[0].dtype == np.float32
    assert slices[0].flags["C_CONTIGUOUS"]
    print(f"\nProduced {len(slices)} slices, shape=({N},{F},{T}), float32 C-contiguous\n")

    # --- Phase 2: GPU pipeline ---
    print("=" * 60)
    print("Phase 2: GPU pipeline (low-rank graph + random walk)")
    print("=" * 60)
    centralities, timing = run_pipeline(slices)
    assert len(centralities) == len(slices)
    for i, c in enumerate(centralities):
        assert c.shape == (N,), f"Slice {i}: expected ({N},), got {c.shape}"
    print(f"GPU returned {len(centralities)} centrality vectors, shape=({N},)")
    print(f"Timing: {timing}\n")

    # --- Phase 3: Benchmark ---
    print("=" * 60)
    print("Phase 3: Mini benchmark (20 windows)")
    print("=" * 60)
    result = benchmark_pipeline(
        parquet_path=PARQUET_PATH, subset_time_ids=test_ids_20
    )
    for k, v in result.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
