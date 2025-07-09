# Yquoter
Yquoter: Your universal cross-market quote fetcher. Fetch A-shares, H-shares, and US stock prices easily via one interface.
---
## structure
```
yquoter/
├── yquoter/
│   ├── __init__.py
│   ├── base.py           # 公共工具函数与统一接口
│   ├── cn.py             # A 股行情抓取模块
│   ├── hk.py             # 港股行情抓取模块
│   ├── us.py             # 美股行情抓取模块
│   ├── cache.py          # 本地缓存管理
│   └── utils.py          # 通用函数
│
├── examples/
│   └── basic_usage.ipynb # 示例 Jupyter Notebook
│
├── temp/                 # debug
├── .cache/                # 缓存
├── tests/
│   └── test_china.py     # 单元测试
│
├── setup.py              # 包配置（可上传 PyPI）
├── requirements.txt      # 依赖声明
├── LICENSE               # Apache 2.0 开源协议
├── README.md             # 项目说明
├── .gitignore            # 忽略文件配置
└── .github/workflows/ci.yml  # GitHub Actions 自动测试
```
