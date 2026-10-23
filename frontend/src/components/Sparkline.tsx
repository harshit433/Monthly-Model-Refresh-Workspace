import { confColor, sparklinePath } from "../util";

export function Sparkline({ series, active }: { series?: number[] | null; active: boolean }) {
  if (!series || !series.length) return null;
  const { d, flat, w, h } = sparklinePath(series);
  return (
    <svg className="spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      {flat ? (
        <line x1={0} y1={h - 1.5} x2={w} y2={h - 1.5} stroke="var(--faint)" strokeWidth={1.2} strokeDasharray="2 2" />
      ) : (
        <path d={d} fill="none" stroke={active ? confColor(1) : "var(--faint)"} strokeWidth={1.6} />
      )}
    </svg>
  );
}
