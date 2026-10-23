import type { Summary } from "../types";

interface Props {
  summary: Summary;
  view: "mapping" | "insights";
  setView: (v: "mapping" | "insights") => void;
  dark: boolean;
  toggleTheme: () => void;
  onCommit: () => void;
}

export function Header({ summary, view, setView, dark, toggleTheme, onCommit }: Props) {
  const SUN = "M12 4V2M12 22v-2M4 12H2M22 12h-2M6 6 4.5 4.5M19.5 19.5 18 18M18 6l1.5-1.5M4.5 19.5 6 18M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z";
  const MOON = "M21 12.8A8 8 0 1 1 11.2 3a6.2 6.2 0 0 0 9.8 9.8z";
  return (
    <header className="bar">
      <div className="brand">
        <div className="logo">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M4 7h8M4 12h12M4 17h7" />
            <circle cx="18" cy="8" r="2.1" fill="currentColor" stroke="none" />
            <circle cx="19" cy="16" r="2.1" fill="currentColor" stroke="none" />
          </svg>
        </div>
        <div>
          <b>Refresh Studio</b>
          <span>Mapping &amp; alignment</span>
        </div>
      </div>
      <div className="sep" />
      <div className="viewnav">
        <button className={"vn" + (view === "mapping" ? " on" : "")} onClick={() => setView("mapping")}>Mapping</button>
        <button className={"vn" + (view === "insights" ? " on" : "")} onClick={() => setView("insights")}>Insights</button>
      </div>
      <div className="sep" />
      <span className="pick"><small>BMC</small> {summary.bmc.replace("_", " · ")}</span>
      <span className="pick"><small>Refresh</small> {summary.refresh}</span>
      <div className="grow" />
      <span className="env">{(summary.env || "dev").toUpperCase()}</span>
      <button className="icon" title="Theme" onClick={toggleTheme}>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
          <path d={dark ? SUN : MOON} />
        </svg>
      </button>
      <button className="commit" onClick={onCommit}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M20 6L9 17l-5-5" /></svg>
        Commit mapping
      </button>
    </header>
  );
}
