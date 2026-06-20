# Yquant-Alpha

基于 CPU-GPU 异构流式架构的时空金融图采样与量化分析系统。

## 项目结构

```
blank/
├── __init__.py              # 包入口，GPU 优雅降级
├── data_loader.py           # [CPU] 流式读取 book_train.parquet
├── feature_engine.py        # [CPU] 4 个高频特征计算
├── tensor_builder.py        # [CPU] DataFrame → (N,4,T) Tensor
├── pipeline_runner.py       # [CPU] 总调度器
├── pipeline_manager.py      # [GPU] 双 CUDA Stream 流水线管理器
├── low_rank_graph.py        # [GPU] 低秩关联图重构 (截断 SVD)
├── random_walk.py           # [GPU] 时序保序随机游走 (Gumbel-Max)
├── verify_pipeline.py       # 端到端验证脚本
├── test_gpu_pipeline.py     # GPU 算子单元测试
└── members_work/            # 组员原始交付件
```

## 我在组员基础上新增的内容

### 1. CPU 侧数据处理流水线（4 个模块）

| 模块 | 做了什么 |
|:--|:--|
| `data_loader.py` | 从 1.67 亿行 Parquet 中按 time_id 窗口流式读取，PyArrow predicate pushdown 只扫描目标数据，单窗口常驻内存 |
| `feature_engine.py` | 用 Level 1 订单簿数据（bid_price1/ask_price1/bid_size1/ask_size1）逐股票逐 tick 计算 4 个高频衍生特征：**WAP**（加权平均价）、**Bid-Ask Spread**（买卖价差）、**Volume Imbalance**（量不平衡度）、**Log Return**（对数收益率）。纯 NumPy 向量化实现，处理除零/空 group 等边界情况 |
| `tensor_builder.py` | 将多级索引的特征 DataFrame 重构为 `(N_stocks, 4, T)` C-contiguous float32 数组。缺失 tick forward-fill 补齐，不连续 stock_id 对齐到全局字典序，保证与 GPU 侧 `graph_centrality` 索引一一对应 |
| `pipeline_runner.py` | CPU 侧总调度：pre-scan 发现 stock/time ID → 遍历时间窗 → 算特征 → 组 Tensor → 产出 `list[np.ndarray]`。11.6 秒处理 10 个窗口（~112 stocks × 600 ticks） |

### 2. 集成与适配

- **模块导入修正**：将组员 GPU 代码从相对导入（`from low_rank_graph import ...`）改为包内绝对导入（`from blank.low_rank_graph import ...`），适配 `blank/` 包结构
- **优雅降级**：`__init__.py` 中 CuPy 可用性检测，无 GPU 时自动回退 stub `run_pipeline()`，CPU 流水线始终可运行
- **benchmark_pipeline()**：在组员的 `pipeline_manager.py` 中补充了端到端性能基准函数，串联 CPU → GPU 全流程并输出分阶段耗时
- **CuPy 可选导入**：在 `low_rank_graph.py` 和 `random_walk.py` 中添加 `try/except` 保护，允许在无 GPU 环境下进行类型检查和模块导入
- **环境适配**：解决 CUDA 13.2 + NumPy 版本冲突（pandas 3.x / pyarrow / bottleneck / numexpr 兼容性）

### 3. 验证

- `verify_pipeline.py`：端到端验证 CPU → GPU 全流程，10 窗口/20 窗口两档测试
- 实测数据：**10 窗口 CPU 11.6s，GPU 1.9s**（含 SVD + 随机游走）

## 接口

```python
from blank import run_cpu_pipeline, run_pipeline

# CPU 侧：流式读 parquet → 特征 → Tensor
slices = run_cpu_pipeline(
    parquet_path="book_train.parquet",
    time_ids_subset=[5, 11, 16],  # None = 全量 3830 窗口
)
# slices: list of np.ndarray, 每个 (112, 4, 600) float32

# GPU 侧：低秩图重构 → 随机游走 → 中心度
centralities, timing = run_pipeline(
    slices,
    k=8,                    # SVD 截断秩
    walk_length=100,        # 随机游走步数
    num_walks_per_node=20,  # 每节点游走数
)
# centralities: list of np.ndarray, 每个 (112,) float32
```

## 环境要求

- Python 3.9+
- pandas, numpy, pyarrow
- **GPU 模式**：NVIDIA GPU + CUDA 12/13 + `pip install cupy-cuda13x`
- 无 GPU 时 CPU 流水线正常运行，GPU 部分返回 stub 结果
