price monitor — sheets-backed stock price alerts with cooldown

trigger: cron every 1m (24/7)

nodes:
- sheets.read watchlist (symbol, upper_limit, lower_limit, direction: above|below|both, cooldown_minutes)
- fetch live price via CoinGecko API (free tier) per symbol
- llm.jev model=laya -> Noul breach?, Score severity 1-5
- check cooldown to avoid duplicate alerts
- deliver: Email, Telegram, Discord + sheets.write last_alert_price, last_alert_time

n8n shape: trigger.cron -> sheets.read -> fetch -> llm.jev.noul -> if breach -> deliver -> store
note: supports stocks via Alpha Vantage same shape
