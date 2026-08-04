"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api";

const API = getApiBaseUrl();
const DK = "demo-anya";
const hdrs = { "X-Demo-User-Key": DK };

type OpsSnapshot = {
  db_aggregates: Record<string, number>;
  in_memory: { counters: Record<string, number>; uptime_seconds: number; latency_stats: Record<string, Record<string, number>> };
  uptime_seconds: number;
};

type AlertEventRow = {
  id: string;
  severity: string;
  status: string;
  message: string;
  created_at: string;
};

export default function ObservabilityPage() {
  const [snapshot, setSnapshot] = useState<OpsSnapshot | null>(null);
  const [metricsText, setMetricsText] = useState("");
  const [alerts, setAlerts] = useState<AlertEventRow[]>([]);

  const load = useCallback(async () => {
    const [snap, metrics, al] = await Promise.all([
      fetch(`${API}/api/v1/observability/snapshot`, { headers: hdrs }).then((r) => r.json()),
      fetch(`${API}/metrics`).then((r) => r.text()),
      fetch(`${API}/api/v1/alerts/events?limit=20`, { headers: hdrs }).then((r) => r.json()),
    ]);
    setSnapshot(snap);
    setMetricsText(metrics);
    setAlerts(al as AlertEventRow[]);
  }, []);

  useEffect(() => {
    void load();
    const iv = setInterval(() => { void load(); }, 15000);
    return () => clearInterval(iv);
  }, [load]);

  const seedRules = async () => {
    await fetch(`${API}/api/v1/alerts/rules/seed`, { method: "POST", headers: hdrs });
    load();
  };

  const fmtUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
  };

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="font-display text-2xl text-slate-900 mb-6">Observability</h1>

      {snapshot && (
        <>
          <section className="mb-8">
            <h2 className="text-lg font-semibold text-slate-800 mb-3">System Overview</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg border p-4">
                <p className="text-xs text-slate-500">Uptime</p>
                <p className="text-xl font-semibold">{fmtUptime(snapshot.uptime_seconds)}</p>
              </div>
              {Object.entries(snapshot.db_aggregates).map(([k, v]) => (
                <div key={k} className="bg-white rounded-lg border p-4">
                  <p className="text-xs text-slate-500">{k.replace(/_/g, " ")}</p>
                  <p className="text-xl font-semibold">{v}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="mb-8">
            <h2 className="text-lg font-semibold text-slate-800 mb-3">In-Memory Counters</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(snapshot.in_memory.counters).map(([k, v]) => (
                <div key={k} className="bg-white rounded-lg border p-4">
                  <p className="text-xs text-slate-500">{k.replace(/_/g, " ")}</p>
                  <p className="text-lg font-semibold">{v}</p>
                </div>
              ))}
            </div>
          </section>

          {Object.keys(snapshot.in_memory.latency_stats).length > 0 && (
            <section className="mb-8">
              <h2 className="text-lg font-semibold text-slate-800 mb-3">Latency Stats</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead><tr className="border-b text-left text-slate-600">
                    <th className="pb-2">Operation</th><th className="pb-2">Avg (ms)</th><th className="pb-2">P95 (ms)</th><th className="pb-2">P99 (ms)</th><th className="pb-2">Count</th>
                  </tr></thead>
                  <tbody>
                    {Object.entries(snapshot.in_memory.latency_stats).map(([k, v]) => (
                      <tr key={k} className="border-b"><td className="py-1">{k}</td><td>{v.avg}</td><td>{v.p95}</td><td>{v.p99}</td><td>{v.count}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}

      <section className="mb-8">
        <div className="flex items-center gap-4 mb-3">
          <h2 className="text-lg font-semibold text-slate-800">Alert Events</h2>
          <button onClick={seedRules} className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700">Seed Alert Rules</button>
        </div>
        {alerts.length === 0 ? (
          <p className="text-slate-500 text-sm">No alert events.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead><tr className="border-b text-left text-slate-600">
                <th className="pb-2">Severity</th><th className="pb-2">Status</th><th className="pb-2">Message</th><th className="pb-2">Time</th>
              </tr></thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id} className="border-b">
                    <td className="py-1"><span className={`px-2 py-0.5 rounded text-xs ${a.severity === "critical" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}`}>{a.severity}</span></td>
                    <td>{a.status}</td><td className="max-w-xs truncate">{a.message}</td><td>{new Date(a.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-slate-800 mb-3">Prometheus Metrics</h2>
        <pre className="bg-slate-50 rounded-lg border p-4 text-xs text-slate-700 overflow-x-auto max-h-64">{metricsText || "Loading..."}</pre>
      </section>

      <button onClick={load} className="rounded bg-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-300">Refresh</button>
    </main>
  );
}
