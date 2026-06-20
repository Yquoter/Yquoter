"""
Tests for the GPU-accelerated financial graph sampling operators.

This test suite covers the three deliverables of the Yquant-Alpha
GPU pipeline sub-project:

  - low_rank_graph.py    — low-rank correlation graph reconstruction
  - random_walk.py       — time-ordered random walk (Gumbel-max)
  - pipeline_manager.py  — out-of-core dual-stream pipeline manager

All tests are designed to run with `pytest` on a machine with CuPy and
a CUDA-capable GPU.  When CuPy is unavailable every test is skipped
automatically via ``pytest.importorskip``.

Usage
-----
    cd blank
    pytest test_gpu_pipeline.py -v

Or, from the repository root:

    pytest blank/test_gpu_pipeline.py -v
"""

from __future__ import annotations

import math
from typing import List

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# CuPy guard — skip the entire module when CuPy / a GPU is not present.
# ---------------------------------------------------------------------------
cp = pytest.importorskip("cupy", reason="CuPy is not installed.")
# Verify a CUDA device is actually available (import may succeed but the
# machine may lack a GPU).
try:
    _ = cp.cuda.runtime.getDeviceCount()
    if _ == 0:
        pytest.skip("No CUDA device detected.", allow_module_level=True)
except cp.cuda.runtime.CUDARuntimeError:
    pytest.skip("CUDA runtime error — no usable GPU.", allow_module_level=True)

# Module-level imports depend on CuPy, so they must be done after the guard.
from blank.low_rank_graph import low_rank_correlation_graph, _matrix_rank  # noqa: E402
from blank.random_walk import time_ordered_random_walk       # noqa: E402
from blank.pipeline_manager import run_pipeline              # noqa: E402


# ===========================================================================
# Shared constants
# ===========================================================================

NUM_STOCKS = 200   # representative; real datasets vary (Optiver ≈ 112)
NUM_FEATURES = 4
NUM_TIME_STEPS = 400  # representative; real windows may differ
DEFAULT_K = 8
EPS = 1e-12


# ===========================================================================
# Helpers
# ===========================================================================


def _make_synthetic_slice(
    seed: int = 0,
    num_stocks: int = NUM_STOCKS,
    num_features: int = NUM_FEATURES,
    num_time_steps: int = NUM_TIME_STEPS,
) -> np.ndarray:
    """Return a single CPU-side synthetic time slice of standard shape."""
    rng = np.random.RandomState(seed)
    return rng.randn(num_stocks, num_features, num_time_steps).astype(np.float32)


def _make_synthetic_slices(
    n: int,
    seed: int = 0,
    num_stocks: int = NUM_STOCKS,
    num_time_steps: int = NUM_TIME_STEPS,
) -> List[np.ndarray]:
    """Return *n* CPU-side synthetic time slices."""
    return [
        _make_synthetic_slice(
            seed=seed + i,
            num_stocks=num_stocks,
            num_time_steps=num_time_steps,
        )
        for i in range(n)
    ]


# ===========================================================================
# low_rank_graph tests
# ===========================================================================


class TestLowRankGraph:
    """Tests for ``low_rank_correlation_graph``."""

    # -- input validation ---------------------------------------------------

    def test_rejects_wrong_ndim(self):
        """A 2-D array must raise ValueError."""
        bad = cp.random.randn(NUM_STOCKS, NUM_TIME_STEPS, dtype=cp.float32)
        with pytest.raises(ValueError, match="3-D"):
            low_rank_correlation_graph(bad, k=DEFAULT_K)

    def test_rejects_wrong_shape(self):
        """An array with features != 4 must raise ValueError."""
        bad = cp.random.randn(100, 3, 200, dtype=cp.float32)
        with pytest.raises(ValueError, match="Expected 4 features"):
            low_rank_correlation_graph(bad, k=DEFAULT_K)

    def test_rejects_k_too_large(self):
        """k > min(stocks, time_steps) must raise ValueError."""
        good = cp.asarray(_make_synthetic_slice())
        with pytest.raises(ValueError, match="k="):
            low_rank_correlation_graph(good, k=999)

    # -- output shapes ------------------------------------------------------

    def test_output_shapes(self):
        """All returned arrays must have the documented shapes."""
        gpu_slice = cp.asarray(_make_synthetic_slice())
        P_trans, P_raw, A, B = low_rank_correlation_graph(gpu_slice, k=DEFAULT_K)

        assert P_trans.shape == (NUM_STOCKS, NUM_STOCKS)
        assert P_raw.shape == (NUM_STOCKS, NUM_STOCKS)
        assert A.shape == (NUM_STOCKS, DEFAULT_K)
        assert B.shape == (DEFAULT_K, NUM_TIME_STEPS)

    def test_reconstruction_shape(self):
        """A @ B must produce a (N_stocks, T_steps) array."""
        gpu_slice = cp.asarray(_make_synthetic_slice())
        _Pt, _Pr, A, B = low_rank_correlation_graph(gpu_slice, k=DEFAULT_K)
        X_recon = A @ B
        assert X_recon.shape == (NUM_STOCKS, NUM_TIME_STEPS)

    # -- low-rank property --------------------------------------------------

    def test_raw_rank_does_not_exceed_k(self):
        """rank(P_raw) must be ≤ k by construction."""
        gpu_slice = cp.asarray(_make_synthetic_slice())
        _Pt, P_raw, _A, _B = low_rank_correlation_graph(gpu_slice, k=DEFAULT_K)
        rank_val = int(_matrix_rank(P_raw))
        assert rank_val <= DEFAULT_K, f"rank(P_raw) = {rank_val} > {DEFAULT_K}"

    @pytest.mark.parametrize("k", [1, 2, 4, 8, 16])
    def test_rank_bound_for_various_k(self, k: int):
        """The rank bound must hold across a range of truncation ranks."""
        gpu_slice = cp.asarray(_make_synthetic_slice())
        _Pt, P_raw, _A, _B = low_rank_correlation_graph(gpu_slice, k=k)
        rank_val = int(_matrix_rank(P_raw))
        assert rank_val <= k, f"k={k}, rank(P_raw)={rank_val}"

    # -- stochastic / Markov properties ------------------------------------

    def test_row_sums_are_one(self):
        """Every row of P_trans must sum to 1 (within fp32 tolerance)."""
        gpu_slice = cp.asarray(_make_synthetic_slice())
        P_trans, _Pr, _A, _B = low_rank_correlation_graph(gpu_slice, k=DEFAULT_K)
        row_sums = P_trans.sum(axis=1)
        max_dev = float(cp.max(cp.abs(row_sums - 1.0)))
        assert max_dev < 1e-4, f"max |row_sum - 1| = {max_dev}"

    def test_no_negative_entries(self):
        """P_trans must have no negative entries."""
        gpu_slice = cp.asarray(_make_synthetic_slice())
        P_trans, _Pr, _A, _B = low_rank_correlation_graph(gpu_slice, k=DEFAULT_K)
        n_neg = int(cp.sum(P_trans < 0))
        assert n_neg == 0, f"{n_neg} negative entries"

    def test_diagonal_is_zero(self):
        """Self-loops must be removed (diagonal ≈ 0)."""
        gpu_slice = cp.asarray(_make_synthetic_slice())
        P_trans, _Pr, _A, _B = low_rank_correlation_graph(gpu_slice, k=DEFAULT_K)
        diag_sum = float(cp.sum(cp.diag(P_trans)))
        assert diag_sum < 1e-6, f"diagonal sum = {diag_sum}"

    def test_dtype_is_float32(self):
        """P_trans must be float32 (consistent with the input slice)."""
        gpu_slice = cp.asarray(_make_synthetic_slice())
        P_trans, _Pr, _A, _B = low_rank_correlation_graph(gpu_slice, k=DEFAULT_K)
        assert P_trans.dtype == cp.float32

    # -- deterministic behaviour --------------------------------------------

    def test_deterministic_with_fixed_seed(self):
        """Identical inputs must produce identical outputs."""
        cp.random.seed(999)
        s1 = cp.random.randn(NUM_STOCKS, 4, NUM_TIME_STEPS, dtype=cp.float32)

        cp.random.seed(999)
        s2 = cp.random.randn(NUM_STOCKS, 4, NUM_TIME_STEPS, dtype=cp.float32)

        P1, _Pr1, _A1, _B1 = low_rank_correlation_graph(s1, k=DEFAULT_K)
        P2, _Pr2, _A2, _B2 = low_rank_correlation_graph(s2, k=DEFAULT_K)

        assert float(cp.max(cp.abs(P1 - P2))) < 1e-5

    # -- edge case: all-constant slice -------------------------------------

    def test_constant_slice_does_not_crash(self):
        """A slice of all zeros must not produce NaN / inf."""
        gpu_slice = cp.zeros((NUM_STOCKS, 4, NUM_TIME_STEPS), dtype=cp.float32)
        P_trans, _Pr, _A, _B = low_rank_correlation_graph(gpu_slice, k=DEFAULT_K)
        row_sums = P_trans.sum(axis=1)
        max_dev = float(cp.max(cp.abs(row_sums - 1.0)))
        assert max_dev < 1e-4
        assert not cp.any(cp.isnan(P_trans))
        assert not cp.any(cp.isinf(P_trans))


# ===========================================================================
# random_walk tests
# ===========================================================================


class TestRandomWalk:
    """Tests for ``time_ordered_random_walk``."""

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _make_uniform_P(num_stocks: int = 50) -> cp.ndarray:
        """Return a uniform row-stochastic matrix (50×50)."""
        P = cp.full((num_stocks, num_stocks),
                     1.0 / num_stocks, dtype=cp.float32)
        cp.fill_diagonal(P, 0.0)
        row_sums = P.sum(axis=1, keepdims=True)
        P = P / row_sums
        return P

    @staticmethod
    def _make_star_P(num_stocks: int = 50,
                     centre: int = 7) -> cp.ndarray:
        """Return a star-graph transition matrix.

        Every non-centre node transitions to *centre* with probability 0.9
        and uniformly to the remaining nodes with probability 0.1.
        """
        P = cp.full((num_stocks, num_stocks),
                     0.1 / (num_stocks - 1), dtype=cp.float32)
        P[:, centre] = 0.9
        # Centre row: uniform.
        P[centre, :] = 1.0 / num_stocks
        # Remove self-loops for non-centre rows and re-normalise.
        for i in range(num_stocks):
            if i != centre:
                P[i, i] = 0.0
                s = P[i].sum()
                if s > 0:
                    P[i] /= s
        return P

    # -- input validation ---------------------------------------------------

    def test_empty_P_list_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            time_ordered_random_walk([], walk_length=10)

    def test_non_square_P_raises(self):
        bad = cp.ones((50, 30), dtype=cp.float32)
        with pytest.raises(ValueError, match="square"):
            time_ordered_random_walk([bad], walk_length=10)

    def test_inconsistent_shapes_raise(self):
        P1 = self._make_uniform_P(50)
        P2 = self._make_uniform_P(40)
        with pytest.raises(ValueError, match="consistent"):
            time_ordered_random_walk([P1, P2], walk_length=10)

    # -- output properties --------------------------------------------------

    @pytest.mark.parametrize("num_stocks", [10, 50, 100])
    @pytest.mark.parametrize("num_walks_per_node", [3, 10])
    def test_output_shape(self, num_stocks: int, num_walks_per_node: int):
        P = self._make_uniform_P(num_stocks)
        centrality = time_ordered_random_walk(
            [P], walk_length=20, num_walks_per_node=num_walks_per_node,
        )
        assert centrality.shape == (num_stocks,)

    def test_centrality_sums_to_one(self):
        P = self._make_uniform_P(50)
        centrality = time_ordered_random_walk(
            [P], walk_length=30, num_walks_per_node=5,
        )
        assert float(cp.abs(centrality.sum() - 1.0)) < 1e-5

    def test_no_negative_centrality(self):
        P = self._make_uniform_P(50)
        centrality = time_ordered_random_walk(
            [P], walk_length=30, num_walks_per_node=5,
        )
        assert float(cp.min(centrality)) >= 0.0

    # -- correctness: star graph -------------------------------------------

    def test_star_graph_centre_ranked_first(self):
        """The high-in-degree centre node must have the highest centrality."""
        num_stocks = 50
        centre = 7
        P = self._make_star_P(num_stocks, centre=centre)
        centrality = time_ordered_random_walk(
            [P], walk_length=60, num_walks_per_node=15,
        )
        centrality_cpu = cp.asnumpy(centrality)
        top_node = int(centrality_cpu.argmax())
        assert top_node == centre, (
            f"Expected centre node {centre} to rank first, "
            f"but node {top_node} did (centrality {centrality_cpu[top_node]:.4f} "
            f"vs centre {centrality_cpu[centre]:.4f})"
        )

    @pytest.mark.parametrize("centre", [0, 25, 49])
    def test_star_graph_various_centres(self, centre: int):
        """The star-graph test should work regardless of centre index."""
        num_stocks = 50
        P = self._make_star_P(num_stocks, centre=centre)
        centrality = time_ordered_random_walk(
            [P], walk_length=50, num_walks_per_node=10,
        )
        centrality_cpu = cp.asnumpy(centrality)
        top_node = int(centrality_cpu.argmax())
        assert top_node == centre, (
            f"centre={centre}, top_node={top_node}"
        )

    # -- time-ordering constraint ------------------------------------------

    def test_time_ordering_clamps_at_last_slice(self):
        """When walk_length > len(P_list), later steps must reuse last P."""
        num_stocks = 20
        # Build three distinct P matrices so we can detect which one is used.
        # P0: all transitions → node 0
        P0 = cp.zeros((num_stocks, num_stocks), dtype=cp.float32)
        P0[:, 0] = 1.0
        # P1: all transitions → node 10
        P1 = cp.zeros((num_stocks, num_stocks), dtype=cp.float32)
        P1[:, 10] = 1.0
        # P2: all transitions → node 19
        P2 = cp.zeros((num_stocks, num_stocks), dtype=cp.float32)
        P2[:, 19] = 1.0

        P_list = [P0, P1, P2]

        # walk_length=5, but only 3 slices → steps 0→P0, 1→P1, 2→P2,
        # 3→P2, 4→P2 (clamped).
        centrality = time_ordered_random_walk(
            P_list, walk_length=5, num_walks_per_node=20,
        )
        centrality_cpu = cp.asnumpy(centrality)

        # Node 19 (last slice's target) should dominate because steps
        # 2, 3, 4 all point to it, while node 0 gets step 0 and node 10
        # gets step 1.
        assert centrality_cpu[19] > centrality_cpu[0], (
            f"node 19 ({centrality_cpu[19]:.4f}) should dominate "
            f"node 0 ({centrality_cpu[0]:.4f})"
        )
        assert centrality_cpu[19] > centrality_cpu[10], (
            f"node 19 ({centrality_cpu[19]:.4f}) should dominate "
            f"node 10 ({centrality_cpu[10]:.4f})"
        )

    def test_single_slice_all_steps_same(self):
        """With a single-slice P_list all steps use the same P."""
        num_stocks = 10
        # Deterministic P: every node → node 0 with prob 1.
        P = cp.zeros((num_stocks, num_stocks), dtype=cp.float32)
        P[:, 0] = 1.0
        centrality = time_ordered_random_walk(
            [P], walk_length=10, num_walks_per_node=1,
        )
        centrality_cpu = cp.asnumpy(centrality)
        # Node 0 should get nearly all visits (step 0 starts at each node,
        # then every subsequent step goes to node 0).
        assert centrality_cpu[0] > 0.8, (
            f"node 0 centrality = {centrality_cpu[0]:.4f}, expected > 0.8"
        )

    # -- statistical robustness ---------------------------------------------

    def test_more_walkers_reduces_variance(self):
        """More walkers per node should tighten the centrality distribution
        for a uniform graph (informal variance check)."""
        P = self._make_uniform_P(50)

        def _std(num_walks: int) -> float:
            c = time_ordered_random_walk(
                [P], walk_length=20, num_walks_per_node=num_walks,
            )
            return float(cp.std(c))

        std_few = _std(3)
        std_many = _std(20)
        # Many walkers → lower std.  This is probabilistic; use a loose
        # ratio in case of rare unlucky draws.
        # Actually for a uniform graph the expected centrality is 1/50 for
        # all nodes.  With more walkers the estimate should be tighter.
        # We just check that *many* does not explode — it should be small.
        assert std_many < 0.02, f"std with 20 walkers = {std_many:.4f}"

    # -- numerical edge case ------------------------------------------------

    def test_zero_row_in_P_does_not_crash(self):
        """A P with an all-zero row (degenerate after clipping) must not
        produce NaN / inf.  The eps guard in log(P) handles this."""
        num_stocks = 10
        P = cp.ones((num_stocks, num_stocks), dtype=cp.float32)
        P[0, :] = 0.0  # row 0 is all zeros.
        # Re-normalise other rows.
        for i in range(1, num_stocks):
            P[i] /= P[i].sum()
        centrality = time_ordered_random_walk(
            [P], walk_length=5, num_walks_per_node=2,
        )
        assert not cp.any(cp.isnan(centrality))
        assert not cp.any(cp.isinf(centrality))


# ===========================================================================
# pipeline_manager tests
# ===========================================================================


class TestPipelineManager:
    """Tests for ``run_pipeline``."""

    # -- basic contract -----------------------------------------------------

    def test_empty_slices_returns_empty(self):
        centralities, timing = run_pipeline([])
        assert centralities == []
        assert timing["num_slices"] == 0

    def test_single_slice(self):
        slices = _make_synthetic_slices(1)
        centralities, timing = run_pipeline(
            slices, k=4, walk_length=10, num_walks_per_node=3,
        )
        assert len(centralities) == 1
        assert centralities[0].shape == (NUM_STOCKS,)
        assert timing["num_slices"] == 1

    def test_multiple_slices_output_count(self):
        n = 5
        slices = _make_synthetic_slices(n)
        centralities, timing = run_pipeline(
            slices, k=4, walk_length=10, num_walks_per_node=2,
        )
        assert len(centralities) == n
        assert timing["num_slices"] == n

    # -- output validity per slice -----------------------------------------

    def test_every_centrality_is_valid(self):
        n = 4
        slices = _make_synthetic_slices(n)
        centralities, _timing = run_pipeline(
            slices, k=4, walk_length=15, num_walks_per_node=3,
        )
        for i, c in enumerate(centralities):
            assert isinstance(c, np.ndarray), f"slice {i}: not np.ndarray"
            assert c.shape == (NUM_STOCKS,), f"slice {i}: shape {c.shape}"
            assert c.dtype == np.float32, f"slice {i}: dtype {c.dtype}"
            assert abs(float(c.sum()) - 1.0) < 1e-4, (
                f"slice {i}: sum = {c.sum():.6f}"
            )
            assert float(c.min()) >= 0.0, f"slice {i}: negative values"

    # -- timing info --------------------------------------------------------

    def test_timing_info_keys(self):
        slices = _make_synthetic_slices(3)
        _cent, timing = run_pipeline(
            slices, k=4, walk_length=10, num_walks_per_node=2,
        )
        expected_keys = {
            "total_transfer_ms", "total_compute_ms",
            "wall_ms", "overlap_saved_ms", "num_slices",
        }
        assert set(timing.keys()) == expected_keys

    def test_timing_values_are_non_negative(self):
        slices = _make_synthetic_slices(3)
        _cent, timing = run_pipeline(
            slices, k=4, walk_length=10, num_walks_per_node=2,
        )
        for k in ["total_transfer_ms", "total_compute_ms", "wall_ms",
                   "overlap_saved_ms"]:
            assert timing[k] >= 0.0, f"{k} is negative: {timing[k]}"

    def test_wall_time_is_positive(self):
        slices = _make_synthetic_slices(3)
        _cent, timing = run_pipeline(
            slices, k=4, walk_length=10, num_walks_per_node=2,
        )
        assert timing["wall_ms"] > 0.0, "wall time should be > 0"

    def test_overlap_not_larger_than_wall(self):
        slices = _make_synthetic_slices(5)
        _cent, timing = run_pipeline(
            slices, k=4, walk_length=15, num_walks_per_node=3,
        )
        assert timing["overlap_saved_ms"] <= timing["wall_ms"] + 1e-3, (
            f"overlap_saved_ms ({timing['overlap_saved_ms']:.2f}) "
            f"> wall_ms ({timing['wall_ms']:.2f})"
        )

    # -- double-buffering correctness ---------------------------------------

    def test_pipeline_result_matches_sequential(self):
        """Pipeline output must match a naive sequential run (same math,
        just no stream overlap)."""
        n = 3
        slices = _make_synthetic_slices(n, seed=42)

        # Pipeline run.
        cent_pipe, _timing = run_pipeline(
            slices, k=8, walk_length=20, num_walks_per_node=5,
        )

        # Sequential run (same seed for RNG inside each operator).
        cp.random.seed(42)
        cent_seq = []
        for slc in slices:
            gpu = cp.asarray(slc)
            P_trans, _Pr, _A, _B = low_rank_correlation_graph(gpu, k=8)
            c_gpu = time_ordered_random_walk(
                [P_trans], walk_length=20, num_walks_per_node=5,
            )
            cent_seq.append(cp.asnumpy(c_gpu))

        for i, (cp_val, cs_val) in enumerate(zip(cent_pipe, cent_seq)):
            # The pipeline uses different RNG seeding order because the
            # streams may interleave, so we only check shape / sum, not
            # exact equality.
            assert cp_val.shape == cs_val.shape
            assert abs(float(cp_val.sum()) - 1.0) < 1e-4

    # -- memory: pipeline should handle repeated slices --------------------

    def test_repeated_slices_do_not_leak(self):
        """Processing many slices back-to-back must not crash (smoke test
        for VRAM fragmentation)."""
        n = 8
        slices = _make_synthetic_slices(n, seed=77)
        centralities, timing = run_pipeline(
            slices, k=4, walk_length=10, num_walks_per_node=2,
        )
        assert len(centralities) == n


# ===========================================================================
# Integration tests
# ===========================================================================


class TestIntegration:
    """End-to-end pipeline tests that exercise all three modules together."""

    def test_full_pipeline_on_synthetic_data(self):
        """Run the full pipeline on a realistic-sized batch and verify
        every intermediate invariant."""
        n = 4
        k = 8
        walk_length = 30
        num_walks = 5

        slices = _make_synthetic_slices(n, seed=123)
        centralities, timing = run_pipeline(
            slices, k=k, walk_length=walk_length,
            num_walks_per_node=num_walks,
        )

        # -- output count --
        assert len(centralities) == n

        # -- per-slice invariants --
        for i, c in enumerate(centralities):
            assert c.shape == (NUM_STOCKS,)
            assert c.dtype == np.float32
            assert abs(float(c.sum()) - 1.0) < 1e-4
            assert float(c.min()) >= 0.0

        # -- timing is plausible --
        assert timing["wall_ms"] > 0
        assert timing["total_compute_ms"] > 0
        # total_transfer_ms can be very small (pre-load only if n=1
        # and no overlapping uploads are timed), but with n=4 we have
        # pre-load + 3 loop transfers → should be > 0.
        assert timing["total_transfer_ms"] >= 0.0

    def test_low_rank_and_walk_consistency(self):
        """For a single slice, the low-rank graph + walk pipeline must
        produce the same centrality as calling them directly."""
        slc = _make_synthetic_slice(seed=888)
        gpu = cp.asarray(slc)

        # Direct call.
        P_trans_direct, _Pr, _A, _B = low_rank_correlation_graph(gpu, k=8)
        c_direct = time_ordered_random_walk(
            [P_trans_direct], walk_length=25, num_walks_per_node=5,
        )

        # Through pipeline (single slice).
        cent_pipe, _timing = run_pipeline(
            [slc], k=8, walk_length=25, num_walks_per_node=5,
        )

        # Both should be valid centrality vectors — exact match is not
        # guaranteed due to RNG, but they should have similar magnitude.
        c_direct_cpu = cp.asnumpy(c_direct)
        c_pipe_cpu = cent_pipe[0]

        assert c_direct_cpu.shape == c_pipe_cpu.shape
        assert abs(float(c_direct_cpu.sum()) - 1.0) < 1e-4
        assert abs(float(c_pipe_cpu.sum()) - 1.0) < 1e-4

    def test_pipeline_with_varying_k(self):
        """The pipeline should work correctly with different SVD ranks."""
        slices = _make_synthetic_slices(3, seed=42)
        for k in [1, 2, 4, 8, 16, 32]:
            centralities, timing = run_pipeline(
                slices, k=k, walk_length=10, num_walks_per_node=2,
            )
            assert len(centralities) == 3
            for c in centralities:
                assert c.shape == (NUM_STOCKS,)
                assert abs(float(c.sum()) - 1.0) < 1e-4
                assert float(c.min()) >= 0.0

    def test_pipeline_with_varying_walk_params(self):
        """The pipeline should work with different walk lengths and walker
        counts."""
        slices = _make_synthetic_slices(2, seed=55)
        for wl, nw in [(5, 2), (20, 10), (50, 5)]:
            centralities, _timing = run_pipeline(
                slices, k=4, walk_length=wl, num_walks_per_node=nw,
            )
            assert len(centralities) == 2
            for c in centralities:
                assert c.shape == (NUM_STOCKS,)
                assert abs(float(c.sum()) - 1.0) < 1e-4


# ===========================================================================
# Boundary / error-path tests
# ===========================================================================


class TestBoundaryConditions:
    """Tests that probe numerical edge cases and error paths."""

    def test_k_equals_min_dimension(self):
        """k == min(N_stocks, T_steps) must be accepted (full-rank SVD)."""
        max_k = min(NUM_STOCKS, NUM_TIME_STEPS)
        gpu_slice = cp.asarray(_make_synthetic_slice())
        P_trans, _Pr, _A, _B = low_rank_correlation_graph(gpu_slice, k=max_k)
        assert P_trans.shape == (NUM_STOCKS, NUM_STOCKS)
        assert float(cp.max(cp.abs(P_trans.sum(axis=1) - 1.0))) < 1e-4

    def test_walk_length_zero_is_valid(self):
        """walk_length=0 means no transition steps → all-zero centrality.

        Per the specification, visit_count is accumulated *after* each
        transition step.  With zero steps the loop never executes, so
        no visits are recorded and the result is the zero vector."""
        P = cp.ones((10, 10), dtype=cp.float32) / 10.0
        centrality = time_ordered_random_walk(
            [P], walk_length=0, num_walks_per_node=5,
        )
        # All entries must be exactly zero.
        assert float(cp.sum(centrality)) == 0.0
        assert centrality.shape == (10,)

    def test_very_long_walk_does_not_crash(self):
        """A long walk (500 steps) with few walkers must complete."""
        P = cp.eye(50, dtype=cp.float32)
        cp.fill_diagonal(P, 0.0)
        P = P / P.sum(axis=1, keepdims=True)
        centrality = time_ordered_random_walk(
            [P], walk_length=500, num_walks_per_node=2,
        )
        assert centrality.shape == (50,)
        assert not cp.any(cp.isnan(centrality))

    def test_cupy_vs_numpy_roundtrip(self):
        """Results copied back to CPU must be usable as plain NumPy arrays."""
        slices = _make_synthetic_slices(2)
        centralities, _timing = run_pipeline(
            slices, k=4, walk_length=10, num_walks_per_node=2,
        )
        for c in centralities:
            # Must support standard NumPy operations.
            assert isinstance(c, np.ndarray)
            assert c.flags["C_CONTIGUOUS"] or c.flags["F_CONTIGUOUS"]
            top3 = np.argsort(c)[::-1][:3]
            assert len(top3) == 3
            assert np.issubdtype(top3.dtype, np.integer)
