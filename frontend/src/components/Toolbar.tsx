const ACTIONS = ["all", "direct", "rename", "split", "aggregate", "unmapped"];

interface Props {
  q: string; setQ: (v: string) => void;
  action: string; setAction: (v: string) => void;
  sort: string; setSort: (v: string) => void;
  reviewOnly: boolean; toggleReview: () => void;
  onAcceptAll: () => void;
}

export function Toolbar({ q, setQ, action, setAction, sort, setSort, reviewOnly, toggleReview, onAcceptAll }: Props) {
  return (
    <div className="toolbar">
      <div className="search">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--faint)" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
        <input value={q} placeholder="Search variable name or token…" onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="chips">
        {ACTIONS.map((a) => (
          <button key={a} className={"chip" + (action === a ? " on" : "")} onClick={() => setAction(a)}>
            {a === "all" ? "All types" : a}
          </button>
        ))}
      </div>
      <div className="selwrap">
        Sort
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="conf-asc">Confidence ↑ (review first)</option>
          <option value="conf-desc">Confidence ↓</option>
          <option value="status">Status</option>
          <option value="name">Name A–Z</option>
        </select>
      </div>
      <button className={"btn" + (reviewOnly ? " key" : "")} onClick={toggleReview}>Review queue</button>
      <button className="btn key" onClick={onAcceptAll}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M20 6L9 17l-5-5" /></svg>
        Accept suggested
      </button>
    </div>
  );
}
