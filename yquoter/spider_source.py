# yquoter/spider_source.py
import pandas as pd
import time
from yquoter.spider_core import crawl_kline_segments, crawl_realtime_data, crawl_structured_data
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
    """
    Unified spider interface for fetching historical stock data across markets (Eastmoney source)

        Args:
            market: Market identifier ('cn' for China, 'hk' for Hong Kong, 'us' for US)
            code: Stock code
            start: Start date for data fetching (format: "YYYYMMDD")
            end: End date for data fetching (format: "YYYYMMDD")
            klt: K-line type code (default: 101 for 1min; 1=daily, 2=weekly, etc.)
            fqt: Forward/factor adjustment type (default: 1 for adjusted data)

        Returns:
            DataFrame containing historical K-line data
    """
    logger.info(f"Starting historical data fetch by spider: {market}:{code}")

    secid = get_secid_of_eastmoney(market,code)
    def make_url(beg: str, end_: str) -> str:
        """Construct Eastmoney API URL for historical K-line data"""
        ts = int(time.time() * 1000)  # Timestamp to avoid caching
        return (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            f"&ut=fa5fd1943c7b386f1734de82599f7dc"
            f"&fields1=f1,f2,f3,f4,f5,f6"  # Basic fields
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"  # K-line specific fields
            f"&klt={klt}&fqt={fqt}&beg={beg}&end={end_}&lmt=10000&_={ts}"
        )
    def parse_kline(json_data):
        """Parse Eastmoney K-line JSON response into structured 2D list"""
        klines = json_data.get("data", {}).get("klines", [])
        rows = []
        # Map parsed parts to standard columns: [date, open, high, low, close, volume, amount, change%, turnover%, change, amplitude%]
        for line in klines:
            parts = line.split(',')
            rows.append([parts[0], parts[1], parts[3], parts[4], parts[2], parts[5], parts[6], parts[8], parts[10],
                        parts[9], parts[7]])
        return rows
    return crawl_kline_segments(start, end, make_url, parse_kline)

def get_secid_of_eastmoney(market: str,code: str):
    """
    Generate Eastmoney-specific 'secid' (security ID) based on market and stock code

        Args:
            market: Market identifier ('cn', 'hk', 'us')
            code: Raw stock code

        Returns:
            Eastmoney-standard secid string

        Raises:
            CodeFormatError: If A-share code format is unrecognized
            ValueError: If market is unknown
    """
    market = market.lower().strip()
    if market == "cn":
        # Classify A-share secid by code prefix (Shanghai/Shenzhen Exchange)
        if code.startswith(("600", "601", "603", "605", "688")):
            secid = f"1.{code}"  # Shanghai Stock Exchange
        elif code.startswith(("000", "001", "002", "003", "300", "301")):
            secid = f"0.{code}"  # Shenzhen Stock Exchange
        else:
            raise CodeFormatError("Unrecognized A-share code; cannot determine exchange")
    elif market == "hk":
        secid = f"116.{code.zfill(5)}"  # HKEX: Pad code to 5 digits with leading zeros
    elif market == "us":
        secid = f"105.{code.upper()}"  # US stocks: Standardize code to uppercase
    else:
        logger.error(f"Unrecognized market: {market}")
        raise ValueError(f"Unknown market: {market}")
    logger.info(f"Generated Eastmoney secid: {secid}")
    return secid

# Eastmoney field mapping: User-friendly name -> Eastmoney internal field code
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


def map_fields_of_eastmoney(fields: list[str]) -> list[str]:
    """
    Map user-friendly field names to Eastmoney internal field codes

        Args:
            fields: List of user-friendly field names (e.g., ["latest", "change%"])

        Returns:
            List of corresponding Eastmoney field codes (e.g., ["f2", "f3"])

        Raises:
            ValueError: If any user-friendly field name is invalid (not in dict_of_eastmoney)
    """
    result = []
    for field in fields:
        if field in dict_of_eastmoney:
            result.append(dict_of_eastmoney[field])
        else:
            logger.error(f"Field {field} is not in dict_of_eastmoney")
            raise ValueError(f"Invalid field: {field}")
    logger.info(f"Mapped {len(result)} fields to EastMoney")
    return result

def get_stock_realtime_spider(
    market: str,
    codes: Union[str, list[str]] = [],
    fields: Union[str, list[str]] = [],
) -> pd.DataFrame:
    """
    Spider interface for fetching real-time stock data from Eastmoney

        Args:
            market: Market identifier ('cn', 'hk', 'us')
            codes: Single stock code or list of codes (cannot be empty)
            fields: Single field name or list of fields (defaults to ["code","latest","pe_dynamic","open","high","low","pre_close"] if empty)

        Returns:
            DataFrame containing real-time stock data with user-specified fields

        Raises:
            ValueError: If codes/fields are empty or invalid
    """
    logger.info(f"Fetching real-time stock data from spider")
    # Convert single string inputs to lists for consistency
    if isinstance(codes, str):
        codes = [codes]
    if isinstance(fields, str):
        fields = [fields]

    # Validate and clean input
    if not codes: # Check if codes list is empty
        logger.error("No codes provided")
        raise ValueError("Code(s) can't be none.")
    if not fields:# Set default fields if none provided (to be finalized via discussion)
        logger.info("No fields provided, initial fields will be used.")
        fields = ["code", "latest", "pe_dynamic", "open", "high", "low", "pre_close"]

    if "code" not in fields:
        fields.insert(0, "code")
    #if "name" not in fields:
    #   fields.insert(1, "name")

    url_fields = map_fields_of_eastmoney(fields)
    def get_fields_number(field: str) -> int:
        return int(field[1:])
    url_fields.sort(key=get_fields_number)

    # Generate Eastmoney secids for all input codes
    secids = []
    for percode in codes:
        persecid = get_secid_of_eastmoney(market,percode)
        secids.append(persecid)

    def make_realtime_url() -> str:
        """Construct Eastmoney API URL for real-time data"""
        ts = int(time.time() * 1000)
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
        """Parse Eastmoney real-time JSON response into structured 2D list"""
        realtime_data = json_data.get("data", {}).get("diff", [])
        result = []
        for single_data in realtime_data:
            # Extract values in the order of sorted url_fields
            rows = []
            for value in single_data.values():
                rows.append(value)
            result.append(rows)
        return result
    return crawl_realtime_data(make_realtime_url, parse_realtime_data, url_fields, fields, dict_of_eastmoney)

def get_stock_financials_spider(
        market: str,
        code: str,
        end_day: str,
        report_type: str = 'CWBB',  # Default to Consolidated Financial Statements
        limit: int = 12,  # Last 12 periods
) -> pd.DataFrame:
    """
    Spider interface for fetching stock financial statements (Eastmoney source)

        Args:
            market: Market identifier ('cn', 'hk', 'us')
            code: Stock code
            end_day: The end date for the last report period
            report_type: Report type, e.g., 'CWBB' (Consolidated), 'LRB' (Profit)
            limit: Number of latest reports to fetch

        Returns:
            DataFrame containing standardized financial data
    """
    if market in ("hk", "us"):
        logger.warning(f"Data for market '{market}' is not yet implemented via Spider. Returning empty DataFrame.")
        return pd.DataFrame()
    elif market == "cn":
        logger.info(f"Fetching financials data for {market}:{code}, end_day: {end_day}, type: {report_type}")
        secid = get_secid_of_eastmoney(market, code)

        # This API typically returns the last N report periods
        def make_financials_url() -> str:
            return (
                f"https://datacenter-web.eastmoney.com/api/data/v1/get"
                f"?reportName=RPT_F10_FIN_STATEMENT"
                f"&columns=REPORT_DATE,SECURITY_CODE,BASIC_EPS,TOTAL_ASSET,TOTAL_LIABILITY,NET_PROFIT"
                f"&filter=(SECURITY_CODE='{code}')(REPORT_TYPE='{report_type}')"
                f"&sortTypes=-1&sortFills=REPORT_DATE"
                f"&pageNumber=1&pageSize={limit}"
                f"&_={int(time.time() * 1000)}"
            )

        # Example columns for a general financial statement
        financial_cols = ['REPORT_DATE', 'SECURITY_CODE', 'BASIC_EPS', 'TOTAL_ASSET', 'TOTAL_LIABILITY', 'NET_PROFIT']

        def parse_financials(json_data):
            """Parse Eastmoney F10 Financial JSON"""
            data = json_data.get("result", {}).get("data", [])
            rows = []
            for item in data:
                # Match data fields to our expected order in financial_cols
                rows.append([
                    item.get('REPORT_DATE', ''),
                    item.get('SECURITY_CODE', ''),
                    item.get('BASIC_EPS', 0),
                    item.get('TOTAL_ASSET', 0),
                    item.get('TOTAL_LIABILITY', 0),
                    item.get('NET_PROFIT', 0)
                ])
            return rows

        # Return the structured data using the general crawler
        return crawl_structured_data(make_financials_url, parse_financials, financial_cols)


def get_stock_profile_spider(
        market: str,
        code: str,
) -> pd.DataFrame():  # TODO!Not yet!
    """
    Spider interface for fetching stock fundamental profile (Eastmoney source)

        Args:
            market: Market identifier ('cn', 'hk', 'us')
            code: Stock code

        Returns:
            DataFrame containing key profile data (e.g., industry, main business, listing date)
    """
    if market in ("hk", "us"):
        logger.warning(f"Data for market '{market}' is not yet implemented via Spider. Returning empty DataFrame.")
        return pd.DataFrame()
    elif market == "cn":
        logger.info(f"Fetching profile data for {market}:{code}")
        secid = get_secid_of_eastmoney(market, code)

        # Eastmoney F10 Basic Profile API (Simplified Example)
        def make_profile_url() -> str:
            # Note: Profile often requires HTML parsing, but we look for a structured API
            return (
                f"https://emh5.eastmoney.com/api/F10/CompanyProfile/GetCompanyProfile?code={secid}"  # Example API
            )

        # Example columns for profile data
        profile_cols = ['CODE', 'NAME', 'INDUSTRY', 'MAIN_BUSINESS', 'LISTING_DATE']

        def parse_profile(json_data):
            data = json_data.get('data', {})
            info = data.get('jbzl', {})
            if not info:
                logger.warning("No 'jbzl' field found in profile response.")
                return []

            rows = [[
                info.get('SECUCODE', code),
                info.get('SECURITY_NAME_ABBR', ''),
                info.get('INDUSTRY', ''),
                info.get('BUSINESS_SCOPE', ''),
                info.get('LISTING_DATE', '')
            ]]
            return rows

        # Return the structured data using the general crawler
        return crawl_structured_data(make_profile_url, parse_profile, profile_cols)

def get_stock_factors_spider(
        market: str,
        code: str,
        trade_date: str
) -> pd.DataFrame():  # TODO!Not yet!
    """
    Spider interface for fetching stock fundamental factors (Eastmoney source)

        Args:
            market: Market identifier ('cn', 'hk', 'us')
            code: Stock code
            trade_date: The date for the factor snapshot (format: "YYYYMMDD")

        Returns:
            DataFrame containing standardized factors (e.g., PB, PE_TTM, Total Market Cap)
    """
    if market in ("hk", "us"):
        logger.warning(f"Data for market '{market}' is not yet implemented via Spider. Returning empty DataFrame.")
        return pd.DataFrame()
    elif market == "cn":
        logger.info(f"Fetching factors data for {market}:{code} on date: {trade_date}")
        secid = get_secid_of_eastmoney(market, code)

        # Eastmoney API for historical valuations (PE/PB/PS)
        def make_factors_url() -> str:
            return (
                f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
                f"?secid={secid}"
                f"&fields1=f1,f2,f3,f4,f5,f6"
                f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f169,f170"  # Include TTM_PE (f169) and TTM_PB (f170)
                f"&klt=1&fqt=1&beg={trade_date}&end={trade_date}&lmt=1&_={int(time.time() * 1000)}"
            )

        # Factors columns often come directly from the K-line data in Eastmoney,
        # but we will extract specific valuation metrics.
        factor_cols = ['TRADE_DATE', 'PE_TTM', 'PB', 'TOTAL_MARKET_CAP']

        def parse_factors(json_data):
            """Parse K-line API response to get factors for a single day"""
            klines = json_data.get("data", {}).get("klines", [])
            rows = []
            if klines:
                # The line contains many comma-separated values;
                # we assume the custom fields (f169, f170) are included at the end.
                line = klines[0].split(',')

                # This mapping is *very* fragile and depends on the fieds2 parameter order!
                # We assume f169 (PE_TTM) is the 13th element, f170 (PB) is the 14th element,
                # and Total Market Cap (f20) is not directly in the K-line API.

                # To get market cap, you'd usually need a separate API or rely on the real-time dict
                # Since K-line API is the closest, we'll try to extract what's there:
                rows.append([
                    line[0],  # Date
                    line[-2],  # Assuming PE_TTM is the second to last field (f169)
                    line[-1],  # Assuming PB is the last field (f170)
                    0  # Placeholder for Market Cap (Needs dedicated API)
                ])
            return rows

        # Return the structured data using the general crawler
        return crawl_structured_data(make_factors_url, parse_factors, factor_cols)


if __name__ == "__main__":
    df_1 = get_stock_factors_spider(market="cn", code="688256", trade_date="20250312")
    print(df_1)
    df_2 = get_stock_profile_spider(market="cn", code="688256")
    print(df_2)
    df_3 = get_stock_financials_spider("cn", "688256", "20250820")
    print(df_3)


