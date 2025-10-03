# yquoter/spider_source.py
import pandas as pd
import time
from yquoter.spider_core import crawl_kline_segments,crawl_realtime_data
from yquoter.utils import *
from typing import Union, List
def get_stock_history_spider(
    market: str,
    code: str,
    start: str,
    end: str,
    klt: int = 101,
    fqt: int = 1,
) -> pd.DataFrame:
    """统一 spider 接口，支持各市场历史数据抓取。"""
    secid = get_secid_of_eastmoney(market,code)
    def make_url(beg: str, end_: str) -> str:
        ts = int(time.time() * 1000)  # 当前时间戳用于防止缓存
        return (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            f"&ut=fa5fd1943c7b386f1734de82599f7dc"
            f"&fields1=f1,f2,f3,f4,f5,f6"  # 基础字段
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"  # K线字段
            f"&klt={klt}&fqt={fqt}&beg={beg}&end={end_}&lmt=10000&_={ts}"
        )
    def parse_kline(json_data):
        klines = json_data.get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            parts = line.split(',')
            rows.append([parts[0], parts[1], parts[3], parts[4], parts[2], parts[5], parts[6], parts[8], parts[10],
                        parts[9], parts[7]])
        return rows
    return crawl_kline_segments(start, end, make_url, parse_kline)
###############################技术面####################################
def get_secid_of_eastmoney(market: str,code: str):
    market = market.lower().strip()
    if market == "cn":
        if code.startswith(("600", "601", "603", "605")):
            secid = f"1.{code}"  # 上交所
        elif code.startswith(("000", "001", "002", "003", "300", "301")):
            secid = f"0.{code}"  # 深交所
        else:
            raise CodeFormatError("未知A股代码，无法判断市场")
    elif market == "hk":
        secid = f"116.{code.zfill(5)}"  # 确保代码五位数，前补零
    elif market == "us":
        secid = f"105.{code.upper()}"  # 美股代码大写标准化
    else:
        raise ValueError(f"未知市场：{market}")
    return secid

#此处修改完还要修改初始化部分
dict_of_eastmoney = {
    "latest": "f2",
    "change%": "f3",
    "change": "f4",
    "volume": "f5",
    "amount": "f6",
    "amplitude": "f7",
    "turnover%": "f8",
    "pe_dynamic": "f9",
    "vol_ratio": "f10",
    "5min_change%": "f11",
    "code": "f12",
    "market": "f13",
    "name": "f14",
    "high": "f15",
    "low": "f16",
    "open": "f17",
    "pre_close": "f18",
    "total_market_value": "f20",
    "circulating_market_value": "f21",
    "price_rise_speed": "f22",
    "pb": "f23",
    "60day_change%": "f24",
    "ytd_price_change_percent": "f25",
    "listing_date": "f26",
    "pre_settlement_price": "f28",
    "last_trade_volume": "f30",
    "spot_exchange_bid_price": "f31",
    "spot_exchange_ask_price": "f32",
    "order_ratio": "f33",
    "external_market": "f34",
    "internal_market": "f35",
    "weighted_roe_latest_qtr": "f37",
    "total_share_capital": "f38",
    "circulating_a_shares_10k": "f39",
    "total_revenue_latest_qtr": "f40",
    "total_revenue_yoy_latest_qtr": "f41",
    "total_profit_latest_qtr": "f44",
    "net_profit_latest_qtr": "f45",
    "net_profit_growth_rate_yoy_latest_qtr": "f46",
    "undistributed_profit_per_share": "f48",
    "gross_profit_margin_latest_qtr": "f49",
    "total_assets_latest_qtr": "f50",
    "debt_ratio": "f57",
    "shareholders_equity": "f58",
    "main_force_net_inflow_today": "f62",
    "extra_large_order_inflow": "f64",
    "extra_large_order_outflow": "f65",
    "extra_large_order_net_inflow_today": "f66",
    "extra_large_order_net_ratio": "f69",
    "large_order_inflow": "f70",
    "large_order_outflow": "f71",
    "large_order_net_inflow_today": "f72",
    "large_order_net_ratio": "f75",
    "medium_order_inflow": "f76",
    "medium_order_outflow": "f77",
    "medium_order_net_inflow_today": "f78",
    "medium_order_net_ratio_pct": "f81",
    "small_order_inflow": "f82",
    "small_order_outflow": "f83",
    "small_order_net_inflow_today": "f84",
    "small_order_net_ratio": "f87",
    "industry": "f100",
    "regional_sector": "f102",
    "remarks": "f103",
    "number_of_gaining_stocks": "f104",
    "number_of_declining_stocks": "f105",
    "number_of_flat_stocks": "f106",
    "eps_1": "f112",
    "net_asset_per_share": "f113",
    "pe_ratio_static": "f114",
    "pe_ratio_ttm": "f115",
    "trading_time": "f124",
    "sector_leading_stock": "f128",
    "net_profit": "f129",
    "ps_ratio_ttm": "f130",
    "pcf_ratio_ttm": "f131",
    "total_operating_revenue_ttm": "f132",
    "dividend_yield": "f133",
    "industry_sector_constituent_count": "f134",
    "net_assets": "f135",
    "net_profit_ttm": "f138",
    "5day_main_force_net_amount": "f164",
    "5day_extra_large_order_net_amount": "f166",
    "5day_large_order_net_amount": "f168",
    "5day_medium_order_net_amount": "f170",
    "5day_small_order_net_amount": "f172",
    "10day_main_force_net_amount": "f174",
    "10day_extra_large_order_net_amount": "f176",
    "10day_large_order_net_amount": "f178",
    "10day_medium_order_net_amount": "f180",
    "10day_small_order_net_amount": "f182",
    "convertible_bond_subscription_code": "f348",
    "convertible_bond_subscription_date": "f243",
    "limit_up_price": "f350",
    "limit_down_price": "f351",
    "average_price": "f352"
    }


def map_fields_of_eastmoney(fields: list[str])->list[str]:
    result = []
    for field in fields:
        if field in dict_of_eastmoney:
            result.append(dict_of_eastmoney[field])
        else:
            raise ValueError(f"无效的字段:{field}")
    return result

def get_stock_realtime_spider(
    market: str,
    codes: Union[str, list[str]] = [],
    fields: Union[str,list[str]] = [],
) -> pd.DataFrame:
    if isinstance(codes, str):
        codes = [codes]
    if isinstance(fields, str):
        fields = [fields]

    # 清洗用户输入的数据并正确初始化
    if codes == "" or codes == []:
        raise ValueError("代码或代码列表不可为空")
    if fields == "" or fields == []:
        #test,到时候讨论决定要以什么作为默认输出
        fields = ["code","latest","pe_dynamic","open","high","low","pre_close"]

    if "code" not in fields:
        fields.insert(0, "code")
    #if "name" not in fields:
    #   fields.insert(1, "name")

    url_fields = map_fields_of_eastmoney(fields)
    def get_fields_number(field: str) -> int:
        return int(field[1:])
    url_fields.sort(key=get_fields_number)

    secids = []
    for percode in codes:
        persecid = get_secid_of_eastmoney(market,percode)
        secids.append(persecid)

    def make_realtime_url() -> str:
        ts = int(time.time() * 1000)
        # 构建URL
        return (
            f"https://push2.eastmoney.com/api/qt/ulist.np/get"
            f"?OSVersion=14.3"
            f"&appVersion=6.3.8"
            f"&fields={','.join(url_fields)}"
            f"&fltt=2"
            f"&plat=Iphone"
            f"&product=EFund"
            f"&secids={','.join(secids)}"
            f"&serverVersion=6.3.6"
            f"&version=6.3.8"
            f"&_={ts}"
        )
    def parse_realtime_data(json_data):
        realtime_data = json_data.get("data", {}).get("diff", [])
        result = []
        for single_data in realtime_data:
            rows = []
            for value in single_data.values():
                rows.append(value)
            result.append(rows)
        return result
    return crawl_realtime_data(make_realtime_url, parse_realtime_data, url_fields, fields, dict_of_eastmoney)

if __name__ == "__main__":
    pd.set_option('display.max_columns', None)
    pd.set_option('display.float_format', None)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_colwidth', 100)
    pd.set_option('display.expand_frame_repr', False)
    df = get_stock_history_spider("cn","600519","20241002","20241012")
    print(df)
    df = get_stock_realtime_spider("hk",codes=["00700","02583"])
    print(df)
