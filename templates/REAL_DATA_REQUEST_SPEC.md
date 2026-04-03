# Futures Research Real Data Request Spec v1

## Goal

This template is for internal data handoff so the technical team can connect real market and fundamental data into the existing futures research workflow.

The current reporting workflow supports:

- single-symbol report generation
- daily report review and scoring
- REST API query
- WebSocket runtime events

To evaluate report quality with real inputs, please provide structured data with:

- clear timestamps
- clear units
- source traceability
- stable identifiers

## Delivery Suggestion

Preferred delivery order:

1. Excel workbook with multiple sheets
2. CSV files with the same sheet names
3. Internal API or database table mapping after field confirmation

## Granularity Rules

Not all data should be 30-minute frequency.

Recommended 30-minute frequency:

- futures intraday quotes
- intraday volume and open interest snapshots
- basis snapshots if internally available
- key market microstructure fields

Recommended daily frequency:

- daily futures close / settle summary
- spot prices
- warehouse receipts
- exchange inventory
- top member positions

Recommended weekly or monthly frequency:

- supply-demand balance
- operating rates
- import / export
- USDA and other institutional balance-sheet data

Recommended event-driven frequency:

- policy news
- macro headlines
- industry news
- weather disruptions
- logistics disruptions

## Required Global Fields

Every row should include these fields whenever applicable:

| field | required | description |
|---|---|---|
| as_of_date | yes | business date |
| as_of_time | conditional | timestamp for intraday data |
| variety_code | yes | product code, e.g. CF |
| variety_name | yes | product name, e.g. 棉花 |
| contract | conditional | contract code, e.g. CF2609 |
| metric_code | yes | stable technical metric identifier |
| metric_name | yes | business-friendly metric name |
| value | yes | numeric or text value |
| unit | yes | unit for the metric |
| source_name | yes | source system or institution |
| source_time | yes | source publish or snapshot time |
| source_url | recommended | original URL or system path |
| frequency | recommended | 30m / daily / weekly / monthly / event |
| remark | recommended |口径说明、异常说明、补充备注 |

## Sheet Design

### 1. README

Workbook usage notes and the meaning of each sheet.

### 2. futures_quotes_30m

Purpose:

- intraday market replay
- short-term momentum and sentiment description
- intraday price range reference

Suggested fields:

- as_of_date
- as_of_time
- variety_code
- variety_name
- contract
- exchange
- open
- high
- low
- close
- last_price
- settle_est
- change
- change_pct
- volume
- turnover
- open_interest
- bid_price_1
- ask_price_1
- source_name
- source_time
- source_url
- remark

### 3. futures_quotes_daily

Purpose:

- daily report main market recap
- historical trend comparison

Suggested fields:

- as_of_date
- variety_code
- variety_name
- contract
- exchange
- open
- high
- low
- close
- settle
- prev_settle
- change
- change_pct
- volume
- turnover
- open_interest
- delivery_month
- is_main_contract
- source_name
- source_time
- source_url
- remark

### 4. spot_basis_daily

Purpose:

- basis analysis
- spot/futures linkage

Suggested fields:

- as_of_date
- variety_code
- variety_name
- spot_region
- spot_grade
- spot_price
- spot_unit
- futures_contract
- futures_price
- futures_unit
- basis
- basis_rate_pct
- source_name
- source_time
- source_url
- remark

### 5. inventory_receipts_daily

Purpose:

- inventory and receipt analysis
- delivery pressure analysis

Suggested fields:

- as_of_date
- variety_code
- variety_name
- inventory_type
- region
- warehouse
- value
- unit
- change_vs_prev
- change_vs_prev_pct
- source_name
- source_time
- source_url
- remark

### 6. member_positions_daily

Purpose:

- top member long/short structure
- capital sentiment clues

Suggested fields:

- as_of_date
- variety_code
- variety_name
- contract
- ranking_type
- member_name
- position_value
- change_vs_prev
- source_name
- source_time
- source_url
- remark

ranking_type examples:

- long
- short
- volume

### 7. industry_fundamentals_daily

Purpose:

- downstream demand
- industrial chain health

Suggested fields:

- as_of_date
- variety_code
- variety_name
- indicator_code
- indicator_name
- region
- value
- unit
- frequency
- source_name
- source_time
- source_url
- remark

Examples:

- spinning_operating_rate
- yarn_price
- yarn_cotton_spread
- ginning_progress
- industrial_profit

### 8. international_market_daily

Purpose:

- international linkage
- external macro context

Suggested fields:

- as_of_date
- variety_code
- linked_asset_code
- linked_asset_name
- contract_or_symbol
- close
- change
- change_pct
- unit
- source_name
- source_time
- source_url
- remark

Examples:

- ICE Cotton
- DXY
- Brent
- USD/CNY

### 9. supply_demand_weekly_monthly

Purpose:

- medium-term supply-demand balance
- report-level fundamental judgment

Suggested fields:

- as_of_date
- period_label
- variety_code
- variety_name
- indicator_code
- indicator_name
- value
- unit
- frequency
- source_name
- source_time
- source_url
- remark

Examples:

- production
- imports
- consumption
- ending_stocks
- export_sales

### 10. events_news

Purpose:

- recent key information
- risk reminders

Suggested fields:

- event_date
- event_time
- variety_code
- variety_name
- event_type
- title
- summary
- impact_bias
- importance
- source_name
- source_time
- source_url
- remark

event_type examples:

- policy
- macro
- industry
- weather
- international
- logistics

impact_bias examples:

- bullish
- neutral
- bearish

importance examples:

- high
- medium
- low

### 11. source_dictionary

Purpose:

- unify source names and source priorities
- simplify downstream confidence scoring

Suggested fields:

- source_name
- source_type
- owner_team
- freshness_rule
- trust_level
- access_method
- remark

### 12. data_dictionary

Purpose:

- metric governance
- mapping to code-side field standards

Suggested fields:

- sheet_name
- metric_code
- metric_name
- definition
- unit
- frequency
- nullable
- example_value
- remark

## CF Cotton Minimum Required Metrics

Recommended minimum set for quality evaluation:

- intraday futures bars every 30 minutes for main contract
- daily futures close / settle / volume / open interest
- spot price for 3128B and basis
- warehouse receipts and commercial inventory
- top member long/short positions
- spinning operating rate
- yarn price or yarn-cotton spread
- ICE cotton daily market data
- USDA monthly balance-sheet key numbers
- 3 to 10 relevant news or event items per day

## Suggested Technical Workflow

Recommended internal workflow:

1. business team confirms metric list and source ownership
2. technical team fills this workbook with real source mapping
3. technical team outputs CSV or API according to the sheet structure
4. ingestion layer maps each sheet to source adapters
5. report generation runs against real data
6. reviewer score and final report quality are checked against expectations

## Important Notes

- missing values should stay blank, not fake zero
- every quantitative metric should have explicit units
- every data row should be traceable to a real source
- weekly and monthly data must include statistical period description
- 30-minute data should only be used for market behavior, not fabricated fundamentals
