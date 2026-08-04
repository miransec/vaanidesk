"use client";

import { useEffect, useState } from "react";
import {
  getApiBaseUrl,
  type EvalDatasetOut,
  type EvalRunOut,
} from "@/lib/api";

const API = getApiBaseUrl();
const DK = "demo-anya";
const hdrs = { "X-Demo-User-Key": DK };

export default function EvaluationsPage() {
  const [datasets, setDatasets] = useState<EvalDatasetOut[]>([]);
  const [runs, setRuns] = useState<EvalRunOut[]>([]);
  const [running, setRunning] = useState(false);
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null);

  const load = async () => {
    const [ds, rs] = await Promise.all([
      fetch(`${API}/api/v1/evaluations/datasets`, { headers: hdrs }).then((r) => r.json()),
      fetch(`${API}/api/v1/evaluations/runs?limit=20`, { headers: hdrs }).then((r) => r.json()),
    ]);
    setDatasets(ds);
    setRuns(rs);
  };

  useEffect(() => { load(); }, []);

  const seedDataset = async () => {
    await fetch(`${API}/api/v1/evaluations/datasets/seed`, { method: "POST", headers: hdrs });
    load();
  };

  const startRun = async () => {
    setRunning(true);
    await fetch(`${API}/api/v1/evaluations/runs`, {
      method: "POST",
      headers: { ...hdrs, "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_name: "vaanidesk-core-v1", provider: "mock", seed: 42 }),
    });
    setRunning(false);
    load();
  };

  const exportRun = async (id: string, fmt: string) => {
    const res = await fetch(`${API}/api/v1/evaluations/runs/${id}/export?fmt=${fmt}`, { headers: hdrs });
    const text = await res.text();
    const blob = new Blob([text], { type: fmt === "json" ? "application/json" : "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `eval-${id}.${fmt === "json" ? "json" : "md"}`;
    a.click();
  };

  const compareRun = async (id: string) => {
    const res = await fetch(`${API}/api/v1/evaluations/runs/${id}/compare`, { headers: hdrs });
    setComparison(await res.json());
  };

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="font-display text-2xl text-slate-900 mb-6">Evaluations</h1>

      <section className="mb-8">
        <div className="flex items-center gap-4 mb-4">
          <h2 className="text-lg font-semibold text-slate-800">Datasets</h2>
          <button onClick={seedDataset} className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700">
            Seed Dataset
          </button>
        </div>
        {datasets.length === 0 ? (
          <p className="text-slate-500">No datasets. Click Seed Dataset to create one.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead><tr className="border-b text-left text-slate-600">
                <th className="pb-2">Name</th><th className="pb-2">Cases</th><th className="pb-2">Version</th><th className="pb-2">Created</th>
              </tr></thead>
              <tbody>
                {datasets.map((d) => (
                  <tr key={d.id} className="border-b"><td className="py-2">{d.name}</td><td>{d.case_count}</td><td>v{d.version}</td><td>{new Date(d.created_at).toLocaleDateString()}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="mb-8">
        <div className="flex items-center gap-4 mb-4">
          <h2 className="text-lg font-semibold text-slate-800">Runs</h2>
          <button onClick={startRun} disabled={running} className="rounded bg-green-600 px-3 py-1 text-sm text-white hover:bg-green-700 disabled:opacity-50">
            {running ? "Running..." : "Start Eval Run"}
          </button>
        </div>
        {runs.length === 0 ? (
          <p className="text-slate-500">No evaluation runs yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead><tr className="border-b text-left text-slate-600">
                <th className="pb-2">Name</th><th className="pb-2">Status</th><th className="pb-2">Provider</th>
                <th className="pb-2">Pass Rate</th><th className="pb-2">Security</th><th className="pb-2">Actions</th>
              </tr></thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} className="border-b">
                    <td className="py-2">{r.run_name}</td>
                    <td><span className={`px-2 py-0.5 rounded text-xs ${r.status === "completed" ? "bg-green-100 text-green-700" : r.status === "failed" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}`}>{r.status}</span></td>
                    <td>{r.provider}</td>
                    <td>{r.pass_rate != null ? `${r.pass_rate.toFixed(1)}%` : "—"}</td>
                    <td>{r.security_failures > 0 ? <span className="text-red-600 font-bold">{r.security_failures} failures</span> : <span className="text-green-600">Clean</span>}</td>
                    <td className="flex gap-2 py-2">
                      <button onClick={() => exportRun(r.id, "json")} className="text-xs text-blue-600 hover:underline">JSON</button>
                      <button onClick={() => exportRun(r.id, "markdown")} className="text-xs text-blue-600 hover:underline">MD</button>
                      <button onClick={() => compareRun(r.id)} className="text-xs text-blue-600 hover:underline">Compare</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {comparison && (
        <section className="mb-8 p-4 bg-slate-50 rounded-lg border">
          <h2 className="text-lg font-semibold text-slate-800 mb-2">Run Comparison</h2>
          <pre className="text-xs text-slate-700 overflow-x-auto">{JSON.stringify(comparison, null, 2)}</pre>
          <button onClick={() => setComparison(null)} className="mt-2 text-xs text-slate-500 hover:underline">Close</button>
        </section>
      )}

      <p className="text-xs text-slate-400 mt-8">Mock provider evaluation — scores reflect deterministic mock behavior, not real LLM quality.</p>
    </main>
  );
}
