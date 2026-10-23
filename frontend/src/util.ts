import type { Proposal } from "./types";

export const SUBS = ["Access", "Multivitaminicos", "Others", "Select"];

export const DOMAIN_LABEL: Record<string, string> = {
  raw_to_processed: "Raw → Processed",
  processing_detail_to_processed: "Processing detail → Processed",
  contribution_to_processed: "Contribution → Processed",
};

export function humanize(v: string): string {
  const majors = v.split("__");
  const cat = majors[0];
  const tail = majors[majors.length - 1].replace(/_/g, " ").replace(/-/g, " ");
  const sb = (v.match(/sub-brand-([a-z0-9&-]+)/i) || [])[1];
  const lab = cat.charAt(0).toUpperCase() + cat.slice(1) + " · " + tail + (sb ? " · " + sb : "");
  return lab.length > 52 ? lab.slice(0, 51) + "…" : lab;
}

export const short = (v: string) => v.split("__").slice(-1)[0].replace(/_/g, " ");

export function confColor(c: number): string {
  return c >= 0.92 ? "var(--ok)" : c >= 0.6 ? "var(--warn)" : "var(--bad)";
}

export const fmt = (n: number) => (n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(Math.round(n)));

export function weightLabel(t: { active?: boolean; percent: number; weight: { kind: string; value?: unknown; side?: string; breakpoint?: string } }): string {
  const on = t.active || t.percent > 0;
  if (!on) return "weight 0";
  if (t.weight.kind === "rule") return `${t.weight.side} ${t.weight.breakpoint}`;
  if (t.weight.kind === "vector") return "time mask";
  return t.weight.value === 1 ? "×1 (replicate)" : `×${t.weight.value} (${t.percent}%)`;
}

export function splitNote(kind: string | null): string {
  if (kind === "temporal") return "Temporal split: routed by a dated breakpoint; a new month flows into the later regime automatically.";
  if (kind === "membership") return "By value: active regions carry the same series (replicated); zero regions get nothing.";
  if (kind === "varying") return "Active regions carry different values — flagged for review.";
  return "";
}

/** Rows that feed a target also fed by another proposal → double-count risk. */
export function dedupConflicts(proposals: Proposal[]): Set<number> {
  const byTarget: Record<string, number[]> = {};
  proposals.forEach((r, i) => {
    if (r.action === "unmapped" || r.action === "skip" || r.action === "aggregate") return;
    (r.targets || []).forEach((t) => {
      if (!(t.active || t.percent > 0)) return;
      const k = t.var + "|" + t.region;
      (byTarget[k] = byTarget[k] || []).push(i);
    });
  });
  const out = new Set<number>();
  Object.values(byTarget).forEach((ids) => { if (ids.length > 1) ids.forEach((i) => out.add(i)); });
  return out;
}

export function sparklinePath(ser: number[]): { d: string; flat: boolean; w: number; h: number } {
  const w = 70, h = 20;
  const mx = Math.max(...ser, 1e-9);
  const flat = mx <= 1e-9;
  const d = ser
    .map((v, i) => `${i ? "L" : "M"}${((i / (ser.length - 1)) * w).toFixed(1)},${(h - (v / (mx || 1)) * (h - 3) - 1.5).toFixed(1)}`)
    .join("");
  return { d, flat, w, h };
}
