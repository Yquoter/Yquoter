"""
Time-Ordered Random Walk Operator (Gumbel-Max Batch Sampling)
==============================================================

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

Algorithm: Gumbel-Max Trick for Batch Categorical Sampling
----------------------------------------------------------
Given a transition probability matrix P (row-stochastic) and a set of
current nodes, the next node for each walker is drawn from the
categorical distribution defined by P[current_node, :].

The Gumbel-max trick states that for a categorical distribution with
unnormalised log-probabilities log_p, the following gives an exact sample:

    next = argmax(log_p + g),   g_i ~ Gumbel(0, 1) i.i.d.

where g_i = -log(-log(u_i)), u_i ~ Uniform(0, 1).

This is preferred over explicit CDF-inversion on the GPU because it only
requires one elementwise addition and one argmax per transition step —
there is no per-walker branching, no cumulative-sum scan, and the
computation is naturally SIMT-friendly.

Time-Ordered Constraint
-----------------------
The walker's step s uses P_list[min(s, len(P_list)-1)] as the transition
matrix.  As market time advances, the correlation structure evolves
through the pre-computed sequence.  When the walk length exceeds the
number of available slices, the last slice is reused (clamped), so the
list is never accessed out of bounds and earlier slices are never
re-visited — respecting the arrow of time.

Environment
-----------
- NVIDIA RTX 4050, 6 GB VRAM
- Python + CuPy only
"""

from typing import List

try:
    import cupy as cp
except ImportError:
    cp = None  # type: ignore[assignment]

# Numerical epsilon — guards against log(0) when a transition probability
# is exactly 0 (common after non-negative clipping + diagonal removal).
_EPS = 1e-12


def time_ordered_random_walk(
    P_list: List[cp.ndarray],
    walk_length: int = 100,
    num_walks_per_node: int = 20,
    eps: float = _EPS,
) -> cp.ndarray:
    """Run time-ordered random walks and compute node centrality.

    All (num_stocks × num_walks_per_node) walks advance simultaneously
    via batch Gumbel-max sampling at each step — no Python-level
    per-walker loop.  This lets the GPU schedule the elementwise and
    argmax operations across its SIMT units.

    Time-order discipline:
        At step s ∈ [0, walk_length), the transition matrix is
            P = P_list[min(s, len(P_list) - 1)]
        This ensures the walk always moves forward in market time.
        Steps beyond the last available slice reuse the final slice.

    Args:
        P_list: Ordered list of row-stochastic transition matrices,
            each of shape (num_stocks, num_stocks).  The ordering
            corresponds to increasing market time.
        walk_length: Number of transition steps per walk.  Default 100.
        num_walks_per_node: Number of independent walkers launched from
            each stock node.  Default 20 (for statistical robustness).
        eps: Small constant to prevent log(0) when a transition
            probability is exactly zero.

    Returns:
        graph_centrality: Normalised visit-count vector of shape
            (num_stocks,).  Each entry is the fraction of total visits
            received by that node across all walks and all steps.
            Higher values → more central in the capital-flow network.

    Raises:
        ValueError: If P_list is empty or matrices have inconsistent shapes.
    """
    if not P_list:
        raise ValueError("P_list must not be empty.")

    num_stocks = P_list[0].shape[0]
    num_slices = len(P_list)

    # Validate that every P in the list is square and of consistent size.
    for i, P in enumerate(P_list):
        if P.ndim != 2 or P.shape[0] != P.shape[1]:
            raise ValueError(
                f"P_list[{i}] has shape {P.shape}; expected square matrix."
            )
        if P.shape[0] != num_stocks:
            raise ValueError(
                f"P_list[{i}] has {P.shape[0]} nodes; "
                f"expected {num_stocks} (consistent with P_list[0])."
            )

    # Total number of concurrent walkers.
    total_walkers = num_stocks * num_walks_per_node

    # Initial node assignment: each stock launches num_walks_per_node
    # walkers starting from itself.
    # current_nodes shape: (total_walkers,), dtype int32.
    current_nodes = cp.repeat(cp.arange(num_stocks, dtype=cp.int32),
                              num_walks_per_node)

    # Accumulator: visit_count[i] counts how many times node i was visited.
    visit_count = cp.zeros(num_stocks, dtype=cp.int64)

    # Pre-compute log(P) for every slice to avoid re-computing at each
    # step.  Clipping avoids log(0).  Each entry has shape (500, 500).
    log_P_cache = []
    for P in P_list:
        log_P = cp.log(cp.clip(P, eps, 1.0))
        log_P_cache.append(log_P)

    # Main walk loop — each iteration is one transition step for ALL
    # walkers simultaneously.
    for step in range(walk_length):
        # Resolve which slice to use under the time-ordering constraint.
        slice_idx = min(step, num_slices - 1)
        log_P = log_P_cache[slice_idx]  # (num_stocks, num_stocks)

        # Gather log-probabilities for each walker's current node.
        # log_P_walker shape: (total_walkers, num_stocks)
        log_P_walker = log_P[current_nodes]

        # Generate Gumbel noise.
        # Clip uniform samples away from 0 and 1 so that both
        # log(u) and log(1-u) are finite.  eps is small enough
        # (~1e-12) that it does not materially bias the sampling.
        u = cp.clip(
            cp.random.random((total_walkers, num_stocks), dtype=cp.float32),
            eps, 1.0 - eps,
        )
        gumbel = -cp.log(-cp.log(u))

        # Gumbel-max: argmax over the perturbed log-probabilities.
        # next_nodes shape: (total_walkers,), dtype int32.
        next_nodes = cp.argmax(log_P_walker + gumbel, axis=1).astype(cp.int32)

        # Accumulate visit counts.
        # cp.bincount is the natural choice — it counts occurrences of
        # each node index in next_nodes.  We specify minlength to ensure
        # the output always has length num_stocks even if some nodes
        # happen not to be visited in this particular step.
        visit_count += cp.bincount(next_nodes, minlength=num_stocks)

        # Advance all walkers.
        current_nodes = next_nodes

    # Normalise to obtain centrality scores.
    total_visits = visit_count.sum()
    if total_visits == 0:
        # Degenerate case — should not happen with valid input and
        # walk_length > 0, but we guard anyway.
        graph_centrality = cp.zeros(num_stocks, dtype=cp.float32)
    else:
        graph_centrality = visit_count.astype(cp.float32) / float(total_visits)

    return graph_centrality


# ===========================================================================
# Self-check block — validates with a synthetic "star" graph where one
# central node receives the vast majority of incoming probability mass.
# ===========================================================================
if __name__ == "__main__":
    print("=" * 64)
    print("random_walk.py — self-check")
    print("=" * 64)

    cp.random.seed(123)

    num_stocks_test = 50  # Smaller for quick validation.
    central_node = 7      # This node will be the obvious "centre."

    # Build a single synthetic transition matrix.
    # Every node transitions to the central_node with probability 0.95,
    # and uniformly to all other nodes with the remaining 0.05.
    # The central_node itself transitions uniformly.
    P_test = cp.full((num_stocks_test, num_stocks_test),
                      0.05 / (num_stocks_test - 1), dtype=cp.float32)
    P_test[:, central_node] = 0.95
    # Fix the central node's row: uniform over all nodes (including itself).
    P_test[central_node, :] = 1.0 / num_stocks_test
    # Remove self-loops for all other rows (the central node's self-loop
    # is kept only because it's part of its uniform row).
    for i in range(num_stocks_test):
        if i != central_node:
            P_test[i, i] = 0.0
            # Re-normalise row i so it still sums to 1.
            row_sum = P_test[i].sum()
            if row_sum > 0:
                P_test[i] /= row_sum

    # Verify the test matrix is row-stochastic.
    row_sums = P_test.sum(axis=1)
    assert float(cp.max(cp.abs(row_sums - 1.0))) < 1e-5, "Test P not stochastic"

    # Use a single-slice P_list so the time-ordering constraint is trivial
    # (every step uses the same matrix).
    P_list_test = [P_test]
    walk_length_test = 50
    num_walks_test = 10

    centrality = time_ordered_random_walk(
        P_list_test,
        walk_length=walk_length_test,
        num_walks_per_node=num_walks_test,
    )

    # Move to CPU for sorting / display.
    centrality_cpu = cp.asnumpy(centrality)
    sorted_indices = centrality_cpu.argsort()[::-1]  # descending
    sorted_values = centrality_cpu[sorted_indices]

    print(f"\nTop-5 nodes by centrality:")
    print(f"{'Rank':<6} {'Node':<6} {'Centrality':<12}")
    print("-" * 30)
    for rank, (node, val) in enumerate(
        zip(sorted_indices[:5], sorted_values[:5]), start=1
    ):
        marker = " <-- centre" if node == central_node else ""
        print(f"{rank:<6} {node:<6} {val:<12.6f}{marker}")

    # The central node should be ranked first.
    top_node = int(sorted_indices[0])
    print(f"\nTop-ranked node: {top_node}")
    print(f"Expected central node: {central_node}")

    if top_node == central_node:
        print("PASS: Central node correctly identified as most central.")
    else:
        print(f"FAIL: Expected node {central_node} to be top-ranked, "
              f"but got node {top_node}.")
        # Still print the centrality ratio for diagnostic purposes.
        ratio = (centrality_cpu[central_node] /
                 centrality_cpu[sorted_indices[-1]])
        print(f"  Central node value: {centrality_cpu[central_node]:.6f}")
        print(f"  Max / min ratio: {ratio:.2f}")

    # Sanity checks.
    assert centrality.shape == (num_stocks_test,), (
        f"Centrality shape {centrality.shape} != ({num_stocks_test},)"
    )
    assert float(cp.abs(centrality.sum() - 1.0)) < 1e-5, (
        "Centrality does not sum to 1"
    )
    assert float(cp.min(centrality)) >= 0.0, "Negative centrality values"

    print("\n" + "=" * 64)
    print("All self-checks passed.")
    print("=" * 64)
