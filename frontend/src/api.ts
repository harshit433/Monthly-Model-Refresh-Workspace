import type { Analysis, ExtendResult, Insights, Proposal, Summary } from "./types";

const BASE: string = (import.meta as any).env?.VITE_API_BASE ?? "";

async function j<T>(url: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(BASE + url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return (await r.json()) as T;
}

export const api = {
  environments: () => j<Array<{ name: string; catalog: string }>>("/environments"),
  bmcs: (env: string) => j<{ bmcs: string[] }>(`/bmcs?env=${encodeURIComponent(env)}`),
  refreshes: (env: string, bmc: string) =>
    j<{ refreshes: string[] }>(`/refreshes?env=${encodeURIComponent(env)}&bmc=${encodeURIComponent(bmc)}`),
  createSession: (body: { env: string; bmc: string; refresh: string }) =>
    j<Summary>("/sessions", { method: "POST", body: JSON.stringify(body) }),
  getSummary: (id: string) => j<Summary>(`/sessions/${id}`),
  getMapping: (id: string, domain: string) =>
    j<{ domain: string; proposals: Proposal[] }>(`/sessions/${id}/mapping/${domain}`),
  patchMapping: (id: string, domain: string, proposals: Proposal[]) =>
    j<{ changed_targets: unknown[]; analysis: Analysis }>(`/sessions/${id}/mapping/${domain}`, {
      method: "PATCH",
      body: JSON.stringify({ proposals }),
    }),
  extend: (id: string) => j<ExtendResult>(`/sessions/${id}/extend`, { method: "POST", body: "{}" }),
  insights: (id: string) => j<Insights>(`/sessions/${id}/insights`),
  commit: (id: string) =>
    j<{ committed: boolean; baseline_paths: Record<string, string> }>(`/sessions/${id}/commit`, {
      method: "POST",
      body: "{}",
    }),
};
