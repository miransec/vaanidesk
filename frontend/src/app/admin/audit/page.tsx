"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api";

const API = getApiBaseUrl();
const DK = "demo-anya";
const hdrs = { "X-Demo-User-Key": DK };

type AuditEntry = {
  id: string;
  action: string;
  actor: string;
  resource_type: string | null;
  resource_id: string | null;
  detail: string;
  created_at: string;
};

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    params.set("limit", "200");
    if (actionFilter) params.set("action", actionFilter);
    if (resourceFilter) params.set("resource_type", resourceFilter);
    const res = await fetch(`${API}/api/v1/audit?${params}`, { headers: hdrs });
    setEntries(await res.json());
  }, [actionFilter, resourceFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="font-display text-2xl text-slate-900 mb-6">Audit Log</h1>

      <div className="flex gap-4 mb-6">
        <input
          type="text"
          placeholder="Filter by action..."
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="rounded border px-3 py-1.5 text-sm w-48"
        />
        <input
          type="text"
          placeholder="Filter by resource type..."
          value={resourceFilter}
          onChange={(e) => setResourceFilter(e.target.value)}
          className="rounded border px-3 py-1.5 text-sm w-48"
        />
        <button onClick={load} className="rounded bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700">
          Apply Filters
        </button>
      </div>

      {entries.length === 0 ? (
        <p className="text-slate-500">No audit log entries found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b text-left text-slate-600">
                <th className="pb-2 pr-4">Time</th>
                <th className="pb-2 pr-4">Action</th>
                <th className="pb-2 pr-4">Actor</th>
                <th className="pb-2 pr-4">Resource</th>
                <th className="pb-2">Detail</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-b hover:bg-slate-50">
                  <td className="py-2 pr-4 text-slate-500 whitespace-nowrap">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-4"><span className="px-2 py-0.5 bg-slate-100 rounded text-xs">{e.action}</span></td>
                  <td className="py-2 pr-4">{e.actor}</td>
                  <td className="py-2 pr-4 text-slate-500">{e.resource_type ? `${e.resource_type}/${e.resource_id?.slice(0, 8)}` : "—"}</td>
                  <td className="py-2 max-w-md truncate">{e.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-slate-400 mt-8">Showing up to 200 most recent entries. No secrets or full bodies are stored in audit records.</p>
    </main>
  );
}
