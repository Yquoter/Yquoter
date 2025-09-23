from yquoter.utils import load_config

config = load_config()
TUSHARE_TOKEN = config["TUSHARE_TOKEN"]
CACHE_ROOT = config["CACHE_ROOT"]