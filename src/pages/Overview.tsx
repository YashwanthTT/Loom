import { motion } from "motion/react"
import { Card, CardContent, CardHeader, CardTitle, CardDesc } from "../components/ui/card"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import { ShimmerButton, Spotlight } from "../components/ui/shimmer-button"
import { Marquee } from "../components/ui/marquee"
import { BentoGrid, BentoCard, DotPattern } from "../components/ui/grid"
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs"
import { useState } from "react"

const fade = { initial:{opacity:0,y:8}, animate:{opacity:1,y:0}, transition:{duration:0.45, ease:[0.25,0.1,0.25,1] as any} }

export default function Overview() {
  const [tab, setTab] = useState("overview")
  return (
    <div className="workspace" style={{ gap:16 }}>
      {/* Hero - aceternity Spotlight + magic shimmer */}
      <motion.div {...fade} className="relative overflow-hidden rounded-[16px] border border-[var(--border)] bg-white p-6 md:p-8">
        <DotPattern />
        <Spotlight />
        <div className="relative flex flex-col gap-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex flex-col gap-2 max-w-[560px]">
              <div className="flex items-center gap-2">
                <Badge>✦ loom — automation canvas</Badge>
                <span className="text-xs text-[var(--text-muted)]">shadcn · magicui · aceternity · motion</span>
              </div>
              <h1 className="text-[22px] md:text-[26px] font-semibold tracking-[-0.03em] text-[var(--text-h)] leading-tight">
                Ship automations <span className="bg-gradient-to-r from-violet-600 to-fuchsia-500 bg-clip-text text-transparent" style={{WebkitBackgroundClip:"text"}}>beautifully</span>. Canvas, nodes, runs — all in one calm UI.
              </h1>
              <p className="text-[13px] leading-relaxed text-[var(--text)]">Wireframe in Image 1 → polished shell. Motion for every hover, tap, and page transition. No logic yet — just the design system.</p>
            </div>
            <div className="flex items-center gap-2 self-start">
              <Button variant="secondary" size="md">View docs</Button>
              <ShimmerButton>New workflow</ShimmerButton>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="workflows">Workflows</TabsTrigger>
                <TabsTrigger value="runs">Runs</TabsTrigger>
                <TabsTrigger value="components">Components</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="ml-auto flex items-center gap-2">
              <Input placeholder="Search workflows…" style={{ width:200 }} />
              <Button variant="outline" size="sm">⌘K</Button>
            </div>
          </div>
        </div>

        <motion.div className="relative mt-6 grid grid-cols-3 gap-3" initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ delay:0.15 }}>
          {[
            { k:"Active flows", v:"12", sub:"+3 this week" },
            { k:"Success rate", v:"98.2%", sub:"1.2k runs" },
            { k:"Avg. latency", v:"1.4s", sub:"p95 2.8s" },
          ].map((s,i)=>(
            <Card key={s.k} className="p-3.5" style={{ animationDelay:`${i*80}ms` } as any}>
              <div className="text-[11px] font-medium" style={{ color:"var(--text-muted)" }}>{s.k}</div>
              <div className="text-[20px] font-semibold tracking-[-0.02em]" style={{ color:"var(--text-h)" }}>{s.v}</div>
              <div className="text-xs" style={{ color:"#0e7a4b", fontWeight:600 }}>{s.sub}</div>
            </Card>
          ))}
        </motion.div>
        <Marquee items={["trigger.cron 0 9 * * *","llm.jev.verdict-151m","browser.stagehand act","deliver.slack #loom","node.if → branch","retry with backoff"]} />
      </motion.div>

      {tab !== "overview" && (
        <div className="empty">
          <div className="empty-icon">◐</div>
          <div style={{ fontWeight:600, color:"var(--text-h)" }}>{tab} — empty</div>
          <div style={{ fontSize:12 }}>No {tab} yet. Create a workflow to see it here.</div>
        </div>
      )}

      {/* Bento - aceternity */}
      <BentoGrid>
        <BentoCard span="md:col-span-2" title="Visual canvas" desc="Drag nodes, wire edges, inspect payloads. Zoom, minimap, and undo — Figma-like but for workflows." icon="◈" delay={0.05} />
        <BentoCard title="Runs & logs" desc="Every execution is replayable. Step-through, diff inputs, jump to node." icon="▶" delay={0.1} />
        <BentoCard title="Triggers" desc="Cron, webhook, email, manual. One trigger type per workflow, validated by schema." icon="◐" delay={0.12} />
        <BentoCard span="md:col-span-2" title="Stagehand browser" desc="Natural language → Playwright. Mocked locally until keys added — then live." icon="⬙" delay={0.15} />
        <BentoCard title="Deliver anywhere" desc="Slack, email, sheet, webhook — last node always a delivery." icon="✉" delay={0.18} />
      </BentoGrid>

      {/* Component gallery - shadcn + animate-ui */}
      <motion.div {...fade} transition={{ delay:0.2 } as any} className="grid md:grid-cols-2 gap-3">
        <Card>
          <CardHeader>
            <CardTitle>Components</CardTitle>
            <CardDesc>shadcn primitives · motion on every interaction</CardDesc>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              <Button size="sm">Default</Button>
              <Button variant="secondary" size="sm">Secondary</Button>
              <Button variant="outline" size="sm">Outline</Button>
              <Button variant="ghost" size="sm">Ghost</Button>
              <Badge>badge</Badge>
              <Badge className="bg-violet-50 border-violet-200 text-violet-700">llm.jev</Badge>
              <Badge className="bg-amber-50 border-amber-200 text-amber-700">browser</Badge>
            </div>
            <div className="flex gap-2">
              <Input placeholder="workflow name" />
              <Button>Save</Button>
            </div>
            <div className="rounded-[10px] border border-dashed border-[var(--border)] bg-[var(--skim)] p-3 text-xs text-[var(--text-muted)]">
              Cards, badges, inputs, tabs — copy-paste ready under <code>src/components/ui</code>. Add when needed, delete when not.
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Motion</CardTitle>
            <CardDesc>motion.dev · spring taps, layout tabs, marquee, shimmer</CardDesc>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex gap-2 overflow-auto pb-1">
              {["◐ Canvas","◑ Runs","◒ Triggers","◓ Deliver"].map((t,i)=>(
                <motion.div key={t} whileHover={{ y:-1, scale:1.02 }} whileTap={{ scale:0.98 }} className="shrink-0 rounded-[10px] border border-[var(--border)] bg-white px-3 py-2 text-xs font-medium shadow-sm" transition={{ type:"spring", stiffness:400, damping:20, delay:i*0.04 }}>
                  {t}
                </motion.div>
              ))}
            </div>
            <div className="h-[86px] rounded-[10px] border border-[var(--border)] bg-[var(--skim)] grid place-items-center overflow-hidden relative">
              <motion.div animate={{ rotate:360 }} transition={{ duration:6, repeat:Infinity, ease:"linear" }} className="h-10 w-10 rounded-full border-2 border-[var(--border)] border-t-[var(--accent)]" />
              <span className="absolute bottom-2 text-[11px] text-[var(--text-muted)]">hover the pills ↑ · drag-free</span>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      <div className="text-[11px] text-[var(--text-muted)] text-center py-2">UI only — no workflow execution wired. Next: wire real canvas + n8n-lite runtime.</div>
    </div>
  )
}
