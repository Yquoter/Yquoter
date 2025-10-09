# 📚 Yquoter Parameters Reference

This document provides detailed definitions for the common and specialized parameters used across the primary data acquisition functions in the Yquoter library.

---

### 1. Market Identifier (`market`)
- **Type**: `str` 
- **Description**: Specifies the target stock market to fetch data from.  
- **Supported Values**:

| Value | Corresponding Market       | 
|-------|----------------------------|
| `'cn'`| A-shares (Shanghai/Shenzhen) |
| `'hk'`| H-shares         |
| `'us'`| US stocks (NYSE/NASDAQ)    |


### 2. Stock Code (`code`)
- **Type**:  
  - Single code: `str` (e.g., `'600000'`)  
  - Multiple codes: `list[str]` or `str` (e.g., `['600000', '000858']`)  
- **Description**: Unique identifier of the target stock(s), **without market suffixes**.  
- **Format**:  
  - A-shares: 6 digits (e.g., `'600000'`, `'000858'`)  
  - H-shares: 5 digits (e.g., `'00700'`, `'02318'`)  
  - US stocks: Ticker symbol (e.g., `'AAPL'`, `'MSFT'`, `'TSLA'`)  

### 3. Date Range (`start`/`end`)
- **Type**: `str`  
- **Description**: Defines the time range for data retrieval (used for historical data, e.g., `get_stock_history`).  
- **Format**: `'YYYYMMDD'` (e.g.  `'20251008'`,`'2023-01-08'` (auto-parsed to `'20230108'` internally))
- **Default Behavior**:  
  - If `start` is not provided: Automatically uses the past 30 days.  
  - If `end` is not provided: Automatically uses the current date.  

### 4. Data Frequency (`klt`)
- **Description**: Controls the time granularity of the returned data (e.g., daily bars, 1-minute bars).  
- **Type**:  
  - Human-readable type: `str` (e.g.,`d`,`w`,`m`)
  - Low-level type: `int` (e.g.,`101`,`102`,`103`)
- **Supported values**:  
  - 101: daily, Daily, day, Day, d, D, 1day, 1Day, 1d, 1D
  - 102: weekly, Weekly, week, Week, w, W, 1week, 1Week, 1w, 1W
  - 103: monthly, Monthly, month, Month, m, M, 1month, 1Month, 1m, 1M
  - 104: half_year, Half_year, Half_Year, HALF_YEAR, halfyear, Halfyear, HalfYear, HALFYEAR
  - 105: yearly, Yearly, year, Year, y, Y, 1year, 1Year, 1y, 1Y

### 5. Data Source (`source`)
- **Type**: `Optional[str]` 
- **Description**: Specifies the underlying data source to fetch data from (supports multi-source fallback for stability).  
- **Supported Values**:  
    
    | Value       | Description                               | Prerequisite                                                                                                            |
    |-------------|-------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
    | `'spider'`  | Internal web scraping                     | No prerequisites (default fallback source).                                                                             |
    | `'tushare'` | TuShare API (professional financial data) | Requires prior initialization with `yquoter.init_tushare(token)` (token obtained from [TuShare](https://tushare.pro/)). |
    | othersource | your own spider or your own database      | Requires prior initialization with `yquoter.register_source(source_name: str, func_type: str, func: Callable = None)` . |

- **Default Behavior**: Uses the global `_DEFAULT_SOURCE` (usually `'spider'`) if not specified. Throws `DataSourceError` for unknown sources.

### 6. Data Field Set (`fields`)
- **Type**:
  - For history data: `str`(eg. `"basic"`,`"full"`)
  - For realtime data: `Union[str,list]` (eg. `"code"`,`["code", "name"]`)
- **Description**: Defines the scope of data fields to return.  
- **Common Values**:  

  - For history data:
    
    | Value    | Description                  | Typical Fields Included                                                      |
    |----------|------------------------------|-------------------------------------------------------------------------------|
    | `'basic'`| Core essential fields (default) | Open price, close price, high price, low price, trading volume, turnover.    |
    | `'full'` | All available fields (varies by source) | Extends `'basic'` with fields like pre-market price, post-market price, PE ratio, PB ratio. |

  - For realtime data (for spider):
    
    | Value                                   | Description                                                       |
    |-----------------------------------------|-------------------------------------------------------------------|
    | `latest`                                | Latest Price                                                      |
    | `change%`                               | Change Percentage                                                 |
    | `change`                                | Absolute Change                                                   |
    | `vol`                                   | Trading Volume                                                    |
    | `amount`                                | Trading Amount                                                    |
    | `amplitude`                             | Price Amplitude                                                   |
    | `turnover%`                             | Turnover Percentage                                               |
    | `pe_dynamic`                            | Dynamic Price-to-Earnings Ratio                                   |
    | `vol_ratio`                             | Volume Ratio                                                      |
    | `5min_change%`                          | 5-Minute Change Percentage                                        |
    | `code`                                  | Stock Code                                                        |
    | `market`                                | Trading Market                                                    |
    | `name`                                  | Stock Name                                                        |
    | `high`                                  | Daily High Price                                                  |
    | `low`                                   | Daily Low Price                                                   |
    | `open`                                  | Daily Opening Price                                               |
    | `pre_close`                             | Previous Closing Price                                            |
    | `total_market_value`                    | Total Market Capitalization                                       |
    | `circulating_market_value`              | Circulating Market Capitalization                                 |
    | `price_rise_speed`                      | Price Rise Speed                                                  |
    | `pb`                                    | Price-to-Book Ratio                                               |
    | `60day_change%`                         | 60-Day Change Percentage                                          |
    | `ytd_price_change_percent`              | Year-to-Date Price Change Percentage                              |
    | `listing_date`                          | Listing Date                                                      |
    | `pre_settlement_price`                  | Previous Settlement Price                                         |
    | `last_trade_volume`                     | Last Trade Volume                                                 |
    | `spot_exchange_bid_price`               | Spot Exchange Bid Price                                           |
    | `spot_exchange_ask_price`               | Spot Exchange Ask Price                                           |
    | `order_ratio`                           | Order Ratio                                                       |
    | `external_market`                       | External Market Volume                                            |
    | `internal_market`                       | Internal Market Volume                                            |
    | `weighted_roe_latest_qtr`               | Weighted Return on Equity (ROE) of the Latest Quarter             |
    | `total_share_capital`                   | Total Share Capital                                               |
    | `circulating_a_shares_10k`              | Circulating A-Shares (10,000 Shares Unit)                         |
    | `total_revenue_latest_qtr`              | Total Revenue of the Latest Quarter                               |
    | `total_revenue_yoy_latest_qtr`          | Year-over-Year (YoY) Total Revenue Growth of the Latest Quarter   |
    | `total_profit_latest_qtr`               | Total Profit of the Latest Quarter                                |
    | `net_profit_latest_qtr`                 | Net Profit of the Latest Quarter                                  |
    | `net_profit_growth_rate_yoy_latest_qtr` | Year-over-Year (YoY) Net Profit Growth Rate of the Latest Quarter |
    | `undistributed_profit_per_share`        | Undistributed Profit per Share                                    |
    | `gross_profit_margin_latest_qtr`        | Gross Profit Margin of the Latest Quarter                         |
    | `total_assets_latest_qtr`               | Total Assets of the Latest Quarter                                |
    | `debt_ratio`                            | Debt Ratio                                                        |
    | `shareholders_equity`                   | Shareholders' Equity                                              |
    | `main_force_net_inflow_today`           | Main Force Net Inflow Today                                       |
    | `extra_large_order_inflow`              | Extra-Large Order Inflow                                          |
    | `extra_large_order_outflow`             | Extra-Large Order Outflow                                         |
    | `extra_large_order_net_inflow_today`    | Extra-Large Order Net Inflow Today                                |
    | `extra_large_order_net_ratio`           | Extra-Large Order Net Ratio                                       |
    | `large_order_inflow`                    | Large Order Inflow                                                |
    | `large_order_outflow`                   | Large Order Outflow                                               |
    | `large_order_net_inflow_today`          | Large Order Net Inflow Today                                      |
    | `large_order_net_ratio`                 | Large Order Net Ratio                                             |
    | `medium_order_inflow`                   | Medium Order Inflow                                               |
    | `medium_order_outflow`                  | Medium Order Outflow                                              |
    | `medium_order_net_inflow_today`         | Medium Order Net Inflow Today                                     |
    | `medium_order_net_ratio_pct`            | Medium Order Net Ratio Percentage                                 |
    | `small_order_inflow`                    | Small Order Inflow                                                |
    | `small_order_outflow`                   | Small Order Outflow                                               |
    | `small_order_net_inflow_today`          | Small Order Net Inflow Today                                      |
    | `small_order_net_ratio`                 | Small Order Net Ratio                                             |
    | `industry`                              | Industry Category                                                 |
    | `regional_sector`                       | Regional Sector                                                   |
    | `remarks`                               | Remarks                                                           |
    | `number_of_gaining_stocks`              | Number of Gaining Stocks                                          |
    | `number_of_declining_stocks`            | Number of Declining Stocks                                        |
    | `number_of_flat_stocks`                 | Number of Flat Stocks                                             |
    | `eps_1`                                 | Earnings Per Share (EPS) for the Latest Fiscal Year               |
    | `net_asset_per_share`                   | Net Asset Per Share                                               |
    | `pe_ratio_static`                       | Static Price-to-Earnings Ratio                                    |
    | `pe_ratio_ttm`                          | Trailing Twelve Months (TTM) Price-to-Earnings Ratio              |
    | `trading_time`                          | Trading Time                                                      |
    | `sector_leading_stock`                  | Sector Leading Stock                                              |
    | `net_profit`                            | Net Profit                                                        |
    | `ps_ratio_ttm`                          | Trailing Twelve Months (TTM) Price-to-Sales Ratio                 |
    | `pcf_ratio_ttm`                         | Trailing Twelve Months (TTM) Price-to-Cash Flow Ratio             |
    | `total_operating_revenue_ttm`           | Total Operating Revenue for Trailing Twelve Months (TTM)          |
    | `dividend_yield`                        | Dividend Yield                                                    |
    | `industry_sector_constituent_count`     | Industry Sector Constituent Count                                 |
    | `net_assets`                            | Net Assets                                                        |
    | `net_profit_ttm`                        | Net Profit for Trailing Twelve Months (TTM)                       |
    | `5day_main_force_net_amount`            | 5-Day Main Force Net Amount                                       |
    | `5day_extra_large_order_net_amount`     | 5-Day Extra-Large Order Net Amount                                |
    | `5day_large_order_net_amount`           | 5-Day Large Order Net Amount                                      |
    | `5day_medium_order_net_amount`          | 5-Day Medium Order Net Amount                                     |
    | `5day_small_order_net_amount`           | 5-Day Small Order Net Amount                                      |
    | `10day_main_force_net_amount`           | 10-Day Main Force Net Amount                                      |
    | `10day_extra_large_order_net_amount`    | 10-Day Extra-Large Order Net Amount                               |
    | `10day_large_order_net_amount`          | 10-Day Large Order Net Amount                                     |
    | `10day_medium_order_net_amount`         | 10-Day Medium Order Net Amount                                    |
    | `10day_small_order_net_amount`          | 10-Day Small Order Net Amount                                     |
    | `convertible_bond_subscription_code`    | Convertible Bond Subscription Code                                |
    | `convertible_bond_subscription_date`    | Convertible Bond Subscription Date                                |
    | `limit_up_price`                        | Limit Up Price                                                    |
    | `limit_down_price`                      | Limit Down Price                                                  |
    | `average_price`                         | Average Price                                                     |
    | `datetime`                              | Datetime                                                          |
---