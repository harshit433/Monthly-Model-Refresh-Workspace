import React from "react";
import type { Proposal } from "../types";
import { confColor, humanize, splitNote, weightLabel } from "../util";
import { Sparkline } from "./Sparkline";

function targetCell(r: Proposal) {
  if (r.action === "unmapped") return <span className="reg muted">— unresolved —</span>;
  if (r.action === "aggregate")
    return (<><div className="vname">{r.targets[0].var.split("__").slice(-1)[0]}</div><span className="reg">{r.targets[0].region} · {r.sources.length} sources</span></>);
  const act = r.targets.filter((t) => t.active || t.percent > 0);
  if (r.action === "split")
    return (<><div className="reg multi">{act.length} of {r.targets.length} regions · {r.kind || "split"}</div><span className="reg">{r.targets[0].var.split("__").slice(-1)[0]}</span></>);
  const t = r.targets[0];
  return (<><div className="vname">{t ? (t.var === r.source_var ? "same name" : t.var.split("__").slice(-1)[0]) : "—"}</div><span className="reg">{t ? t.region : ""}</span></>);
}

interface Props {
  rows: Array<[Proposal, number]>;
  total: number;
  conflicts: Set<number>;
  expanded: Record<number, boolean>;
  onToggle: (i: number) => void;
  onAccept: (i: number) => void;
  onEdit: (i: number) => void;
  sort: string;
  setSort: (s: string) => void;
  alignNode: React.ReactNode;
}

export function MappingTable({ rows, total, conflicts, expanded, onToggle, onAccept, onEdit, sort, setSort, alignNode }: Props) {
  const headSort = (k: string) => {
    if (k === "conf") setSort(sort === "conf-desc" ? "conf-asc" : "conf-desc");
    else setSort(k);
  };
  return (
    <div className="panel">
      <div className="gscroll">
        <table>
          <thead>
            <tr>
              <th className="nosort" style={{ width: 30 }} />
              <th onClick={() => headSort("name")}>Source variable</th>
              <th className="nosort">Region</th>
              <th className="nosort">Maps to</th>
              <th onClick={() => headSort("type")}>Type</th>
              <th onClick={() => headSort("conf")}>Confidence</th>
              <th onClick={() => headSort("status")}>Status</th>
              <th className="nosort">Source</th>
              <th className="nosort" style={{ width: 96 }} />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={9} style={{ padding: 26, textAlign: "center", color: "var(--muted)" }}>No variables match these filters.</td></tr>
            )}
            {rows.map(([r, i]) => {
              const canExpand = r.action === "split";
              const open = expanded[i];
              return (
                <React.Fragment key={i}>
                  <tr className={"main" + (conflicts.has(i) ? " conflict" : "")}>
                    <td onClick={() => canExpand && onToggle(i)} style={{ cursor: canExpand ? "pointer" : "default" }}>
                      {canExpand && (
                        <svg className={"caret" + (open ? " open" : "")} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--faint)" strokeWidth="2.4"><path d="M9 6l6 6-6 6" /></svg>
                      )}
                    </td>
                    <td>
                      <div className="vcell">
                        <span className={"cat " + r.category} />
                        <div>
                          <div className="vname">{humanize(r.source_var)}{conflicts.has(i) && <span className="warnpill">⚠ dup target</span>}</div>
                          <span className="vtok">{r.source_var}</span>
                        </div>
                      </div>
                    </td>
                    <td><span className="reg">{r.source_region}</span></td>
                    <td>{targetCell(r)}</td>
                    <td><span className={"type " + r.action}>{r.action}{r.action === "split" && r.kind ? " · " + r.kind : ""}</span></td>
                    <td>
                      <div className="conf">
                        <div className="tr"><i style={{ width: Math.round(r.confidence * 100) + "%", background: confColor(r.confidence) }} /></div>
                        <b>{Math.round(r.confidence * 100)}</b>
                      </div>
                    </td>
                    <td><span className={"st " + r.status}><span className="d" />{r.status}</span></td>
                    <td><span className="prov">{r.provenance}</span></td>
                    <td>
                      <div className="rowbtns">
                        {r.status !== "confirmed" && (
                          <button className="mini ok" title="Accept" onClick={() => onAccept(i)}>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6L9 17l-5-5" /></svg>
                          </button>
                        )}
                        <button className="mini" title="Edit mapping" onClick={() => onEdit(i)}>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                  {open && canExpand && (
                    <tr className="detail">
                      <td colSpan={9}>
                        <div className="detwrap">
                          <h4>Split targets{r.kind === "temporal" && r.breakpoint ? " · breakpoint " + r.breakpoint : ""}</h4>
                          {r.targets.map((t, ti) => {
                            const on = !!(t.active || t.percent > 0);
                            return (
                              <div key={ti} className={"targ" + (on ? "" : " off")}>
                                <span className="rg mono">{t.region}</span>
                                <Sparkline series={t.series} active={on} />
                                <span className={"badge " + (on ? "on" : "zero")}>{on ? "active" : "zero"}</span>
                                <span className="w">{weightLabel(t)}</span>
                              </div>
                            );
                          })}
                          <div className="detnote">{splitNote(r.kind)}</div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="foot"><span>{rows.length} of {total} variables</span>{alignNode}</div>
    </div>
  );
}
