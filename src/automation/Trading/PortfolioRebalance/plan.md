portfolio rebalance — drift check and auto trade

trigger: cron daily 16:00 (post-close) or manual

nodes:
- extract portfolio positions (broker API or browser.stagehand extract if no API)
- llm.jev model=laya -> Score drift 1-5, Choice rebalance|hold, Noul tax-impact?
- if rebalance and drift>threshold -> browser.stagehand act: place orders (or API execute)
- log execution, update sheet, deliver summary

n8n shape: trigger.cron -> extract -> llm.jev.score/choice -> if -> browser.stagehand(act) -> deliver
stagehand showcase: self-healing act for broker UI changes; laya drives goal
