import { useState } from "react"
import "./App.css"

type Wf = { name: string; trigger: { type: string; cron?: string }; nodes: { id: string; type: string; params?: Record<string, unknown> }[] }

const wfRaw = import.meta.glob<string>("../automation/**/workflow.json", { eager: true, query: "?raw", import: "default" })
const planRaw = import.meta.glob<string>("../automation/**/plan.md", { eager: true, query: "?raw", import: "default" })

function getAutos() {
  const m = new Map<string, { id: string; label: string; wf?: Wf; plan?: string }>()
  for (const [p, raw] of Object.entries(wfRaw)) {
    const id = p.replace("../automation/", "").replace("/workflow.json", "")
    const label = id.includes("/") ? id.split("/").pop()! : id
    try { m.set(id, { ...m.get(id), id, label, wf: JSON.parse(raw as string) }) } catch {}
  }
  for (const [p, raw] of Object.entries(planRaw)) {
    const id = p.replace("../automation/", "").replace("/plan.md", "")
    const label = id.includes("/") ? id.split("/").pop()! : id
    m.set(id, { ...m.get(id)!, id, label, plan: raw as string })
    if (!m.get(id)!.wf) m.get(id)!.wf = undefined as any
    if (!m.has(id)) m.set(id, { id, label, plan: raw as string })
  }
  return [...m.values()].sort((a, b) => a.id.localeCompare(b.id))
}

const AUTOS = getAutos()

export default function App() {
  const [sel, setSel] = useState<string>(AUTOS[0]?.id ?? "")

  const cur = AUTOS.find(a => a.id === sel)

  return (
    <div className="frame">
      <div className="frame-inner">
        <header className="topbar">
          <div className="topbar-inner">
            <span className="topbar-logo"><span className="stack-icon">◐</span> loom</span>
            <label className="topbar-select-wrap" aria-label="Automations">
              <select value={sel} onChange={e => setSel(e.target.value)} className="topbar-select">
                {AUTOS.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
              </select>
              <span className="topbar-caret">▾</span>
            </label>
            <span className="topbar-hint hidden md:inline">{AUTOS.length} automations</span>
          </div>
        </header>

        <main className="stack">
          <div className="stack-card">
            <div className="stack-card-head">
              <div className="stack-title"><span className="stack-icon">◐</span> {cur?.wf?.name ?? cur?.label ?? "—"}</div>
              <div className="ml-auto text-xs" style={{ color: "var(--text-muted)" }}>{cur?.wf?.trigger.type ?? ""} {cur?.wf?.trigger.cron ?? ""}</div>
            </div>
            <div className="workspace" style={{ flex: 1 }}>
              {!cur ? (
                <div className="empty">no automations</div>
              ) : (
                <div style={{ border: "1px solid var(--border)", borderRadius: 2, background: "#fff", padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-h)" }}>{cur.id} {cur.wf ? "· workflow.json" : ""} {cur.plan ? "· plan.md" : ""}</div>
                  {cur.plan && <div style={{ fontSize: 12, color: "var(--text)", whiteSpace: "pre-wrap", lineHeight: 1.5, maxHeight: 160, overflow: "auto", background: "var(--skim)", padding: 8, border: "1px solid var(--border)", borderRadius: 2 }}>{cur.plan.slice(0, 600)}</div>}
                  {cur.wf && (
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {cur.wf.nodes.map(n => (
                        <span key={n.id} style={{ fontSize: 11, padding: "2px 6px", borderRadius: 2, background: "var(--skim-deep)", border: "1px solid var(--border)" }}>{n.type}</span>
                      ))}
                    </div>
                  )}
                  <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{cur.wf?.nodes.length ?? 0} nodes</div>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
