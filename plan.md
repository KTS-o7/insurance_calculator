

# 1) Useful APIs & data sources (quick catalog)

**MFapi (mfapi.in)** — free JSON API for Indian mutual fund schemes and daily NAV history. No auth, updated multiple times daily. Great for scheme NAV history. ([mfapi.in][1])

**AMFI official NAV pages / NAV download** — authoritative source (Association of Mutual Funds in India). AMFI provides daily NAV downloads (text/CSV) and historical NAV interface; more “official” but less API-like (some scraping / periodic downloads needed). Use for verification. ([AMFI India][2])

**Yahoo Finance (via `yfinance`)** — good for ETF tickers (NIFTYBEES.NS, GOLDBEES.NS etc.) and historical prices for ETFs and index-tracking ETFs. Widely used from Python (yfinance library scrapes Yahoo data). Not an official API but practical. ([Yahoo Finance][3])

**Alpha Vantage** — free API key, global equities/ETF time series & indicators with rate limits. Useful for historical price time series; limited for some non-US tickers but works for many ETFs. ([Alpha Vantage][4])

**Twelve Data** — modern freemium market-data API (supports ETFs and historical data). Free tier available; friendly JSON endpoints and SDKs. Good alternative for ETFs and index prices. ([Twelve Data][5])

**NSE / Nifty official historical index data** — NSE provides downloadable historical index (.csv) data and EOD reports (some endpoints require download/subscription for advanced feeds). For bench-marking NIFTY50 use official NiftyIndices/NSE. ([NSE India][6])

**Other community APIs / GitHub projects** — wrappers or datasets that aggregate AMFI/MF data (e.g., mf.captnemo.in or GitHub repos) can be handy for metadata/ISIN lookups. Use carefully and verify. ([India Mutual Funds API][7])

---

# 2) Practical plan — how to build the SIP + allocation + alpha projection tool

1. **Data sources**

   * Use **MFapi** (or AMFI downloads) for mutual fund NAV series (monthly/daily NAV history per scheme). Good for active funds / debt funds.
   * Use **yfinance / Twelve Data / Alpha Vantage** for ETF prices (NIFTYBEES, GOLD ETFs) and for benchmark index series (NIFTY50 total return if available, else use price index).
   * Use **NSE / NiftyIndices** for official index histories if you want daily official index numbers.

2. **Metadata**

   * Build scheme metadata table (scheme name, ISIN, AMC, fund type: equity/debt/hybrid/gold/ETF) using MFapi or CAPTNEMO endpoints.

3. **SIP simulation model**

   * For each month from `start_date` to `today` (or for the historical window you choose), simulate monthly SIP contributions.
   * For funds (mutual fund NAVs): compute number of units bought each SIP = `amount / NAV_on_SIP_date`. For ETFs: use ETF close price similarly.
   * Track daily/monthly portfolio value and total invested.
   * Compute realized returns (XIRR / CAGR) for portfolio and for the chosen benchmark (e.g., NIFTY50 or Nifty Total Return index). Alpha = portfolio return − benchmark return (over same period).
   * Optionally compute rolling alpha / Sharpe / downside deviation to help user decide allocation.

4. **Allocation rules / alpha generation**

   * Let user specify allocation rules across wealth classes (e.g., Core: NIFTY ETF 50%, Satellite: Large-cap active 20%, Debt: 20%, Gold ETF: 10%). Or provide presets.
   * Run historical backtest of those rules (SIP input -> monthly amounts based on allocation -> simulated historic performance) to produce expected annualized return and historical alpha vs benchmark.
   * You can then recommend adjustments: e.g., shifting more to satellite if goal is higher alpha but with higher volatility.

5. **Python stack**

   * `requests`, `pandas`, `numpy`, `scipy` (for xirr), `yfinance` (or `twelvedata` / `alpha_vantage` SDKs), `matplotlib` for plots (or export csv). For production use, cache NAVs and respect provider rate limits.



# References / source links used

* MFapi (free Indian mutual fund API). ([mfapi.in][1])
* AMFI official NAV / NAV download pages. ([AMFI India][2])
* Yahoo Finance (ETF tickers, historical prices). ([Yahoo Finance][3])
* Alpha Vantage (free API for equities/ETFs). ([Alpha Vantage][4])
* Twelve Data (freemium market-data API supporting ETFs). ([Twelve Data][5])
* NSE / Nifty historical data / NiftyIndices. ([NSE India][6])

---
[1]: https://www.mfapi.in/?utm_source=chatgpt.com "MFapi.in - Free India Mutual Fund API"
[2]: https://www.amfiindia.com/net-asset-value?utm_source=chatgpt.com "Net Asset Value"
[3]: https://finance.yahoo.com/quote/NIFTYBEES.NS/history/?utm_source=chatgpt.com "Nippon India ETF Nifty 50 BeES (NIFTYBEES.NS)"
[4]: https://www.alphavantage.co/?utm_source=chatgpt.com "Alpha Vantage: Free Stock APIs in JSON & Excel"
[5]: https://twelvedata.com/?utm_source=chatgpt.com "Twelve Data | Stock, Forex, and Crypto Market Data APIs"
[6]: https://www.nseindia.com/reports-indices-historical-index-data?utm_source=chatgpt.com "Historical Index Data"
[7]: https://mf.captnemo.in/?utm_source=chatgpt.com "India Mutual Funds API | Get information about Indian Mutual ..."
[8]: https://www.mfapi.in/docs/?utm_source=chatgpt.com "Mutual Fund API Documentation - MFapi.in"
[9]: https://www.niftyindices.com/reports/historical-data?utm_source=chatgpt.com "Historical Data Reports"
[10]: https://finance.yahoo.com/quote/NIFTYBEES.NS/?utm_source=chatgpt.com "Nippon India ETF Nifty 50 BeES (NIFTYBEES.NS)"
