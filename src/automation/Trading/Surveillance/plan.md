trade surveillance — pump-and-dump / spoofing / off-market detection

trigger: cron daily

nodes:
- ingest trade/order/execution/quote files + email corpus
- risk indicators: bulk orders, high cancel ratio, unusual quote movement, pump/dump
- llm.jev model=laya -> Choice pump|spoof|off-market|front-run|clean, Score risk 1-5, Noul escalate?
- combine with trader alert history
- deliver: daily score + route high-risk to human review if confidence<0.6

n8n shape: trigger.cron -> ingest -> llm.jev.choice/score/noul -> store -> if -> deliver
stagehand optional: extract broker dashboard when no API
