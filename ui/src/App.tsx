import { useEffect, useState } from "react";
import AskView from "./components/AskView";
import Dashboard from "./components/Dashboard";
import Sidebar from "./components/Sidebar";
import { AskProvider } from "./context/AskContext";

type Tab = "ask" | "dashboard";
type Theme = "light" | "dark";

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem("theme");
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  return [theme, () => setTheme((t) => (t === "light" ? "dark" : "light"))];
}

function BrandMark() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
      <rect x="1" y="1" width="24" height="24" rx="7" style={{ fill: "var(--accent)" }} />
      {/* three retrieval "chunks" feeding an answer -- the pipeline, as a glyph */}
      <rect x="6" y="7" width="9" height="2.6" rx="1.3" fill="rgba(255,255,255,0.55)" />
      <rect x="6" y="11.7" width="14" height="2.6" rx="1.3" fill="#ffffff" />
      <rect x="6" y="16.4" width="11" height="2.6" rx="1.3" fill="rgba(255,255,255,0.55)" />
    </svg>
  );
}

function AppShell() {
  const [tab, setTab] = useState<Tab>("ask");
  const [theme, toggleTheme] = useTheme();

  return (
    <div className="app-frame">
      <header className="topbar">
        <div className="brand">
          <BrandMark />
          <div className="brand-text">
            <span className="brand-title">BridgeMind</span>
            <span className="brand-subtitle">Retrieval console</span>
          </div>
        </div>

        <nav className="tabs">
          <button className={tab === "ask" ? "tab active" : "tab"} onClick={() => setTab("ask")}>
            Ask
          </button>
          <button className={tab === "dashboard" ? "tab active" : "tab"} onClick={() => setTab("dashboard")}>
            Dashboard
          </button>
        </nav>

        <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </header>

      <div className="app-body">
        <Sidebar onSelect={() => setTab("ask")} />

        <main className="app-main">
          {/* Both views stay mounted so an in-flight query in AskView (streaming fetch +
              shared context state) keeps running when the user switches to Dashboard and
              back -- conditional rendering would unmount AskView and lose that state. */}
          <div className="view" hidden={tab !== "ask"}>
            <AskView />
          </div>
          <div className="view" hidden={tab !== "dashboard"}>
            <Dashboard />
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AskProvider>
      <AppShell />
    </AskProvider>
  );
}
