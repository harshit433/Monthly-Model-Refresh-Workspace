import { useMemo, useState } from "react";
import type { Proposal, Target } from "../types";
import { humanize, SUBS } from "../util";
import { Sparkline } from "./Sparkline";

const ACTIONS = ["direct", "rename", "split", "aggregate", "skip", "unmapped"];
const KINDS: Array<[string, string]> = [["membership", "By presence"], ["percentage", "By percentage"], ["temporal", "By time"]];

function ensureAllRegions(p: Proposal): Target[] {
  const present: Record<string, Target> = {};
  p.targets.forEach((t) => { present[t.region] = t; });
  return SUBS.map((sb) => {
    const reg = `('${sb}',)`;
    return present[reg] || { var: p.source_var, region: reg, active: false, percent: 0, weight: { kind: "scalar", value: 0 }, series: null };
  });
}

export function SplitEditor({ proposal, onSave, onClose }: {
  proposal: Proposal;
  onSave: (p: Proposal) => void;
  onClose: () => void;
}) {
  const p = proposal;
  const [action, setAction] = useState(p.action === "unmapped" ? "unmapped" : p.action);
  const [kind, setKind] = useState<string>(p.kind || (p.action === "split" ? "membership" : "membership"));
  const [breakpoint, setBreakpoint] = useState(p.breakpoint || "2025-05-01");
  const [regs, setRegs] = useState<Target[]>(() => ensureAllRegions(p));
  const [tgtVar, setTgtVar] = useState(p.targets[0]?.var || p.source_var);
  const [tgtReg, setTgtReg] = useState(p.targets[0]?.region || p.source_region);
  const initTemp = useMemo(() => {
    const base = p.targets.length >= 2 ? p.targets.slice(0, 2) : ensureAllRegions(p).slice(0, 2);
    return base.map((t) => ({ var: t.var, region: t.region, series: t.series, side: (t.weight?.kind === "rule" ? t.weight.side : "after") || "after" }));
  }, []); // eslint-disable-line
  const [temp, setTemp] = useState(initTemp);

  const pctSum = regs.reduce((s, r) => s + (r.active || r.percent > 0 ? r.percent : 0), 0);

  function save() {
    let targets: Target[] = [];
    let status = "confirmed";
    let confidence = 1.0;
    if (action === "split") {
      if (kind === "membership") {
        targets = regs.map((t) => ({ var: t.var, region: t.region, active: !!t.active, percent: t.active ? 100 : 0, weight: { kind: "scalar", value: t.active ? 1 : 0 }, series: t.series }));
      } else if (kind === "percentage") {
        targets = regs.map((t) => ({ var: t.var, region: t.region, active: t.percent > 0, percent: t.percent, weight: { kind: "scalar", value: t.percent / 100 }, series: t.series }));
      } else {
        targets = temp.map((t) => ({ var: t.var, region: t.region, active: true, percent: 100, weight: { kind: "rule", breakpoint, side: t.side }, series: t.series }));
      }
    } else if (action === "rename" || action === "direct") {
      targets = [{ var: tgtVar, region: tgtReg, active: true, percent: 100, weight: { kind: "scalar", value: 1 }, series: p.targets[0]?.series ?? null }];
    } else if (action === "aggregate") {
      targets = [{ var: tgtVar, region: p.targets[0]?.region || p.source_region, active: true, percent: 100, weight: { kind: "scalar", value: 1 }, series: p.targets[0]?.series ?? null }];
    } else if (action === "unmapped") {
      status = "unmapped"; confidence = 0;
    }
    onSave({
      ...p, action, kind: action === "split" ? (kind === "percentage" ? "proportional" : kind) : null,
      targets, provenance: "manual", status, confidence,
      breakpoint: action === "split" && kind === "temporal" ? breakpoint : undefined,
    });
  }

  return (
    <>
      <div className="dh">
        <div style={{ flex: 1 }}>
          <h3>Edit mapping</h3>
          <div className="vname" style={{ marginTop: 4 }}>{humanize(p.source_var)}</div>
          <div className="vtok mono">{p.source_var} · {p.source_region}</div>
        </div>
        <button className="icon" onClick={onClose}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12" /></svg>
        </button>
      </div>

      <div className="dbody">
        <div className="fld">
          <label>Action</label>
          <div className="seg">
            {ACTIONS.map((a) => (
              <button key={a} className={action === a ? "on" : ""} onClick={() => setAction(a)}>{a}</button>
            ))}
          </div>
        </div>

        {action === "split" && (
          <div className="fld">
            <label>How to split</label>
            <div className="seg">
              {KINDS.map(([k, lbl]) => (
                <button key={k} className={kind === k ? "on" : ""} onClick={() => setKind(k)}>{lbl}</button>
              ))}
            </div>
          </div>
        )}

        {action === "split" && (kind === "membership" || kind === "varying") && (
          <div className="fld">
            <label>Active regions (carry the source value)</label>
            {regs.map((t, i) => {
              const on = !!(t.active || t.percent > 0);
              return (
                <div className="trow" key={i}>
                  <span className="rg">{t.region}</span>
                  <Sparkline series={t.series} active={on} />
                  <label className="switch">
                    <input type="checkbox" checked={on} onChange={(e) => setRegs((rs) => rs.map((r, j) => j === i ? { ...r, active: e.target.checked, percent: e.target.checked ? 100 : 0 } : r))} />
                    <span className="slider" />
                  </label>
                </div>
              );
            })}
            <div className="hint">Auto-detected by value: regions with the same non-zero series are active; zero regions are off. Toggle to override.</div>
          </div>
        )}

        {action === "split" && kind === "percentage" && (
          <div className="fld">
            <label>Share per region</label>
            {regs.map((t, i) => (
              <div className="trow" key={i}>
                <span className="rg">{t.region}</span>
                <input className="input pctin tnum" type="number" min={0} max={100} step={1}
                  value={t.active || t.percent > 0 ? t.percent : 0}
                  onChange={(e) => setRegs((rs) => rs.map((r, j) => j === i ? { ...r, percent: Number(e.target.value) || 0 } : r))} />
                <span className="muted">%</span>
              </div>
            ))}
            <div className={"sumline " + (Math.abs(pctSum - 100) < 0.01 ? "ok" : "bad")}>
              <span>Total</span><span>{pctSum}% {Math.abs(pctSum - 100) < 0.01 ? "✓" : "(must be 100%)"}</span>
            </div>
            <div className="hint">Enter explicit shares (must total 100%). Use only when you really want fixed fractions.</div>
          </div>
        )}

        {action === "split" && kind === "temporal" && (
          <>
            <div className="fld">
              <label>Breakpoint date</label>
              <input className="input" type="date" value={breakpoint} onChange={(e) => setBreakpoint(e.target.value)} />
            </div>
            <div className="fld">
              <label>Assign each target to a regime</label>
              {temp.map((t, i) => (
                <div className="trow" key={i}>
                  <span className="rg">{t.var.split("__").slice(-1)[0]} · {t.region}</span>
                  <Sparkline series={t.series} active={true} />
                  <select className="tsel" value={t.side} onChange={(e) => setTemp((ts) => ts.map((x, j) => j === i ? { ...x, side: e.target.value } : x))}>
                    <option value="before">before date</option>
                    <option value="after">on/after date</option>
                  </select>
                </div>
              ))}
              <div className="hint">Weeks before the date route to the “before” target, on/after to the “after” target. A new month lands in the on/after regime.</div>
            </div>
          </>
        )}

        {(action === "rename" || action === "direct") && (
          <>
            <div className="fld"><label>Target variable</label><input className="input mono" value={tgtVar} onChange={(e) => setTgtVar(e.target.value)} /></div>
            <div className="fld"><label>Target region</label><input className="input mono" value={tgtReg} onChange={(e) => setTgtReg(e.target.value)} /></div>
          </>
        )}

        {action === "aggregate" && (
          <>
            <div className="fld"><label>Sources aggregated into one target</label><div className="hint">{p.sources.map((s) => s.var).join(", ")}</div></div>
            <div className="fld"><label>Target variable</label><input className="input mono" value={tgtVar} onChange={(e) => setTgtVar(e.target.value)} /></div>
          </>
        )}

        {action === "skip" && <div className="hint">This source will be dropped (not mapped). Use for a redundant parent whose one-hot children are already mapped.</div>}
        {action === "unmapped" && <div className="hint">No confident match. Pick an action above to map it manually, or leave unmapped.</div>}
      </div>

      <div className="dfoot">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="save" onClick={save}>Save mapping</button>
      </div>
    </>
  );
}
