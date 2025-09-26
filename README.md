# Yquoter
Yquoter: Your universal cross-market quote fetcher. Fetch A-shares, H-shares, and US stock prices easily via one interface.
<img width="640" height="320" alt="yquoter_github_banner" src="https://github.com/user-attachments/assets/0384fdfb-3383-4fc2-89f5-eed7fab16ae6" />

---
## structure
```
yquoter/
├── yquoter/
│   ├── __init__.py       # 暴露接口
│   ├── datasource.py     # 统一数据源接口
│   ├── tushare_source.py # 仅封装 tushare 的 raw 实现
│   ├── spider_source.py  # 自爬虫的 fallback 数据源
│   ├── spider_core.py    # 爬虫机制
│   ├── config.py         # 管理 token、路径
│   ├── .env              # 管理tuShare的token
│   ├── indicators.py     # 指标计算工具
│   ├── logger.py         # 日志配置
│   ├── cache.py          # 本地缓存管理
│   └── utils.py          # 通用函数
│
├── examples/
│   └── basic_usage.ipynb # 示例 Jupyter Notebook
│
├── temp/                 # debug
├── .cache/               # 缓存
├── setup.py              # 包配置（可上传 PyPI）
├── requirements.txt      # 依赖声明
├── LICENSE               # Apache 2.0 开源协议
├── README.md             # 项目说明
├── .gitignore            # 忽略文件配置
└── .github/workflows/ci.yml  # GitHub Actions 自动测试
```
---
## Contribution Guide
We welcome Issues and Pull Requests. Before submitting a PR, please ensure that you:

Adhere to the project's coding standards.

Add necessary test cases.

Update relevant documentation.

## License
This project is licensed under the Apache License. See the LICENSE file for details.
