import { useState } from "react"
import "./App.css"

const wfRaw = import.meta.glob<string>("./automation/**/workflow.json", { eager: true, query: "?raw", import: "default" })
const planRaw = import.meta.glob<string>("./automation/**/plan.md", { eager: true, query: "?raw", import: "default" })

function getNames(): string[] {
  const ids = new Set<string>()
  for (const p of Object.keys(wfRaw)) {
    const id = p.replace("./automation/", "").split("/")[0]
    if (id) ids.add(id)
  }
  for (const p of Object.keys(planRaw)) {
    const id = p.replace("./automation/", "").split("/")[0]
    if (id) ids.add(id)
  }
  if (ids.size === 0) {
    const altW = import.meta.glob<string>("../src/automation/**/workflow.json", { eager: true, query: "?raw", import: "default" })
    const altP = import.meta.glob<string>("../src/automation/**/plan.md", { eager: true, query: "?raw", import: "default" })
    for (const p of Object.keys(altW)) {
      const id = p.split("/").slice(-3, -1)[0]
      if (id) ids.add(id)
    }
    for (const p of Object.keys(altP)) {
      const id = p.split("/").slice(-3, -1)[0]
      if (id) ids.add(id)
    }
  }
  return [...ids].sort((a,b)=>a.localeCompare(b))
}

const NAMES = getNames()

export default function App() {
  const [active, setActive] = useState(NAMES[0] ?? "")

  return (
    <div className="frame">
      <div className="frame-inner">
        <header className="topbar">
          <div className="topbar-inner">
            <div className="topbar-left">
              <span className="loom-icon" aria-hidden="true">
                <svg viewBox="0 0 12 12" width="16" height="16" shapeRendering="crispEdges">
                  <rect x="2" y="2" width="3" height="8" fill="white" />
                  <rect x="2" y="7" width="8" height="3" fill="white" />
                </svg>
              </span>
            </div>
            <nav className="topbar-center-pill">
              {NAMES.length ? NAMES.map(n => (
                <button
                  key={n}
                  onClick={() => setActive(n)}
                  className={n === active ? "pill-active" : "pill-idle"}
                >
                  {n}
                </button>
              )) : (
                <>
                  <button className="pill-active">Chat</button>
                  <button className="pill-idle">Spark <span style={{ fontSize: 10, marginLeft: 6, opacity: 0.6 }}>BETA</span></button>
                </>
              )}
            </nav>
            <div className="topbar-right">
              <a href="mailto:hello@loom.com" className="profile-link" aria-label="email">
                <span className="profile-icon" aria-hidden="true">
                  <svg viewBox="0 0 16 16" width="18" height="18" shapeRendering="crispEdges" aria-hidden="true">
                    <rect x="2" y="2" width="4" height="3" fill="white" />
                    <rect x="10" y="2" width="4" height="3" fill="white" />
                    <rect x="3" y="3" width="2" height="1" fill="#111" />
                    <rect x="11" y="3" width="2" height="1" fill="#111" />
                    <rect x="2" y="5" width="12" height="7" fill="white" />
                    <rect x="5" y="7" width="2" height="2" fill="#111" />
                    <rect x="9" y="7" width="2" height="2" fill="#111" />
                    <rect x="7" y="9" width="2" height="1" fill="#111" />
                    <rect x="6" y="10" width="1" height="1" fill="#111" />
                    <rect x="9" y="10" width="1" height="1" fill="#111" />
                    <rect x="1" y="8" width="2" height="1" fill="white" />
                    <rect x="13" y="8" width="2" height="1" fill="white" />
                  </svg>
                </span>
              </a>
            </div>
          </div>
        </header>

        {/* clean page — add your component here */}
        <main style={{ flex: 1, background: "#fff", minHeight: "60vh" }} />

        <footer className="site-foot">©2026 LOOM</footer>
      </div>
    </div>
  )
}
