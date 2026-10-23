import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { Header } from "./components/Header";
import { Insights } from "./components/Insights";
import { MappingTable } from "./components/MappingTable";
import { SplitEditor } from "./components/SplitEditor";
import { SummaryTiles } from "./components/SummaryTiles";
import { Toolbar } from "./components/Toolbar";
import { useTheme } from "./theme";
import type { Analysis, Insights as InsightsData, Proposal, Summary } from "./types";
import { dedupConflicts, DOMAIN_LABEL } from "./util";

const BOOT = { env: "dev", bmc: "Brazil_Centrum", refresh: "2025 Q3 Refresh" };

export default function App() {
  const { dark, toggle } = useTheme();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [domain, setDomain] = useState("raw_to_processed");
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [view, setView] = useState<"mapping" | "insights">("mapping");
  const [insights, setInsights] = useState<InsightsData | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const [q, setQ] = useState("");
  const [action, setAction] = useState("all");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [sort, setSort] = useState("conf-asc");
  const [reviewOnly, setReviewOnly] = useState(false);

  function flash(m: string) { setToast(m); setTimeout(() => setToast(null), 1900); }

  useEffect(() => {
    (async () => {
      try {
        const s = await api.createSession(BOOT);
        setSummary(s);
        setAnalysis(s.analysis);
        const dom = Object.keys(s.domains)[0] || "raw_to_processed";
        setDomain(dom);
        const m = await api.getMapping(s.id, dom);
        setProposals(m.proposals);
      } catch (e: any) {
        setError(e.message || String(e));
      }
    })();
  }, []);

  async function loadDomain(id: string, dom: string) {
    setDomain(dom);
    setExpanded({});
    const m = await api.getMapping(id, dom);
    setProposals(m.proposals);
  }

  async function pushAndAnalyze(next: Proposal[]) {
    if (!summary) return;
    setProposals(next);
    setInsights(null);
    try {
      const res = await api.patchMapping(summary.id, domain, next);
      setAnalysis(res.analysis);
    } catch (e: any) { flash("Save failed: " + e.message); }
  }

  const conflicts = useMemo(() => dedupConflicts(proposals), [proposals]);

  const rows = useMemo<Array<[Proposal, number]>>(() => {
    let list: Array<[Proposal, number]> = proposals.map((p, i) => [p, i]);
    if (q) { const l = q.toLowerCase(); list = list.filter(([p]) => (p.source_var).toLowerCase().includes(l)); }
    if (action !== "all") list = list.filter(([p]) => p.action === action);
    if (statusFilter) list = list.filter(([p]) => p.status === statusFilter);
    if (reviewOnly) list = list.filter(([p]) => p.status === "review" || p.status === "unmapped");
    const order: Record<string, number> = { review: 0, unmapped: 1, suggested: 2, confirmed: 3 };
    list.sort(([a], [b]) => {
      if (sort === "conf-asc") return a.confidence - b.confidence;
      if (sort === "conf-desc") return b.confidence - a.confidence;
      if (sort === "name") return a.source_var.localeCompare(b.source_var);
      if (sort === "status") return order[a.status] - order[b.status];
      if (sort === "type") return a.action.localeCompare(b.action);
      return 0;
    });
    return list;
  }, [proposals, q, action, statusFilter, reviewOnly, sort]);

  async function switchView(v: "mapping" | "insights") {
    setView(v);
    if (v === "insights" && !insights && summary) {
      try { setInsights(await api.insights(summary.id)); } catch (e: any) { flash("Insights failed: " + e.message); }
    }
  }

  async function doExtend() {
    if (!summary) return;
    try { const r = await api.extend(summary.id); flash(`Extended +${r.new_weeks} weeks`); setInsights(await api.insights(summary.id)); }
    catch (e: any) { flash("Extend failed: " + e.message); }
  }
  async function doCommit() {
    if (!summary) return;
    try { await pushAndAnalyze(proposals); await api.commit(summary.id); flash("Mapping committed to baseline"); }
    catch (e: any) { flash("Commit failed: " + e.message); }
  }

  const onAccept = (i: number) => pushAndAnalyze(proposals.map((p, j) => j === i && p.status !== "unmapped" ? { ...p, status: "confirmed", confidence: Math.max(p.confidence, 1) } : p));
  const onAcceptAll = () => { pushAndAnalyze(proposals.map((p) => p.status === "suggested" ? { ...p, status: "confirmed" } : p)); flash("Accepted all suggested"); };
  const onEditSave = (i: number, np: Proposal) => { setEditing(null); pushAndAnalyze(proposals.map((p, j) => j === i ? np : p)); flash("Mapping updated"); };
  const onToggle = (i: number) => setExpanded((e) => ({ ...e, [i]: !e[i] }));

  if (error) return (
    <div className="overlay">
      <div style={{ fontWeight: 700 }}>Couldn’t reach the backend.</div>
      <div style={{ fontSize: 12, maxWidth: 420, textAlign: "center" }}>
        Start it with <code>uvicorn mmm_refresh.api:app</code> on :8000, then reload. ({error})
      </div>
    </div>
  );
  if (!summary) return <div className="overlay"><div className="spin" /><div>Loading session…</div></div>;

  const wd = analysis?.weekly_deviation;
  const mm = analysis?.unaligned.mismatch.length ?? 0;
  const aligned = wd ? wd.weeks_within_tol === wd.weeks_total && mm === 0 : true;
  const alignNode = wd ? (
    <span>
      {conflicts.size > 0 && <span style={{ color: "var(--bad)", fontWeight: 600 }}>⚠ {conflicts.size} dup-target rows · </span>}
      <span style={{ color: aligned ? "var(--ok)" : "var(--warn)", fontWeight: 600 }}>{aligned ? "✓ aligned" : `⚠ ${mm} off`}</span> · {wd.weeks_within_tol}/{wd.weeks_total} weeks within tol
    </span>
  ) : null;

  return (
    <>
      <div className="wrap">
        <Header summary={summary} view={view} setView={switchView} dark={dark} toggleTheme={toggle} onCommit={doCommit} />
        {view === "mapping" ? (
          <>
            <div className="tabs">
              {Object.keys(summary.domains).map((d) => (
                <button key={d} className={"tab" + (d === domain ? " on" : "")} onClick={() => loadDomain(summary.id, d)}>
                  {DOMAIN_LABEL[d] || d} <span className="n">{summary.domains[d].total}</span>
                </button>
              ))}
            </div>
            <SummaryTiles proposals={proposals} statusFilter={statusFilter} setStatusFilter={setStatusFilter} />
            <Toolbar q={q} setQ={setQ} action={action} setAction={setAction} sort={sort} setSort={setSort} reviewOnly={reviewOnly} toggleReview={() => { setReviewOnly(!reviewOnly); setSort("conf-asc"); }} onAcceptAll={onAcceptAll} />
            <MappingTable rows={rows} total={proposals.length} conflicts={conflicts} expanded={expanded} onToggle={onToggle} onAccept={onAccept} onEdit={setEditing} sort={sort} setSort={setSort} alignNode={alignNode} />
          </>
        ) : (
          insights ? <Insights data={insights} onExtend={doExtend} /> : <div className="overlay" style={{ position: "static", padding: 40 }}><div className="spin" /></div>
        )}
      </div>

      <div className={"scrim" + (editing !== null ? " open" : "")} onClick={() => setEditing(null)} />
      <aside className={"drawer" + (editing !== null ? " open" : "")}>
        {editing !== null && proposals[editing] && (
          <SplitEditor proposal={proposals[editing]} onSave={(np) => onEditSave(editing, np)} onClose={() => setEditing(null)} />
        )}
      </aside>

      <div className={"toast" + (toast ? " show" : "")}>{toast}</div>
    </>
  );
}
