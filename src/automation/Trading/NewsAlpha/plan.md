news alpha — filter stock news to watchlist relevance

trigger: rss.poll hourly + webhook for breaking news

nodes:
- ingest news/articles per watchlist symbol (paywalled via browser.stagehand extract if needed)
- llm.jev model=laya -> Noul relevant?, Score impact 1-5, Choice long|short|neutral
- filter: only relevant and impact>=3
- deliver: digest to Slack/email + feature extraction for forecasting model

n8n shape: trigger.rss/webhook -> browser.stagehand(extract) -> llm.jev.noul/score/choice -> if -> deliver -> store
cheap laya enables 1000s articles/day at <35ms each
