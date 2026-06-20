"""
Out-of-Core Dual-Stream Pipeline Manager
=========================================

【Boundary Declaration — Must Read】
This implementation borrows the engineering idea of "replacing direct
storage/computation of high-dimensional dense structures with low-rank
factorization A·B" from the ICLR 2025 paper *Expand and Compress:
Exploring Tuning Principles for Continual Spatio-Temporal Graph
Forecasting* (EAC).  However, the original EAC method compresses the
"node-level prompt parameter pool in continual learning scenarios" for
training efficiency; we compress the "market-wide instantaneous
correlation graph" for real-time graph sampling computational
efficiency.  These are different application targets.  Throughout this
file, any reference to EAC describes our work as "borrowing from /
adapting the EAC idea," never as "reproducing an EAC module."

Architecture
------------
This module implements an out-of-core (OOC) streaming pipeline that
processes time slices one at a time while overlapping PCIe data transfer
with GPU computation via dual CUDA streams:

    stream_transfer  —  async host→device copy (cp.asarray)
    stream_compute   —  low-rank graph construction + random walk

A double-buffering scheme keeps two device-side slot buffers so that
while slice `i` is being computed, slice `i+1` is already being
transferred in the background.  After each slice, the memory pool is
purged to limit VRAM fragmentation across many iterations.

Timing
------
Per-iteration GPU-side timestamps (via CUDA events) are accumulated to
report:
  - total_transfer_ms   : aggregate time spent in host→device copies
  - total_compute_ms    : aggregate time spent in graph + walk kernels
  - wall_ms             : end-to-end wall-clock duration
  - overlap_saved_ms    : approximate time hidden by concurrency
                          (~ min(total_transfer_ms, total_compute_ms))

Environment
-----------
- NVIDIA RTX 4050, 6 GB VRAM
- Python + CuPy only
"""

import time
from typing import Dict, List, Optional, Tuple

import numpy as np

# CuPy is imported lazily inside functions so that this module can be
# imported for type-checking even if the CUDA toolkit is absent.
# At runtime a GPU with CuPy is required.
try:
    import cupy as cp
except ImportError:
    cp = None  # type: ignore[assignment]

from blank.low_rank_graph import low_rank_correlation_graph
from blank.random_walk import time_ordered_random_walk


def _ensure_cupy():
    """Raise a clear error if CuPy is not available at runtime."""
    if cp is None:
        raise RuntimeError(
            "CuPy is required but not installed.  "
            "Install with: pip install cupy-cuda12x"
        )


def run_pipeline(
    slices: List[np.ndarray],
    k: int = 8,
    walk_length: int = 100,
    num_walks_per_node: int = 20,
    eps: float = 1e-12,
) -> Tuple[List[np.ndarray], Dict[str, float]]:
    """Process a stream of CPU-side time slices through the GPU pipeline.

    For each slice the pipeline:
      1. Uploads it to the GPU asynchronously (stream_transfer).
      2. Reconstructs the low-rank transition matrix P_trans via
         low_rank_correlation_graph (stream_compute).
      3. Runs a time-ordered random walk on [P_trans] to obtain a
         per-slice graph centrality vector (stream_compute).
      4. Copies the centrality result back to the CPU.
      5. Purges the GPU memory pool to avoid fragmentation.

    Transfer of slice `i+1` overlaps with computation on slice `i`,
    hiding PCIe latency behind compute work.

    Args:
        slices: CPU-side numpy arrays, each of shape (500, 4, 600),
            float32, C-contiguous.  Ordered by increasing market time.
        k: SVD truncation rank for low_rank_correlation_graph.
        walk_length: Number of random-walk steps per slice.
        num_walks_per_node: Walkers launched per stock node.
        eps: Numerical stability constant.

    Returns:
        centralities: List of graph_centrality vectors (one per slice),
            each a numpy array of shape (500,) on the CPU.
        timing_info: Dict with keys:
            'total_transfer_ms'   — aggregate GPU-side transfer time
            'total_compute_ms'    — aggregate GPU-side compute time
            'wall_ms'             — end-to-end wall-clock duration
            'overlap_saved_ms'    — approximate time saved by dual-stream
                                    overlap
            'num_slices'          — number of slices processed
    """
    _ensure_cupy()

    num_slices = len(slices)
    if num_slices == 0:
        return [], {
            'total_transfer_ms': 0.0,
            'total_compute_ms': 0.0,
            'wall_ms': 0.0,
            'overlap_saved_ms': 0.0,
            'num_slices': 0,
        }

    # --- Create non-blocking CUDA streams --------------------------------
    # non_blocking=True means operations on this stream do not implicitly
    # synchronise with the default (legacy) stream.  This is required for
    # true overlap between transfer and compute.
    stream_transfer = cp.cuda.Stream(non_blocking=True)
    stream_compute = cp.cuda.Stream(non_blocking=True)

    # --- Allocate double-buffer slots on the device ----------------------
    # Each slot holds one time slice of shape (500, 4, 600), float32.
    # 500 * 4 * 600 * 4 bytes ≈ 4.8 MB per slot — well within VRAM budget.
    buffer: List[Optional[cp.ndarray]] = [None, None]

    # --- Result accumulator (CPU-side) -----------------------------------
    centralities: List[np.ndarray] = []

    # --- Timing accumulators (GPU-side, via CUDA events) -----------------
    total_transfer_ms = 0.0
    total_compute_ms = 0.0

    # Wall-clock timer — recorded on stream_transfer because the first
    # GPU operation (pre-load) runs there.  Using the default stream
    # would not correctly order against non-blocking streams.
    wall_start = cp.cuda.Event()
    wall_end = cp.cuda.Event()

    # --- Pre-load slice 0 into buffer[0] ---------------------------------
    # This first transfer is unavoidable overhead; subsequent transfers
    # will overlap with compute.  We time it separately and add it to
    # total_transfer_ms so the accounting includes all N transfers.
    preload_start = cp.cuda.Event()
    preload_end = cp.cuda.Event()
    with stream_transfer:
        wall_start.record(stream_transfer)
        preload_start.record(stream_transfer)
        buffer[0] = cp.asarray(slices[0])
        preload_end.record(stream_transfer)
    stream_transfer.synchronize()
    preload_ms = cp.cuda.get_elapsed_time(preload_start, preload_end)
    total_transfer_ms += preload_ms

    # --- Main pipeline loop ----------------------------------------------
    for i in range(num_slices):
        tfer_start = cp.cuda.Event()
        tfer_end = cp.cuda.Event()
        comp_start = cp.cuda.Event()
        comp_end = cp.cuda.Event()

        # -- Phase 1: initiate async upload of the NEXT slice -------------
        # The upload runs on stream_transfer and overlaps with the compute
        # on stream_compute from the *current* iteration.
        if i + 1 < num_slices:
            slot_next = (i + 1) % 2
            with stream_transfer:
                tfer_start.record(stream_transfer)
                buffer[slot_next] = cp.asarray(slices[i + 1])
                tfer_end.record(stream_transfer)

        # -- Phase 2: compute on the CURRENT slice ------------------------
        slot_cur = i % 2
        current_gpu_slice = buffer[slot_cur]
        assert current_gpu_slice is not None, (
            f"Buffer slot {slot_cur} is empty at iteration {i}"
        )

        with stream_compute:
            comp_start.record(stream_compute)

            # 2a. Low-rank correlation graph reconstruction.
            P_trans, _P_raw, _A, _B = low_rank_correlation_graph(
                current_gpu_slice, k=k, eps=eps,
            )

            # 2b. Time-ordered random walk.
            # Each slice's centrality is computed independently using
            # its own P_trans as a single-element list.  The time-
            # ordering constraint min(s, 0) = 0 means every step uses
            # the same transition matrix — appropriate for a per-slice
            # snapshot of market structure.
            centrality_gpu = time_ordered_random_walk(
                [P_trans],
                walk_length=walk_length,
                num_walks_per_node=num_walks_per_node,
                eps=eps,
            )

            comp_end.record(stream_compute)

        # -- Phase 3: synchronise both streams ----------------------------
        # We must wait for BOTH streams before we can safely:
        #   (a) read centrality_gpu back to CPU
        #   (b) overwrite buffer slots in the next iteration
        stream_transfer.synchronize()
        stream_compute.synchronize()

        # -- Phase 4: copy result to CPU ----------------------------------
        centralities.append(cp.asnumpy(centrality_gpu))

        # -- Phase 5: accumulate GPU-side timing --------------------------
        if i + 1 < num_slices:
            # Only measure transfer time when a transfer actually happened.
            tfer_ms = cp.cuda.get_elapsed_time(tfer_start, tfer_end)
            total_transfer_ms += tfer_ms
        comp_ms = cp.cuda.get_elapsed_time(comp_start, comp_end)
        total_compute_ms += comp_ms

        # -- Phase 6: release intermediate tensors -------------------------
        # P_raw (500×500), P_trans (500×500), A (500×k), B (k×600),
        # X_k (500×600), SVD temporaries, and random-walk scratch space
        # are all GPU allocations.  Explicitly drop Python references so
        # the CuPy memory pool can reclaim the underlying device memory.
        del P_trans, _P_raw, _A, _B, centrality_gpu

        # Return all freed blocks to the CUDA driver so that subsequent
        # iterations do not suffer from fragmentation or unnecessary
        # out-of-memory pressure on a 6 GB device.
        cp.get_default_memory_pool().free_all_blocks()

    # --- Mark wall-clock end ---------------------------------------------
    wall_end.record()
    wall_end.synchronize()
    wall_ms = cp.cuda.get_elapsed_time(wall_start, wall_end)

    # --- Compute overlap savings -----------------------------------------
    # In the ideal case, transfer of slice i+1 is entirely hidden behind
    # compute of slice i.  The theoretical maximum saving is therefore
    # bounded by min(total_transfer, total_compute).  Real hardware may
    # achieve less due to driver serialisation, PCIe contention, or kernel
    # launch overhead, so this is reported as an approximate upper bound.
    overlap_saved_ms = min(total_transfer_ms, total_compute_ms)

    timing_info: Dict[str, float] = {
        'total_transfer_ms': total_transfer_ms,
        'total_compute_ms': total_compute_ms,
        'wall_ms': wall_ms,
        'overlap_saved_ms': overlap_saved_ms,
        'num_slices': float(num_slices),
    }

    return centralities, timing_info


def benchmark_pipeline(
    parquet_path: str,
    subset_time_ids: List[int],
    k: int = 8,
    walk_length: int = 100,
    num_walks_per_node: int = 20,
) -> Dict[str, float]:
    """End-to-end benchmark: CPU → GPU pipeline, return timing breakdown.

    Runs the full CPU pipeline (data loading → feature engineering →
    tensor building) followed by the GPU pipeline (low-rank graph →
    random walk → centrality), then reports timing for each phase.

    Args:
        parquet_path: Path to ``book_train.parquet``.
        subset_time_ids: List of time_ids to process.
        k: SVD truncation rank.
        walk_length: Random walk steps per walk.
        num_walks_per_node: Walks per graph node.

    Returns:
        Dict with keys: n_slices, n_stocks, cpu_time_s, gpu_time_s,
        total_time_s, cpu_throughput_wps, and GPU timing breakdown.
    """
    from blank.pipeline_runner import run_cpu_pipeline

    t_total = time.perf_counter()

    # --- CPU phase ---
    t_cpu = time.perf_counter()
    slices = run_cpu_pipeline(
        parquet_path=parquet_path,
        time_ids_subset=subset_time_ids,
    )
    cpu_time = time.perf_counter() - t_cpu

    # --- GPU phase ---
    t_gpu = time.perf_counter()
    centralities, gpu_timing = run_pipeline(
        slices, k=k, walk_length=walk_length, num_walks_per_node=num_walks_per_node
    )
    gpu_time = time.perf_counter() - t_gpu

    total_time = time.perf_counter() - t_total

    return {
        "n_slices": len(slices),
        "n_stocks": slices[0].shape[0] if slices else 0,
        "cpu_time_s": cpu_time,
        "gpu_time_s": gpu_time,
        "total_time_s": total_time,
        "cpu_throughput_wps": len(slices) / cpu_time if cpu_time > 0 else float("inf"),
        **gpu_timing,
    }


# ===========================================================================
# Self-check block — processes a small batch of synthetic slices and
# prints the timing breakdown.
# ===========================================================================
if __name__ == "__main__":
    _ensure_cupy()

    print("=" * 64)
    print("pipeline_manager.py — self-check")
    print("=" * 64)

    # Generate a small number of synthetic CPU-side slices.
    # Using a fixed seed so results are reproducible.
    np.random.seed(99)
    num_test_slices = 5
    test_slices = [
        np.random.randn(500, 4, 600).astype(np.float32)
        for _ in range(num_test_slices)
    ]

    print(f"\nTest slices : {num_test_slices}")
    print(f"Shape each : {test_slices[0].shape}")
    print(f"dtype       : {test_slices[0].dtype}")
    print(f"Total CPU   : {num_test_slices * 500 * 4 * 600 * 4 / 1024**2:.1f} MB")

    # Run the pipeline.
    centralities, timing = run_pipeline(
        test_slices,
        k=8,
        walk_length=50,        # Shorter for quick validation.
        num_walks_per_node=5,  # Fewer walkers for quick validation.
    )

    # --- Print timing breakdown ---
    print(f"\n{'─' * 40}")
    print("Timing breakdown")
    print(f"{'─' * 40}")
    for key in ['total_transfer_ms', 'total_compute_ms', 'wall_ms',
                'overlap_saved_ms', 'num_slices']:
        print(f"  {key:<24s} : {timing[key]:.2f}")

    # Approximate speedup vs a hypothetical serial pipeline.
    serial_estimate = timing['total_transfer_ms'] + timing['total_compute_ms']
    if timing['wall_ms'] > 0:
        effective_speedup = serial_estimate / timing['wall_ms']
        print(f"  {'effective_speedup':<24s} : {effective_speedup:.2f}x")
    print(f"{'─' * 40}")

    # --- Validate outputs ---
    print(f"\nOutput count : {len(centralities)}  (expected {num_test_slices})")
    assert len(centralities) == num_test_slices, "Output count mismatch"

    for i, c in enumerate(centralities):
        assert isinstance(c, np.ndarray), (
            f"centralities[{i}] is {type(c)}, expected np.ndarray"
        )
        assert c.shape == (500,), (
            f"centralities[{i}] shape {c.shape} != (500,)"
        )
        assert abs(float(c.sum()) - 1.0) < 1e-4, (
            f"centralities[{i}] does not sum to 1: sum={c.sum():.6f}"
        )
        assert float(c.min()) >= 0.0, (
            f"centralities[{i}] has negative values"
        )

    # Show a snippet of the last centrality vector.
    print(f"\nLast centrality vector (first 10 entries):")
    print(centralities[-1][:10])

    print("\n" + "=" * 64)
    print("All self-checks passed.")
    print("=" * 64)
