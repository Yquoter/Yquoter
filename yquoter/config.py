from dotenv import load_dotenv
import os

# 加载 .env 文件
load_dotenv()

# 配置项读取
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN")
CACHE_ROOT = os.getenv("CACHE_ROOT", ".cache")

if not TUSHARE_TOKEN:
    raise ValueError("请在 .env 中设置 TUSHARE_TOKEN")

if __name__ == "__main__":
    print("TUSHARE_TOKEN:", TUSHARE_TOKEN[:5] + "..." if TUSHARE_TOKEN else "None")
    print("CACHE_ROOT:", CACHE_ROOT)