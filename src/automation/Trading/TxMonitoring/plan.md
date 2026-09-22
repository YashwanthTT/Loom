tx monitoring — aml for trading transactions (layering/structuring)

trigger: webhook from Crypto APIs / Kraken / exchange

nodes:
- ingest transaction + counterparty + history
- llm.jev model=laya -> Choice typology [layering,structuring,smurfing,clean], Score risk 1-5, Noul SAR needed?
- enrich: counterparty verification, doc intelligence, pattern checks
- route: if high risk -> alert SIEM / compliance queue, else auto-disposition
- store audit trail

n8n shape: trigger.webhook -> llm.jev.choice/score/noul -> enrich -> if -> deliver -> store
covers Arva-style tx monitoring for crypto & stock trading flows
