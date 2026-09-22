import "./App.css"

export default function App() {
  return (
    <div className="frame">
      <div className="frame-inner">
        <header className="topbar">
          <div className="topbar-inner">
            <div className="topbar-left">Bureau Nine</div>
            <nav className="topbar-center">
              <a href="#about">About</a>
              <a href="#work">Work</a>
              <a href="#contact">Contact</a>
            </nav>
            <div className="topbar-right">
              <a href="https://linkedin.com" target="_blank" rel="noreferrer">Linkedin</a>
              <a href="mailto:hello@bureaunine.com">Email</a>
            </div>
          </div>
        </header>

        {/* clean page — add your component here */}
        <main style={{ flex: 1, background: "#fff", minHeight: "60vh" }} />

        <footer className="site-foot">©2026 Bureau Nine</footer>
      </div>
    </div>
  )
}
