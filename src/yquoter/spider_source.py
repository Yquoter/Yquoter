# yquoter/spider_source.py
# Copyright 2025 Yodeesy
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

from datetime import datetime
from typing import Union

import pandas as pd

import time
from yquoter.spider_core import (
    crawl_kline_segments,
    crawl_realtime_data,
    crawl_structured_data,
    _async_crawl_kline_segments,
    _async_crawl_realtime_data,
    _async_crawl_structured_data,
    logger,
)
from yquoter.exceptions import CodeFormatError
from yquoter.config import (
    EASTMONEY_KLINE_MAPPING,
    EASTMONEY_REALTIME_MAPPING,
    EASYMONEY_FINANCIALS_MAPPING,
    REALTIME_STANDARD_FIELDS,
)
from yquoter.plugin_base import DataSource

# Eastmoney field mapping: User-friendly name -> Eastmoney internal field code
dict_of_eastmoney = {v: k for k, v in EASTMONEY_REALTIME_MAPPING.items()}

# Standard column order for K-line data
_KLINE_STANDARD_ORDER = [
    "date", "open", "high", "low", "close",
    "vol", "amount", "change%", "turnover%", "change", "amplitude%",
]

# Order of fields as returned by the Eastmoney K-line API (based on fields2 parameter)
_KLINE_FIELD_CODES = ["f51", "f52", "f53", "f54", "f55", "f56", "f57", "f58", "f59", "f60", "f61"]


def get_stock_history_spider(
    market: str,
    code: str,
    start: str,
    end: str,
    klt: int = 101,
    fqt: int = 1,
) -> pd.DataFrame:
    """Fetch historical K-line data via Eastmoney spider.

    Args:
        market: Market identifier ('cn' for China, 'hk' for Hong Kong,
            'us' for US).
        code: Stock code.
        start: Start date in "YYYYMMDD" format.
        end: End date in "YYYYMMDD" format.
        klt: K-line type code. Default is 101 (daily).
        fqt: Forward/factor adjustment type. Default is 1 (adjusted data).

    Returns:
        pd.DataFrame: DataFrame containing historical K-line data.
    """
    logger.info(f"Starting historical data fetch by spider: {market}:{code}")

    secid = get_secid_of_eastmoney(market, code)

    def make_url(beg: str, end_: str) -> str:
        """Construct Eastmoney API URL for historical K-line data."""
        ts = int(time.time() * 1000)
        return (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            f"&ut=fa5fd1943c7b386f1734de82599f7dc"
            f"&fields1=f1,f2,f3,f4,f5,f6"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            f"&klt={klt}&fqt={fqt}&beg={beg}&end={end_}&lmt=10000&_={ts}"
        )

    def parse_kline(json_data):
        """Parse Eastmoney K-line JSON response into structured 2D list.

        Uses EASTMONEY_KLINE_MAPPING from config to dynamically map
        API field codes to standard column names.
        """
        klines = json_data.get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            parts = line.split(",")
            # Build a dict mapping standard column name -> raw value
            row_dict = {}
            for i, fcode in enumerate(_KLINE_FIELD_CODES):
                if i < len(parts):
                    standard_name = EASTMONEY_KLINE_MAPPING.get(fcode, fcode)
                    row_dict[standard_name] = parts[i]
            # Build row in standard column order
            rows.append([row_dict.get(col, "") for col in _KLINE_STANDARD_ORDER])
        return rows

    return crawl_kline_segments(start, end, make_url, parse_kline)

def get_secid_of_eastmoney(market: str, code: str) -> str:
    """Generate Eastmoney security ID (secid) from market and stock code.

    Args:
        market: Market identifier ('cn', 'hk', 'us').
        code: Raw stock code.

    Returns:
        str: Eastmoney-standard secid string.

    Raises:
        CodeFormatError: If A-share code format is unrecognized.
        ValueError: If market is unknown.
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

def map_fields_of_eastmoney(fields: list[str]) -> list[str]:
    """Map user-friendly field names to Eastmoney internal field codes.

    Args:
        fields: List of user-friendly field names (e.g., ["latest", "change%"]).

    Returns:
        list[str]: List of corresponding Eastmoney field codes
            (e.g., ["f2", "f3"]).

    Raises:
        ValueError: If any field name is not found in the Eastmoney mapping.
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


def get_xueqiu_symbol(market: str, code: str) -> str:
    """Generate Xueqiu-specific symbol from market and stock code.

    Args:
        market: Market identifier ('cn', 'hk', 'us').
        code: Raw stock code.

    Returns:
        str: Xueqiu-standard symbol string (e.g., 'SH600000', 'HK00700',
            'AAPL').

    Raises:
        CodeFormatError: If the A-share code prefix is unrecognized.
        ValueError: If the market identifier is unknown.
    """
    market = market.lower().strip()
    code = code.strip()

    if market == "cn":
        if code.startswith(("600", "601", "603", "605", "688")):
            symbol = f"SH{code}"
        elif code.startswith(("000", "001", "002", "300", "301")):
            symbol = f"SZ{code}"
        elif code.startswith(("8")):
            symbol = f"BJ{code}"
        else:
            logger.error(f"Unrecognized CN A-share code prefix: {code}")
            raise CodeFormatError(f"Unrecognized A-share code: {code}; cannot determine exchange for Xueqiu.")

    elif market == "hk":
        symbol = f"HK{code.zfill(5)}"

    elif market == "us":
        symbol = code.upper()

    else:
        logger.error(f"Unrecognized market: {market}")
        raise ValueError(f"Unknown market identifier for Xueqiu: {market}")

    logger.info(f"Generated Xueqiu symbol: {symbol}")
    return symbol

def get_stock_realtime_spider(
    market: str,
    code: Union[str, list[str]],
    fields: Union[str, list[str]] = None,
) -> pd.DataFrame:
    """Fetch real-time stock data from Eastmoney spider.

    Args:
        market: Market identifier ('cn', 'hk', 'us').
        code: Single stock code or list of codes. Cannot be empty.
        fields: Single field name or list of fields. Defaults to standard
            realtime fields if not provided.

    Returns:
        pd.DataFrame: Real-time stock data with requested fields.

    Raises:
        ValueError: If codes list is empty or a field name is invalid.
    """
    logger.info(f"Fetching real-time stock data from spider")
    # Convert single string inputs to lists for consistency
    if isinstance(code, str):
        code = [code]
    if isinstance(fields, str):
        fields = [fields]

    # Validate and clean input
    if not code:  # Check if codes list is empty
        logger.error("No code(s) provided")
        raise ValueError("Code(s) can't be none.")
    if not fields:  # Set default fields if none provided (to be finalized via discussion)
        logger.info("No fields provided, initial fields will be used.")
        fields = REALTIME_STANDARD_FIELDS
    if "code" not in fields:
        fields.insert(0, "code")
    if "name" not in fields:
        fields.insert(1, "name")
    if "datetime" not in fields:
        fields.insert(2, "datetime")

    url_fields = map_fields_of_eastmoney(fields)
    def get_fields_number(field: str) -> int:
        return int(field[1:])
    url_fields.sort(key=get_fields_number)

    # Generate Eastmoney secids for all input codes
    secids = []
    for percode in code:
        persecid = get_secid_of_eastmoney(market, percode)
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
            current_date = datetime.now().strftime("%Y%m%d %H:%M")
            rows.append(current_date)
            result.append(rows)
        return result

    return crawl_realtime_data(make_realtime_url, parse_realtime_data, url_fields, fields)

def get_stock_financials_spider(
        market: str,
        code: str,
        end_day: str,
        report_type: str = "CWBB",
        limit: int = 12,
) -> pd.DataFrame:
    """Fetch financial statements from Eastmoney spider.

    Args:
        market: Market identifier ('cn', 'hk', 'us'). Note: only 'cn' is
            currently supported via spider.
        code: Stock code.
        end_day: The end date for the last report period.
        report_type: Report type identifier. Options: 'CWBB' (Consolidated
            Financial Statements, default), 'LRB' (Income Statement),
            'ZCFZB' (Balance Sheet), 'XJLLB' (Cash Flow Statement),
            'YJBB' (Performance Report).
        limit: Number of latest reports to fetch. Default is 12.

    Returns:
        pd.DataFrame: Standardized financial data.
    """
    key = report_type.upper()
    report_info = EASYMONEY_FINANCIALS_MAPPING.get(key, EASYMONEY_FINANCIALS_MAPPING['CWBB'])
    output_cols = report_info.get('output_cols', ['REPORT_DATE', 'SECURITY_CODE'])

    if market in ("hk", "us"):
        logger.warning(f"Data for market '{market}' is not yet implemented via Spider. Returning empty DataFrame.")
        return pd.DataFrame()
    elif market == "cn":
        logger.info(f"Fetching financials data for {market}:{code}, end_day: {end_day}, type: {report_type}")
        secid = get_secid_of_eastmoney(market, code)

        # This API typically returns the last N report periods
        def make_financials_url() -> str:
            ts = int(time.time() * 1000)

            report_name = report_info['report_name']
            sort_fill = report_info['sort_fill']
            columns = report_info['columns']

            filter_string = (
                f"(SECURITY_CODE=\"{code}\")"
            )

            return (
                f"https://datacenter-web.eastmoney.com/api/data/v1/get"
                f"?reportName={report_name}"  
                f"&columns={columns}"
                f"&filter={filter_string}"
                f"&sortTypes=-1&sortFills={sort_fill}"  
                f"&pageNumber=1&pageSize={limit}"
                f"&_={ts}"
            )

        def parse_financials(json_data):
            """Parse Eastmoney F10 Financial JSON"""
            data = json_data.get("result", {}).get("data", [])
            rows = []
            for item in data:
                row = []
                # Match data fields to our expected order in financial_cols
                for std_col in output_cols:
                    if std_col in item:
                        value = item.get(std_col, "")
                    else:
                        value = item.get(std_col, 0.0)
                    row.append(value)
                rows.append(row)
            return rows

        # Return the structured data using the general crawler
        return crawl_structured_data(make_financials_url, parse_financials, output_cols, datasource="easymoney")


def get_stock_profile_spider(
        market: str,
        code: str,
) -> pd.DataFrame:
    """Fetch stock company profile from Eastmoney spider.

    Args:
        market: Market identifier ('cn', 'hk', 'us').
        code: Stock code.

    Returns:
        pd.DataFrame: Company profile data (CODE, NAME, INDUSTRY,
            MAIN_BUSINESS, LISTING_DATE).

    Raises:
        ValueError: If market is unknown.
    """
    if market == "hk":
        full_code =f"{code}.HK"
    elif market == "cn":
        full_code = f"SH{code}" if code.startswith(('6', '9')) else f"SZ{code}"
    elif market == "us":
        full_code = f"{code}.O"
    else:
        logger.error(f"Unknown market '{market}'")
        raise ValueError(f"Invalid market '{market}'")

    logger.info(f"Fetching profile data for {market}:{code}")
    # --- Part 1 ---
    def make_url_basic() -> str:
        if market == "cn":
            return f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code={full_code}&type=web"
        if market == "hk":
            base_url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
            params = [
                f"reportName=RPT_HKF10_INFO_ORGPROFILE;RPT_HKF10_INFO_SECURITYINFO",
                f"columns=SECUCODE,SECURITY_CODE,ORG_NAME,ORG_EN_ABBR,BELONG_INDUSTRY,FOUND_DATE,CHAIRMAN,SECRETARY,ACCOUNT_FIRM,REG_ADDRESS,ADDRESS,YEAR_SETTLE_DAY,EMP_NUM,ORG_TEL,ORG_FAX,ORG_EMAIL,ORG_WEB,ORG_PROFILE,REG_PLACE,@SECUCODE;@SECUCODE,LISTING_DATE",
                f"quoteColumns=",
                f"filter=(SECUCODE=\"{full_code}\")",
                f"pageNumber=1",
                f"pageSize=200",
                f"sortTypes=",
                f"sortColumns=",
                f"source=F10",
                f"client=PC",
                f"v=04949759694385859"
            ]
            query_string = "&".join(params)
            full_url = f"{base_url}?{query_string}"
            return full_url
        if market == "us":
            base_url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
            params = [
                f"reportName=RPT_USF10_INFO_SECURITYINFO;RPT_USF10_INFO_ORGPROFILE",
                f"columns=SECUCODE,SECURITY_CODE,SECURITY_TYPE,LISTING_DATE,TRADE_MARKET,ISSUE_PRICE,ISSUE_NUM,@SECUCODE;@SECUCODE,ORG_NAME,ORG_EN_ABBR,BELONG_INDUSTRY,FOUND_DATE,CHAIRMAN,ADDRESS,ORG_WEB,ORG_PROFILE",
                f"quoteColumns=",
                f"filter=(SECUCODE=\"{full_code}\")",
                f"pageNumber=1",
                f"pageSize=200",
                f"sortTypes=",
                f"sortColumns=",
                f"source=SECURITIES",
                f"client=PC",
                f"v=040479816075673425"
            ]
            query_string = "&".join(params)
            full_url = f"{base_url}?{query_string}"
            return full_url

    basic_cols = ['CODE', 'NAME', 'LISTING_DATE', 'MAIN_BUSINESS', 'INDUSTRY']

    def parse_basic(json_data):
        if market == "cn":
            info = json_data.get('jbzl', {})[0]
            data = json_data.get('fxxg', {})[0]
            if not info:
                return []
            row = [
                info.get('SECUCODE', full_code),
                info.get('ORG_NAME'),
                data.get('LISTING_DATE')[:10],
                info.get('BUSINESS_SCOPE'),
                info.get('EM2016'),
            ]
            return [row]
        elif market == "hk":
            data = json_data.get('result', {}).get('data', [])[0]
            if not data:
                return []
            row = [
                data.get('SECUCODE', full_code),
                data.get('ORG_NAME'),
                data.get('LISTING_DATE')[:10],
                data.get('ORG_PROFILE'),
                data.get('BELONG_INDUSTRY'),
            ]
            return [row]
        elif market == "us":
            data = json_data.get('result', {}).get('data', [])[0]
            if not data:
                return []
            row = [
                data.get('SECUCODE', full_code),
                data.get('ORG_EN_ABBR'),
                data.get('LISTING_DATE')[:10],
                data.get('ORG_PROFILE'),
                data.get('BELONG_INDUSTRY'),
            ]
            return [row]
    df_basic = crawl_structured_data(make_url_basic, parse_basic, basic_cols, "easymoney_basic")

    # return an empty DataFrame if fail to get basic
    if df_basic.empty:
        logger.warning(f"Failed to fetch basic data for {code}, returning empty DataFrame.")
        print(make_url_basic())
        return pd.DataFrame()

    # Ensure the final cols are right
    final_cols = ['CODE', 'NAME', 'INDUSTRY', 'MAIN_BUSINESS', 'LISTING_DATE']
    return df_basic.reindex(columns=final_cols).fillna('')

def get_stock_factors_spider(
    market: str,
    code: str,
    trade_date: str,
) -> pd.DataFrame:
    """Fetch stock fundamental factors from Eastmoney spider.

    Args:
        market: Market identifier ('cn', 'hk', 'us'). Note: only 'cn' is
            currently supported via spider.
        code: Stock code.
        trade_date: Date for the factor snapshot in "YYYYMMDD" format.

    Returns:
        pd.DataFrame: Factor data (PE_TTM, PE_LAR, PB_MRQ, PEG_CAR,
            PS_TTM, PCF_OCF_TTM, PCF_OCF_LAR).
    """
    date = time.strftime("%Y-%m-%d", time.strptime(trade_date, "%Y%m%d"))
    if market != "cn":
        logger.warning(f"Unsupported market {market}, returning empty DataFrame.")
        return pd.DataFrame()

    def make_factors_url() -> str:
        base_url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        params = [
            f"sortColumns=SECURITY_CODE",
            f"sortTypes=1",
            f"reportName=RPT_VALUEANALYSIS_DET",
            f"columns=ALL",
            f"quoteColumns=",
            f"source=WEB",
            f"client=WEB",
            f"filter=(TRADE_DATE%3D%27{date}%27)((SECURITY_CODE%3D\"{code}\"))"
        ]
        query_string = "&".join(params)
        full_url = f"{base_url}?{query_string}"
        return full_url
    factor_cols = ['TRADE_DATE', 'SECURITY_CODE', 'PE_TTM', 'PE_LAR', 'PB_MRQ', 'PEG_CAR', 'PS_TTM', 'PCF_OCF_TTM', 'PCF_OCF_LAR']

    def parse_factors(json_data):
        """Parse K-line API response to get factors for a single day"""
        datas = json_data.get('result', {}).get('data', [])
        data = {}
        for item in datas:
            if item["SECURITY_CODE"] == code:
                data = item
        if not data:
            return []
        row = [
            trade_date,
            code,
            data.get('PE_TTM'),
            data.get('PE_LAR'),
            data.get('PB_MRQ'),
            data.get('PEG_CAR'),
            data.get('PS_TTM'),
            data.get('PCF_OCF_TTM'),
            data.get('PCF_OCF_LAR'),
        ]
        return [row]


    # Return the structured data using the general crawler
    return crawl_structured_data(make_factors_url, parse_factors, factor_cols, datasource="easymoney")


# ======================================================================
# Async spider functions (direct awaitable versions)
# ======================================================================


async def async_get_stock_history_spider(
    market: str,
    code: str,
    start: str,
    end: str,
    klt: int = 101,
    fqt: int = 1,
) -> pd.DataFrame:
    """Async version: fetch historical K-line data via Eastmoney spider."""
    logger.info("Starting async history fetch by spider: %s:%s", market, code)
    secid = get_secid_of_eastmoney(market, code)

    def make_url(beg: str, end_: str) -> str:
        ts = int(time.time() * 1000)
        return (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            f"&ut=fa5fd1943c7b386f1734de82599f7dc"
            f"&fields1=f1,f2,f3,f4,f5,f6"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            f"&klt={klt}&fqt={fqt}&beg={beg}&end={end_}&lmt=10000&_={ts}"
        )

    def parse_kline(json_data):
        klines = json_data.get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            parts = line.split(",")
            row_dict = {}
            for i, fcode in enumerate(_KLINE_FIELD_CODES):
                if i < len(parts):
                    standard_name = EASTMONEY_KLINE_MAPPING.get(fcode, fcode)
                    row_dict[standard_name] = parts[i]
            rows.append([row_dict.get(col, "") for col in _KLINE_STANDARD_ORDER])
        return rows

    return await _async_crawl_kline_segments(start, end, make_url, parse_kline)


async def async_get_stock_realtime_spider(
    market: str,
    code: Union[str, list[str]],
    fields: Union[str, list[str]] = None,
) -> pd.DataFrame:
    """Async version: fetch real-time stock data from Eastmoney spider."""
    logger.info("Starting async real-time data fetch from spider")
    if isinstance(code, str):
        code = [code]
    if isinstance(fields, str):
        fields = [fields]

    if not code:
        raise ValueError("Code(s) can't be none.")
    if not fields:
        fields = REALTIME_STANDARD_FIELDS
    if "code" not in fields:
        fields.insert(0, "code")
    if "name" not in fields:
        fields.insert(1, "name")
    if "datetime" not in fields:
        fields.insert(2, "datetime")

    url_fields = map_fields_of_eastmoney(fields)

    def get_fields_number(field: str) -> int:
        return int(field[1:])
    url_fields.sort(key=get_fields_number)

    secids = []
    for percode in code:
        persecid = get_secid_of_eastmoney(market, percode)
        secids.append(persecid)

    def make_realtime_url() -> str:
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
        realtime_data = json_data.get("data", {}).get("diff", [])
        result = []
        for single_data in realtime_data:
            rows = [v for v in single_data.values()]
            current_date = datetime.now().strftime("%Y%m%d %H:%M")
            rows.append(current_date)
            result.append(rows)
        return result

    return await _async_crawl_realtime_data(
        make_realtime_url, parse_realtime_data, url_fields, fields
    )


async def async_get_stock_profile_spider(
        market: str,
        code: str,
) -> pd.DataFrame:
    """Async version: fetch stock company profile from Eastmoney spider."""
    if market == "hk":
        full_code = f"{code}.HK"
    elif market == "cn":
        full_code = f"SH{code}" if code.startswith(('6', '9')) else f"SZ{code}"
    elif market == "us":
        full_code = f"{code}.O"
    else:
        raise ValueError(f"Invalid market '{market}'")

    logger.info("Fetching profile data for %s:%s", market, code)

    def make_url_basic() -> str:
        if market == "cn":
            return f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code={full_code}&type=web"
        if market == "hk":
            params = [
                f"reportName=RPT_HKF10_INFO_ORGPROFILE;RPT_HKF10_INFO_SECURITYINFO",
                f"columns=SECUCODE,SECURITY_CODE,ORG_NAME,ORG_EN_ABBR,BELONG_INDUSTRY,FOUND_DATE,CHAIRMAN,SECRETARY,ACCOUNT_FIRM,REG_ADDRESS,ADDRESS,YEAR_SETTLE_DAY,EMP_NUM,ORG_TEL,ORG_FAX,ORG_EMAIL,ORG_WEB,ORG_PROFILE,REG_PLACE,@SECUCODE;@SECUCODE,LISTING_DATE",
                f"filter=(SECUCODE=\"{full_code}\")",
                f"pageNumber=1", f"pageSize=200",
                f"source=F10", f"client=PC",
            ]
            return f"https://datacenter.eastmoney.com/securities/api/data/v1/get?{'&'.join(params)}"
        if market == "us":
            params = [
                f"reportName=RPT_USF10_INFO_SECURITYINFO;RPT_USF10_INFO_ORGPROFILE",
                f"columns=SECUCODE,SECURITY_CODE,SECURITY_TYPE,LISTING_DATE,TRADE_MARKET,ISSUE_PRICE,ISSUE_NUM,@SECUCODE;@SECUCODE,ORG_NAME,ORG_EN_ABBR,BELONG_INDUSTRY,FOUND_DATE,CHAIRMAN,ADDRESS,ORG_WEB,ORG_PROFILE",
                f"filter=(SECUCODE=\"{full_code}\")",
                f"pageNumber=1", f"pageSize=200",
                f"source=SECURITIES", f"client=PC",
            ]
            return f"https://datacenter.eastmoney.com/securities/api/data/v1/get?{'&'.join(params)}"
        return ""

    basic_cols = ['CODE', 'NAME', 'LISTING_DATE', 'MAIN_BUSINESS', 'INDUSTRY']

    def parse_basic(json_data):
        if not isinstance(json_data, dict):
            return []
        if market == "cn":
            jbzl = json_data.get('jbzl')
            if not isinstance(jbzl, list) or not jbzl:
                return []
            info = jbzl[0]
            fxxg = json_data.get('fxxg')
            if not isinstance(fxxg, list) or not fxxg:
                return []
            data = fxxg[0]
            return [[
                info.get('SECUCODE', full_code),
                info.get('ORG_NAME'),
                data.get('LISTING_DATE', '')[:10],
                info.get('BUSINESS_SCOPE'),
                info.get('EM2016'),
            ]]
        elif market == "hk":
            result = json_data.get('result')
            datas = result.get('data', []) if isinstance(result, dict) else []
            if not datas or not isinstance(datas[0], dict):
                return []
            data = datas[0]
            return [[
                data.get('SECUCODE', full_code),
                data.get('ORG_NAME'),
                data.get('LISTING_DATE', '')[:10],
                data.get('ORG_PROFILE'),
                data.get('BELONG_INDUSTRY'),
            ]]
        elif market == "us":
            result = json_data.get('result')
            datas = result.get('data', []) if isinstance(result, dict) else []
            if not datas or not isinstance(datas[0], dict):
                return []
            data = datas[0]
            return [[
                data.get('SECUCODE', full_code),
                data.get('ORG_EN_ABBR'),
                data.get('LISTING_DATE', '')[:10],
                data.get('ORG_PROFILE'),
                data.get('BELONG_INDUSTRY'),
            ]]
        return []

    df = await _async_crawl_structured_data(
        make_url_basic, parse_basic, basic_cols, "easymoney_basic"
    )

    if df.empty:
        logger.warning("Failed to fetch basic data for %s, returning empty DataFrame.", code)
        return pd.DataFrame()

    final_cols = ['CODE', 'NAME', 'INDUSTRY', 'MAIN_BUSINESS', 'LISTING_DATE']
    return df.reindex(columns=final_cols).fillna('')


async def async_get_stock_factors_spider(
    market: str,
    code: str,
    trade_date: str,
) -> pd.DataFrame:
    """Async version: fetch stock fundamental factors from Eastmoney spider."""
    date = time.strftime("%Y-%m-%d", time.strptime(trade_date, "%Y%m%d"))
    if market != "cn":
        logger.warning("Unsupported market %s, returning empty DataFrame.", market)
        return pd.DataFrame()

    def make_factors_url() -> str:
        params = [
            f"sortColumns=SECURITY_CODE",
            f"sortTypes=1",
            f"reportName=RPT_VALUEANALYSIS_DET",
            f"columns=ALL",
            f"filter=(TRADE_DATE%3D%27{date}%27)((SECURITY_CODE%3D\"{code}\"))"
        ]
        return f"https://datacenter-web.eastmoney.com/api/data/v1/get?{'&'.join(params)}"

    factor_cols = [
        'TRADE_DATE', 'SECURITY_CODE', 'PE_TTM', 'PE_LAR',
        'PB_MRQ', 'PEG_CAR', 'PS_TTM', 'PCF_OCF_TTM', 'PCF_OCF_LAR'
    ]

    def parse_factors(json_data):
        if not isinstance(json_data, dict):
            return []
        result = json_data.get('result')
        datas = result.get('data', []) if isinstance(result, dict) else []
        for item in datas:
            if isinstance(item, dict) and item.get("SECURITY_CODE") == code:
                return [[
                    trade_date, code,
                    item.get('PE_TTM'), item.get('PE_LAR'),
                    item.get('PB_MRQ'), item.get('PEG_CAR'),
                    item.get('PS_TTM'), item.get('PCF_OCF_TTM'),
                    item.get('PCF_OCF_LAR'),
                ]]
        return []

    return await _async_crawl_structured_data(
        make_factors_url, parse_factors, factor_cols, datasource="easymoney"
    )


# ======================================================================
# DataSource plugin wrapper
# ======================================================================


class SpiderDataSource(DataSource):
    """DataSource wrapper for the built-in Eastmoney spider engine.

    Supports all five function types (history, realtime, financials,
    profile, factors) and provides native async implementations for
    all four async methods.
    """

    name = "spider"
    supported_types = {"history", "realtime", "financials", "profile", "factors"}
    supports_batch_realtime = True

    # -- history --

    def get_history(
        self,
        market: str,
        code: str,
        start: str,
        end: str,
        klt: int = 101,
        fqt: int = 1,
        **kwargs,
    ) -> pd.DataFrame:
        return get_stock_history_spider(market, code, start, end, klt, fqt)

    async def get_history_async(
        self,
        market: str,
        code: str,
        start: str,
        end: str,
        klt: int = 101,
        fqt: int = 1,
        **kwargs,
    ) -> pd.DataFrame:
        return await async_get_stock_history_spider(market, code, start, end, klt, fqt)

    # -- realtime --

    def get_realtime(
        self,
        market: str,
        code,
        fields=None,
        **kwargs,
    ) -> pd.DataFrame:
        return get_stock_realtime_spider(market, code, fields)

    async def get_realtime_async(
        self,
        market: str,
        code,
        fields=None,
        **kwargs,
    ) -> pd.DataFrame:
        return await async_get_stock_realtime_spider(market, code, fields)

    # -- financials --

    def get_financials(
        self,
        market: str,
        code: str,
        end_day: str,
        report_type: str = "CWBB",
        limit: int = 12,
        **kwargs,
    ) -> pd.DataFrame:
        return get_stock_financials_spider(market, code, end_day, report_type, limit)

    # -- profile --

    def get_profile(
        self,
        market: str,
        code: str,
        **kwargs,
    ) -> pd.DataFrame:
        return get_stock_profile_spider(market, code)

    async def get_profile_async(
        self,
        market: str,
        code: str,
        **kwargs,
    ) -> pd.DataFrame:
        return await async_get_stock_profile_spider(market, code)

    # -- factors --

    def get_factors(
        self,
        market: str,
        code: str,
        trade_date: str,
        **kwargs,
    ) -> pd.DataFrame:
        return get_stock_factors_spider(market, code, trade_date)

    async def get_factors_async(
        self,
        market: str,
        code: str,
        trade_date: str,
        **kwargs,
    ) -> pd.DataFrame:
        return await async_get_stock_factors_spider(market, code, trade_date)
