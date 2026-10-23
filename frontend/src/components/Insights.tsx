import type { Insights as InsightsData } from "../types";
import { fmt, short } from "../util";

function Trend({ dates, values }: { dates: string[]; values: number[] }) {
  const w = 680, h = 150, L = 34, R = 10, T = 10, B = 22, pw = w - L - R, ph = h - T - B, n = values.length;
  const mx = Math.max(...values, 1), mn = Math.min(...values, 0);
  const X = (i: number) => L + pw * (i / ((n - 1) || 1));
  const Y = (v: number) => T + ph * (1 - (v - mn) / ((mx - mn) || 1));
  const d = values.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
  const ar = d + `L${X(n - 1).toFixed(1)},${Y(mn).toFixed(1)}L${X(0).toFixed(1)},${Y(mn).toFixed(1)}Z`;
  const ticks = [0, Math.floor(n / 2), n - 1];
  return (
    <svg className="trendsvg" viewBox={`0 0 ${w} ${h}`}>
      <path d={ar} fill="var(--accent)" opacity={0.08} />
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth={1.8} />
      <circle cx={X(n - 1)} cy={Y(values[n - 1])} r={3.2} fill="var(--accent)" />
      {ticks.map((i) => (
        <text key={i} x={X(i)} y={h - 6} fontSize={9} fill="var(--faint)" textAnchor="middle" fontFamily="var(--mono)">{(dates[i] || "").slice(5)}</text>
      ))}
      <text x={L - 5} y={Y(mx) + 3} fontSize={9} fill="var(--faint)" textAnchor="end" fontFamily="var(--mono)">{fmt(mx)}</text>
    </svg>
  );
}

export function Insights({ data, onExtend }: { data: InsightsData; onExtend: () => void }) {
  const topv = data.by_variable.slice(0, 7);
  const maxc = Math.max(...data.by_variable.map((r) => r.contribution), 1);
  const maxr = Math.max(...data.by_region.map((r) => r.contribution), 1);
  const rois = data.by_variable.filter((r) => r.roi != null).slice(0, 8);
  const scope = data.scope === "combined" ? "History + new month" : "Historical only";
  return (
    <div>
      <div className="ins-tiles">
        <div className="card"><div className="muted" style={{ fontSize: 11, fontWeight: 600 }}>Total contribution</div><div style={{ fontSize: 24, fontWeight: 700 }} className="tnum">{fmt(data.total)}</div></div>
        <div className="card"><div className="muted" style={{ fontSize: 11, fontWeight: 600 }}>Scope</div><div style={{ fontSize: 15, fontWeight: 700, marginTop: 4 }}>{scope}</div><div className="muted" style={{ fontSize: 11 }}>{data.trend.dates.length} weeks</div></div>
        <div className="card"><div className="muted" style={{ fontSize: 11, fontWeight: 600 }}>Variables</div><div style={{ fontSize: 24, fontWeight: 700 }} className="tnum">{data.by_variable.length}</div></div>
        <div className="card"><div className="muted" style={{ fontSize: 11, fontWeight: 600 }}>Top region</div><div style={{ fontSize: 15, fontWeight: 700, marginTop: 4 }}>{data.by_region[0]?.region || "—"}</div><div className="muted" style={{ fontSize: 11 }}>{data.by_region[0] ? data.by_region[0].pct + "%" : ""}</div></div>
      </div>

      <div className="ins-grid" style={{ marginTop: 12 }}>
        <div className="card">
          <div className="ch"><h3>Top contributors</h3></div>
          {topv.map((r, i) => (
            <div className="bar-row" key={i}>
              <div className="nm">{short(r.var)}<span className="mono">{r.region}</span></div>
              <div className="bg"><i style={{ width: Math.round((r.contribution / maxc) * 100) + "%" }} /></div>
              <div className="val">{fmt(r.contribution)} · {r.pct}%</div>
            </div>
          ))}
        </div>
        <div className="card">
          <div className="ch"><h3>By region</h3></div>
          {data.by_region.map((r, i) => (
            <div className="bar-row" key={i}>
              <div className="nm mono">{r.region}</div>
              <div className="bg"><i style={{ width: Math.round((r.contribution / maxr) * 100) + "%" }} /></div>
              <div className="val">{r.pct}%</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <div className="ch">
          <h3>Contribution over time</h3>
          <div className="grow" />
          <button className="btn key" onClick={onExtend}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M12 5v14M5 12h14" /></svg>
            Extend +1 month
          </button>
        </div>
        <Trend dates={data.trend.dates} values={data.trend.values} />
      </div>

      {rois.length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="ch"><h3>ROI · contribution ÷ spend</h3></div>
          <table className="roi">
            <thead><tr><th>Variable</th><th>Region</th><th>Contribution</th><th>Spend</th><th>ROI</th></tr></thead>
            <tbody>
              {rois.map((r, i) => (
                <tr key={i}>
                  <td>{short(r.var)}</td>
                  <td className="mono">{r.region}</td>
                  <td className="tnum">{fmt(r.contribution)}</td>
                  <td className="tnum">{fmt(r.invest || 0)}</td>
                  <td className="r">{(r.roi || 0).toFixed(2)}×</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
