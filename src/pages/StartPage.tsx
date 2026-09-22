import { useEffect, useState } from 'react'

type Wf = { name: string; trigger: { type: string; cron?: string }; nodes: { id: string; type: string; params?: Record<string, unknown> }[]; connections: Record<string, unknown> }

const modules = import.meta.glob<string>('../automation/*/workflow.json', { eager: true, query: '?raw', import: 'default' })
const plans = import.meta.glob<string>('../automation/*/plan.md', { eager: true, query: '?raw', import: 'default' })

function getAutomations() {
  const byId = new Map<string, { id: string; wf?: Wf; plan?: string }>()
  for (const [p, raw] of Object.entries(modules)) {
    const id = p.split('/')[2]
    try { byId.set(id, { ...byId.get(id), id, wf: JSON.parse(raw as string) }) } catch {}
  }
  for (const [p, raw] of Object.entries(plans)) {
    const id = p.split('/')[2]
    byId.set(id, { ...byId.get(id), id, plan: raw as string })
  }
  return [...byId.values()].sort((a, b) => a.id.localeCompare(b.id))
}

export default function StartPage() {
  const autos = getAutomations()
  const [health, setHealth] = useState<string>('')
  useEffect(() => { fetch('/api/health').then(r => r.json()).then(d => setHealth(JSON.stringify(d))).catch(() => setHealth('offline (vite only)')) }, [])

  return (
    <div className="stack-card">
      <div className="stack-card-head">
        <div className="stack-title"><span className="stack-icon">◐</span> automations — n8n-lite (self-host laya → verdict-151m)</div>
      </div>
      <div className="workspace">
        <div className="empty">API: {health || '…'} · {autos.length} workflows · trigger → llm.jev.* → browser.stagehand → deliver · no TypeSafe key needed</div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 12 }}>
          {autos.map(a => (
            <div key={a.id} style={{ border: '1px solid var(--border)', borderRadius: 2, padding: 12, background: '#fff', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontWeight: 600, color: 'var(--text-h)', fontSize: 13 }}>{a.wf?.name ?? a.id} <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>· {a.wf?.trigger.type}{a.wf?.trigger.cron ? ` ${a.wf.trigger.cron}` : ''}</span></div>
              <div style={{ fontSize: 12, color: 'var(--text)', whiteSpace: 'pre-wrap', lineHeight: 1.5, maxHeight: 120, overflow: 'auto', background: 'var(--bg)', padding: 8, borderRadius: 2, border: '1px solid var(--border)' }}>{(a.plan ?? '').slice(0, 400)}</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {(a.wf?.nodes ?? []).map(n => (
                  <span key={n.id} style={{ fontSize: 11, padding: '2px 6px', borderRadius: 2, background: n.type.startsWith('llm') ? '#ede9fe' : n.type.startsWith('browser') ? '#fef3c7' : n.type.startsWith('trigger') ? '#dcfce7' : 'var(--skim-deep)', border: '1px solid var(--border)' }}>{n.type}{n.params?.model ? `:${String(n.params.model)}` : ''}</span>
                ))}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.wf?.nodes.length ?? 0} nodes · {a.wf ? 'workflow.json ✓' : 'no workflow'} · {a.plan ? 'plan.md ✓' : ''}</div>
            </div>
          ))}
        </div>

        <div className="empty" style={{ fontSize: 11 }}>
          _schema: <code>src/automation/_schema/workflow.schema.json</code> + <code>node-types.ts</code> — LLM_MODEL=verdict-151m (laya alias), self-host via <code>server/llm.py</code>. Stagehand nodes are mocked until Playwright key added.
        </div>
      </div>
    </div>
  )
}
