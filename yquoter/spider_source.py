# yquoter/spider_source.py
import pandas as pd
import time
from yquoter.utils import *
from typing import Union, List
from yquoter.spider_core import *
from yquoter.config import EASTMONEY_REALTIME_MAPPING, EASYMONEY_FINANCIALS_MAPPING

# Eastmoney field mapping: User-friendly name -> Eastmoney internal field code
dict_of_eastmoney = {v: k for k, v in EASTMONEY_REALTIME_MAPPING.items()}
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
        # Map parsed parts to standard columns: [date, open, high, low, close, vol, amount, change%, turnover%, change, amplitude%]
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


def get_xueqiu_symbol(market: str, code: str) -> str:
    """
    Generates the Xueqiu-specific 'symbol' based on the market and stock code.

    Args:
        market: Market identifier ('cn', 'hk', 'us').
        code: Raw stock code.

    Returns:
        Xueqiu-standard symbol string (e.g., 'SH600000', 'HK00700', 'BABA').

    Raises:
        CodeFormatError: If the A-share code format is unrecognized.
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
    # if "name" not in fields:
    #    fields.insert(1, "name")

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
    return crawl_realtime_data(make_realtime_url, parse_realtime_data, url_fields, fields)

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
        full_code = f"{code}.SH" if code.startswith(('6', '9')) else f"{code}.SZ"

        logger.info(f"Fetching profile data for {market}:{code}")
        secid = get_secid_of_eastmoney(market, code)

        # --- Part 1 ---
        def make_url_basic() -> str:
            return f"https://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/Page/GetBasicData?code={full_code}"

        basic_cols = ['CODE', 'NAME', 'LISTING_DATE']

        def parse_basic(json_data):
            info = json_data.get('jbzl', {})
            if not info:
                return []
            row = [
                info.get('SECUCODE', full_code),
                info.get('SECURITY_NAME_ABBR', ''),
                info.get('LISTING_DATE', '').split('T')[0]
            ]
            return [row]

        df_basic = crawl_structured_data(make_url_basic, parse_basic, basic_cols, "easymoney_basic")

        # return an empty DataFrame if fail to get basic
        if df_basic.empty:
            logger.warning(f"Failed to fetch basic data for {code}, returning empty DataFrame.")
            print(make_url_basic())
            return pd.DataFrame()

        # --- Part 2 ---
        def make_url_business() -> str:
            return f"https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/Api/GetZyYw?stockCode={full_code}"

        business_cols = ['CODE', 'INDUSTRY', 'MAIN_BUSINESS']

        def parse_business(json_data):
            if not json_data or not isinstance(json_data, list):
                return []
            info = json_data[0]
            row = [
                full_code,
                info.get('INDUSTRY', ''),
                info.get('BUSINESS_SCOPE', '')
            ]
            return [row]

        df_business = crawl_structured_data(make_url_business, parse_business, business_cols, "easymoney_business")

        # --- Part 3 ---
        if df_business.empty:
            logger.warning(f"Failed to fetch business data for {code}. Some fields will be empty.")
            final_df = df_basic
            final_df['INDUSTRY'] = ''
            final_df['MAIN_BUSINESS'] = ''
        else:
            # Merge data based on df_basic
            final_df = pd.merge(df_basic, df_business, on='CODE', how='left')

        # Ensure the final cols are right
        final_cols = ['CODE', 'NAME', 'INDUSTRY', 'MAIN_BUSINESS', 'LISTING_DATE']
        return final_df.reindex(columns=final_cols).fillna('')

def get_stock_factors_spider(
        market: str,
        code: str,
        trade_date: str
) -> pd.DataFrame():
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
                f"&klt=101&fqt=1&beg={trade_date}&end={trade_date}&lmt=1&_={int(time.time() * 1000)}"
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
        return crawl_structured_data(make_factors_url, parse_factors, factor_cols, datasource="easymoney")


if __name__ == "__main__":
    df_1 = get_stock_factors_spider(market="cn", code="688256", trade_date="20250312")
    print(df_1)
    df_2 = get_stock_profile_spider(market="cn", code="688256")
    print(df_2)
    df_3 = get_stock_financials_spider("cn", "688256", "20250820", "YJBB")
    print(df_3)