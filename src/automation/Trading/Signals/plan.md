trading signals — ai alerts from market data (stock/crypto)

trigger: cron every 5m (configurable 5-30m)

nodes:
- fetch OHLCV parallel for watchlist (CoinGecko, Alpha Vantage, Binance)
  - prepare candles, volume, current price
- technical indicators: RSI, MACD, MA
- llm.jev model=laya (verdict-151m self-host) -> Score confidence 1-5, Choice buy|hold|sell, Noul high-risk?
- filter: only if RSI<30 or MACD crossover and confidence>0.75
- deliver: Slack/email/SMS/webhook + log trace + store signal

n8n shape: trigger.cron -> fetch -> indicators -> llm.jev.score/choice/noul -> if -> deliver
stagehand: none (API only); cheap laya keeps <35ms per symbol
