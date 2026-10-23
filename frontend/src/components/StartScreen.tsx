import { useEffect, useState } from "react";
import { api } from "../api";

export function StartScreen({ onOpen }: { onOpen: (env: string, bmc: string, refresh: string) => Promise<void> }) {
  const [envs, setEnvs] = useState<string[]>([]);
  const [env, setEnv] = useState("");
  const [bmcs, setBmcs] = useState<string[]>([]);
  const [bmc, setBmc] = useState("");
  const [refs, setRefs] = useState<string[]>([]);
  const [refresh, setRefresh] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.environments()
      .then((e) => { const n = e.map((x) => x.name); setEnvs(n); setEnv(n[0] || ""); })
      .catch((e) => setErr("Can’t reach the backend — is the app running? (" + e.message + ")"));
  }, []);
  useEffect(() => {
    if (!env) return;
    api.bmcs(env).then((r) => { setBmcs(r.bmcs); setBmc(r.bmcs[0] || ""); }).catch(() => setBmcs([]));
  }, [env]);
  useEffect(() => {
    if (!env || !bmc) return;
    api.refreshes(env, bmc).then((r) => { setRefs(r.refreshes); setRefresh(r.refreshes[0] || ""); }).catch(() => setRefs([]));
  }, [env, bmc]);

  async function open() {
    if (!bmc || !refresh) { setErr("Pick a BMC and a refresh."); return; }
    setBusy(true); setErr(null);
    try { await onOpen(env, bmc, refresh); } catch (e: any) { setErr("Could not open: " + e.message); setBusy(false); }
  }

  return (
    <div className="overlay">
      <div className="card" style={{ width: "min(420px,92vw)", display: "flex", flexDirection: "column", gap: 12 }}>
        <h3 style={{ fontSize: 15 }}>Open a mapping workspace</h3>
        <div className="fld"><label>Environment</label>
          <select style={{ width: "100%" }} value={env} onChange={(e) => setEnv(e.target.value)}>
            {envs.map((n) => <option key={n} value={n}>{n.toUpperCase()}</option>)}
          </select>
        </div>
        <div className="fld"><label>Brand · Market (BMC)</label>
          <select style={{ width: "100%" }} value={bmc} onChange={(e) => setBmc(e.target.value)}>
            {bmcs.length ? bmcs.map((n) => <option key={n} value={n}>{n}</option>) : <option value="">(none)</option>}
          </select>
        </div>
        <div className="fld"><label>Model refresh</label>
          <select style={{ width: "100%" }} value={refresh} onChange={(e) => setRefresh(e.target.value)}>
            {refs.length ? refs.map((n) => <option key={n} value={n}>{n}</option>) : <option value="">(none)</option>}
          </select>
        </div>
        {err && <div style={{ color: "var(--bad)", fontSize: 12 }}>{err}</div>}
        <button className="commit" style={{ width: "100%", justifyContent: "center" }} disabled={busy} onClick={open}>
          {busy ? "Opening…" : "Open workspace"}
        </button>
      </div>
    </div>
  );
}
