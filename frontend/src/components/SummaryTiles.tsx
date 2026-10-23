import type { Proposal } from "../types";

const TILES: Array<[string, string, string | null]> = [
  ["Total", "var(--muted)", null],
  ["Confirmed", "var(--blue)", "confirmed"],
  ["Suggested", "var(--ok)", "suggested"],
  ["Needs review", "var(--warn)", "review"],
  ["Unmapped", "var(--bad)", "unmapped"],
];

export function SummaryTiles({ proposals, statusFilter, setStatusFilter }: {
  proposals: Proposal[];
  statusFilter: string | null;
  setStatusFilter: (s: string | null) => void;
}) {
  const c: Record<string, number> = { total: proposals.length };
  proposals.forEach((p) => { c[p.status] = (c[p.status] || 0) + 1; });
  return (
    <div className="summary">
      {TILES.map(([label, color, key]) => {
        const count = key ? c[key] || 0 : c.total;
        const on = statusFilter === key && key !== null;
        return (
          <div key={label} className={"tile" + (on ? " active" : "")} onClick={() => key && setStatusFilter(statusFilter === key ? null : key)}>
            <div className="t"><span className="dot" style={{ background: color }} />{label}</div>
            <div className="v tnum">{count}</div>
          </div>
        );
      })}
    </div>
  );
}
