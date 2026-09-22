// ponytail: single-model global (Verdict 151M / laya alias), per-node model routing if needed
export type TriggerType = "cron" | "manual" | "webhook" | "poll"

export type NodeType =
  | "trigger.cron" | "trigger.manual" | "trigger.webhook" | "trigger.poll"
  | "gmail.read" | "gmail.poll" | "gmail.label"
  | "calendar.read" | "rss.poll"
  | "browser.stagehand" | "scrape.jobs" | "scrape.company"
  | "llm.jev.choice" | "llm.jev.noul" | "llm.jev.score"
  | "llm.summarize" | "llm.rank" | "llm.classify" | "llm.extract" | "llm.research" | "llm.tailor" | "llm.gaps"
  | "store.sheet" | "store.json"
  | "deliver.digest" | "deliver.brief" | "deliver.alert" | "deliver.inbox"
  | "switch" | "if"

export type Workflow = {
  name: string
  description?: string
  trigger: { type: TriggerType; cron?: string; event?: string }
  nodes: { id: string; type: NodeType; params?: Record<string, unknown>; position?: [number, number] }[]
  connections: Record<string, { main: { node: string }[][] }>
}

// self-host default — no TypeSafe key required
export const LLM_MODEL = "verdict-151m" // alias: laya -> Heman10x-NGU/Verdict-open-jev
