import { motion } from "motion/react"
import Overview from "./pages/Overview"
import "./App.css"

export default function App() {
  return (
    <div className="frame">
      <div className="frame-inner">
        <main className="stack">
          <div className="stack-card">
            <div className="stack-card-head">
              <div className="stack-title"><span className="stack-icon">◐</span> loom</div>
              <div className="ml-auto flex items-center gap-2">
                <span className="hidden md:inline text-xs font-medium" style={{ color: "var(--text-muted)" }}>motion · shadcn · magic · aceternity</span>
                <motion.a whileHover={{ y: -0.5 }} href="https://motion.dev" target="_blank" rel="noreferrer" className="text-xs px-2.5 py-1 rounded-full border bg-white" style={{ borderColor: "var(--border)", color: "var(--text-h)" }}>motion ↗</motion.a>
              </div>
            </div>

            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: [0.25, 0.1, 0.25, 1] }}
              style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}
            >
              <Overview />
            </motion.div>
          </div>
        </main>
      </div>
    </div>
  )
}
