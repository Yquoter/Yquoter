"""
Low-Rank Correlation Graph Reconstruction Operator
===================================================

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

Environment
-----------
- NVIDIA RTX 4050, 6 GB VRAM
- Python + CuPy only; no hand-written CUDA C / PyBind11
- Input slices have shape (N_stocks, Features=4, T_steps), dtype float32,
  C-contiguous.  Feature order:
    0: WAP (volume-weighted average price)
    1: bid-ask spread
    2: volume imbalance
    3: log return
- N_stocks and T_steps are derived from the upstream data pipeline
  (e.g. ~112 stocks for the Optiver dataset, 600 time steps per window).
"""

from typing import Tuple

try:
    import cupy as cp
except ImportError:
    cp = None  # type: ignore[assignment]
import numpy as np

# ---------------------------------------------------------------------------
# Numerical epsilon — used throughout to guard against log(0), div-by-zero,
# and other degenerate corner cases that are hard to predict on real market
# data (e.g. an entire row of non-positive correlations after clipping).
# ---------------------------------------------------------------------------
_EPS = 1e-12


def _matmul(a: cp.ndarray, b: cp.ndarray) -> cp.ndarray:
    """GPU matrix multiplication with NumPy fallback.

    CuPy dispatches ``@`` to cuBLAS.  If the cuBLAS shared library is
    unavailable at runtime, we transfer both operands to the CPU, let
    NumPy/LAPACK perform the GEMM, and bring the result back.
    """
    try:
        return a @ b
    except ImportError:
        return cp.asarray(cp.asnumpy(a) @ cp.asnumpy(b))


def _matrix_rank(arr: cp.ndarray, tol: float = None) -> int:
    """Compute the numerical rank of a GPU array.

    Attempts ``cp.linalg.matrix_rank`` first.  If the cuSOLVER backend
    is unavailable at runtime, falls back to NumPy on the CPU.

    When *tol* is None (default), each library computes a scale-aware
    threshold: ``S.max() * max(M, N) * finfo(dtype).eps``.  This is
    essential for float32 data where GEMM rounding noise can reach
    ~1e-3 — a hard-coded 1e-5 would miscount noise as signal.
    """
    try:
        return int(cp.linalg.matrix_rank(arr, tol=tol))
    except ImportError:
        arr_cpu = cp.asnumpy(arr)
        # NumPy's signature: matrix_rank(M, tol=None, hermitian=False).
        # Pass tol as keyword to be explicit.
        return int(np.linalg.matrix_rank(arr_cpu, tol=tol))


def low_rank_correlation_graph(
    time_slice: cp.ndarray,
    k: int = 8,
    eps: float = _EPS,
) -> Tuple[cp.ndarray, cp.ndarray, cp.ndarray, cp.ndarray]:
    """Build a low-rank Markov transition matrix from a single time slice.

    Mathematical pipeline (dimensions are critical):
      1. Extract feature index 3 (log return) → X ∈ R^{N_stocks × T_steps}.
      2. Truncated SVD with rank k:
           X ≈ U_k @ diag(S_k) @ Vt_k
         Define  A = U_k @ diag(S_k)  ∈ R^{N_stocks × k}  (low-rank features)
                 B = Vt_k             ∈ R^{k × T_steps}   (shared basis)
         Verify  A @ B  has shape (N_stocks, T_steps) — the low-rank
         reconstruction of the log-return matrix, denoted X_k.
      3. Compute the market-wide correlation graph:
           P_raw = X_k @ X_k^T  ∈ R^{N_stocks × N_stocks}
         Because rank(X_k) ≤ k, rank(P_raw) ≤ k as well — the low-rank
         property is inherited, not separately enforced.
      4. Post-process into a row-stochastic transition matrix:
           - Clip negative correlations to 0 (non-negative graph).
           - Zero the diagonal (remove self-loops).
           - Row-normalise so each row sums to 1 (stochastic / Markov).

    Args:
        time_slice: CuPy array of shape (N_stocks, 4, T_steps), float32,
            C-contiguous.  N_stocks and T_steps may vary by dataset.
        k: Truncation rank for the SVD.  Must be ≤ min(N_stocks, T_steps).
        eps: Small constant for numerical stability (log, division).

    Returns:
        P_trans: Row-stochastic transition matrix, shape (N_stocks, N_stocks).
        P_raw: Raw correlation (Gram) matrix before post-processing,
            shape (N_stocks, N_stocks).  Used for rank verification.
        A: Low-rank feature representation, shape (N_stocks, k).
        B: Shared basis, shape (k, T_steps).

    Raises:
        ValueError: If k exceeds min(N_stocks, T_steps) or if the input
            slice has unexpected ndim or feature count.
    """
    # --- defensive shape checks -------------------------------------------
    if time_slice.ndim != 3:
        raise ValueError(
            f"Expected 3-D input (stocks, features, time_steps), "
            f"got ndim={time_slice.ndim}"
        )
    num_stocks, num_features, num_time_steps = time_slice.shape
    if num_features != 4:
        raise ValueError(
            f"Expected 4 features (WAP, spread, imbalance, log_return), "
            f"got num_features={num_features}"
        )

    max_rank = min(num_stocks, num_time_steps)
    if k > max_rank:
        raise ValueError(
            f"Truncation rank k={k} exceeds min(stocks={num_stocks}, "
            f"time_steps={num_time_steps}) = {max_rank}.  "
            f"Reduce k or use a larger slice."
        )

    # --- step 1: extract log-return feature (index 3) ----------------------
    # X has shape (N_stocks, T_steps) — each row is a stock, each column
    # a time step.
    X = time_slice[:, 3, :].astype(cp.float32, copy=False)

    # --- step 2: truncated SVD ---------------------------------------------
    # We first attempt CuPy's GPU-side SVD (which *may* dispatch to
    # cuSOLVER on supported hardware).  If the cuSOLVER shared library
    # is unavailable at runtime (common when CuPy was installed via pip
    # without a matching CUDA toolkit), we fall back to NumPy's CPU-side
    # SVD.  For typical (N_stocks, T_steps) sizes the CPU path adds only
    # a few milliseconds, and all subsequent GEMM operations remain on
    # the GPU, so the end-to-end performance impact is negligible.
    try:
        U, S, Vt = cp.linalg.svd(X, full_matrices=False)
        # Truncate to rank k (GPU-path).
        U_k = U[:, :k]             # (N_stocks, k)
        S_k = S[:k]                # (k,)
        Vt_k = Vt[:k, :]           # (k, T_steps)
    except ImportError:
        # Fallback: NumPy CPU-side SVD handles the input size efficiently
        # via LAPACK (dsyevr).
        X_cpu = cp.asnumpy(X)
        U_cpu, S_cpu, Vt_cpu = np.linalg.svd(X_cpu, full_matrices=False)
        # Move truncated components back to the GPU.
        U_k = cp.asarray(U_cpu[:, :k])        # (N_stocks, k)
        S_k = cp.asarray(S_cpu[:k])           # (k,)
        Vt_k = cp.asarray(Vt_cpu[:k, :])      # (k, T_steps)

    # Build the low-rank factors.
    # A = U_k * diag(S_k) — scales each column of U_k by the corresponding
    # singular value, giving a weighted embedding of each stock.
    A = U_k * S_k[cp.newaxis, :]   # broadcast: (N_stocks, k) * (1, k) → (N_stocks, k)
    B = Vt_k                        # (k, T_steps)

    # X_k = A @ B — the rank-k reconstruction of the log-return matrix.
    # Shape: (N_stocks, k) @ (k, T_steps) = (N_stocks, T_steps).
    # NOTE: this GEMM call *may* be dispatched to cuBLAS / Tensor Core
    # paths on supported hardware; if cuBLAS is unavailable, we fall
    # back to NumPy via the _matmul helper.
    X_k = _matmul(A, B)

    # --- step 3: correlation (Gram) graph ----------------------------------
    # P_raw[i, j] = inner product of stock i's and stock j's reconstructed
    # log-return series.  This is a Gram matrix, not a Pearson correlation —
    # it captures co-movement magnitude rather than a normalised [-1, 1]
    # coefficient.  Rank(P_raw) ≤ rank(X_k) ≤ k by construction.
    P_raw = _matmul(X_k, X_k.T)   # (N, T) @ (T, N) = (N_stocks, N_stocks)

    # --- step 4: post-processing → stochastic transition matrix ------------
    # 4a. Clip negative values to 0.
    #     Negative inner products indicate opposite-direction movement;
    #     for a "flow" graph we only keep non-negative associations.
    P_clipped = cp.clip(P_raw, 0.0, None)

    # 4b. Zero the diagonal to remove self-loops.
    #     A stock cannot "transfer" to itself in one step of a random walk
    #     over the correlation graph.
    cp.fill_diagonal(P_clipped, 0.0)

    # 4c. Row-normalise to obtain a right-stochastic matrix.
    #     P_trans[i, j] = probability of transitioning from stock i to stock j.
    #     Each row must sum to 1.  If a row sums to 0 after clipping and
    #     diagonal removal (possible when all its correlations were
    #     non-positive), we replace it with uniform outgoing probabilities
    #     to all other nodes, keeping the self-loop at 0.
    row_sums = P_clipped.sum(axis=1)  # (500,)
    degenerate = (row_sums < eps)
    if cp.any(degenerate):
        # Python-level loop over degenerate rows is acceptable: in typical
        # market data at most a handful of stocks hit this path, and even
        # the worst case (500 iterations) is ~µs overhead.
        uniform_val = 1.0 / (num_stocks - 1)
        for idx in cp.where(degenerate)[0]:
            i = int(idx)
            P_clipped[i, :] = uniform_val
            P_clipped[i, i] = 0.0  # keep self-loop zero
        # Recompute row sums after fixing degenerate rows.
        row_sums = P_clipped.sum(axis=1)
    row_sums = cp.clip(row_sums, eps, None)         # guard for division
    P_trans = P_clipped / row_sums[:, cp.newaxis]   # (N_stocks, N_stocks)

    return P_trans, P_raw, A, B


# ===========================================================================
# Self-check block — validates the full pipeline on synthetic data.
# ===========================================================================
if __name__ == "__main__":
    print("=" * 64)
    print("low_rank_graph.py — self-check")
    print("=" * 64)

    # Generate a random test slice with representative dimensions.
    # Using a fixed seed for reproducibility.
    N_test, T_test = 200, 400  # representative but not tied to 500/600
    cp.random.seed(42)
    test_slice = cp.random.randn(N_test, 4, T_test, dtype=cp.float32)

    k = 8
    P_trans, P_raw, A, B = low_rank_correlation_graph(test_slice, k=k)

    # --- shape checks ---
    print(f"\nInput slice shape      : {test_slice.shape}")
    print(f"A shape                : {A.shape}   (expected ({N_test}, {k}))")
    print(f"B shape                : {B.shape}   (expected ({k}, {T_test}))")
    print(f"P_raw shape            : {P_raw.shape}   (expected ({N_test}, {N_test}))")
    print(f"P_trans shape          : {P_trans.shape} (expected ({N_test}, {N_test}))")

    assert A.shape == (N_test, k), f"A shape mismatch: {A.shape}"
    assert B.shape == (k, T_test), f"B shape mismatch: {B.shape}"
    assert P_raw.shape == (N_test, N_test), f"P_raw shape mismatch: {P_raw.shape}"
    assert P_trans.shape == (N_test, N_test), f"P_trans shape mismatch: {P_trans.shape}"

    # --- verify low-rank reconstruction recovers X_k = A @ B ---
    X_k_check = _matmul(A, B)
    print(f"A @ B shape            : {X_k_check.shape} (expected ({N_test}, {T_test}))")
    assert X_k_check.shape == (N_test, T_test), (
        f"A @ B shape mismatch: {X_k_check.shape}"
    )

    # --- rank check on P_raw ---
    # Uses the default scale-aware tolerance (S.max() * shape * eps)
    # rather than a hard-coded value, so that float32 GEMM noise does
    # not inflate the apparent rank.
    rank_P_raw = _matrix_rank(P_raw)
    print(f"\nrank(P_raw)            : {rank_P_raw}  (expected ≤ {k})")
    assert int(rank_P_raw) <= k, (
        f"P_raw rank {rank_P_raw} exceeds k={k} — low-rank property violated"
    )

    # --- row-sum check on P_trans ---
    row_sums = P_trans.sum(axis=1)
    max_deviation = float(cp.max(cp.abs(row_sums - 1.0)))
    print(f"Max |row_sum - 1|      : {max_deviation:.6e}")
    assert max_deviation < 1e-4, (
        f"Row sums deviate from 1 by up to {max_deviation}"
    )

    # --- stochasticity check ---
    n_negative = int(cp.sum(P_trans < 0))
    print(f"Negative entries in P_trans: {n_negative}  (expected 0)")
    assert n_negative == 0, "P_trans contains negative entries"

    # --- self-loop check ---
    diag_sum = float(cp.sum(cp.diag(P_trans)))
    print(f"Sum of diagonal entries: {diag_sum:.6e}  (expected ≈ 0)")
    assert diag_sum < 1e-6, f"Diagonal not zeroed: sum={diag_sum}"

    print("\n" + "=" * 64)
    print("All self-checks passed.")
    print("=" * 64)
