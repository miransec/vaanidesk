"use client";

import { useCallback, useEffect, useState } from "react";
import {
  type ChannelConnectionOut,
  type HandoffQueueItemOut,
  type InboundEventOut,
  type OutboundMessageOut,
  listChannelConnections,
  listFailedOutbound,
  listHandoffQueue,
  listInboundEvents,
  seedChannelConnections,
  simulateEmailEvent,
  simulateWhatsAppEvent,
  toggleChannelConnection,
} from "@/lib/api";

const DEMO_KEY = "demo-anya";

export default function ChannelsPage() {
  const [connections, setConnections] = useState<ChannelConnectionOut[]>([]);
  const [events, setEvents] = useState<InboundEventOut[]>([]);
  const [failed, setFailed] = useState<OutboundMessageOut[]>([]);
  const [handoff, setHandoff] = useState<HandoffQueueItemOut[]>([]);
  const [simForm, setSimForm] = useState({ channel: "email", text: "" });
  const [status, setStatus] = useState("");

  const load = useCallback(async () => {
    try {
      const [c, e, f, h] = await Promise.all([
        listChannelConnections(DEMO_KEY),
        listInboundEvents(DEMO_KEY),
        listFailedOutbound(DEMO_KEY),
        listHandoffQueue(DEMO_KEY),
      ]);
      setConnections(c);
      setEvents(e);
      setFailed(f);
      setHandoff(h);
    } catch {
      await seedChannelConnections(DEMO_KEY);
      const [c, e, f, h] = await Promise.all([
        listChannelConnections(DEMO_KEY),
        listInboundEvents(DEMO_KEY),
        listFailedOutbound(DEMO_KEY),
        listHandoffQueue(DEMO_KEY),
      ]);
      setConnections(c);
      setEvents(e);
      setFailed(f);
      setHandoff(h);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleToggle(id: string, enabled: boolean) {
    await toggleChannelConnection(DEMO_KEY, id, !enabled);
    load();
  }

  async function handleSimulate() {
    if (!simForm.text.trim()) return;
    setStatus("Sending...");
    try {
      if (simForm.channel === "email") {
        await simulateEmailEvent(DEMO_KEY, {
          from_email: "test@example.com",
          from_display: "Simulator",
          subject: "Test",
          text_body: simForm.text,
        });
      } else {
        await simulateWhatsAppEvent(DEMO_KEY, {
          from_phone: "+919876543210",
          display_name: "WA Simulator",
          text: simForm.text,
        });
      }
      setStatus("Sent ✓");
      setSimForm((f) => ({ ...f, text: "" }));
      setTimeout(load, 500);
    } catch (e: unknown) {
      setStatus(`Error: ${e instanceof Error ? e.message : "unknown"}`);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 space-y-8">
      <h1 className="font-display text-2xl text-slate-900">Channels</h1>
      <p className="text-sm text-slate-500">
        Omnichannel management — connections, simulator, events, delivery, handoff queue.
        <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">mock/simulator</span>
      </p>

      {/* Connections */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 mb-2">Channel Connections</h2>
        <div className="rounded border border-slate-200 divide-y divide-slate-100">
          {connections.map((c) => (
            <div key={c.id} className="flex items-center justify-between px-4 py-3">
              <div>
                <span className="font-medium text-slate-800">{c.display_name}</span>
                <span className="ml-2 text-xs text-slate-500">{c.channel_type}</span>
              </div>
              <button
                onClick={() => handleToggle(c.id, c.enabled)}
                className={`rounded px-3 py-1 text-xs font-medium ${
                  c.enabled
                    ? "bg-green-100 text-green-800"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                {c.enabled ? "Enabled" : "Disabled"}
              </button>
            </div>
          ))}
          {connections.length === 0 && (
            <div className="px-4 py-6 text-center text-sm text-slate-400">
              No connections. They will be seeded on first load.
            </div>
          )}
        </div>
      </section>

      {/* Simulator */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 mb-2">
          Simulator
          <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">mock</span>
        </h2>
        <div className="flex gap-2 items-end">
          <select
            value={simForm.channel}
            onChange={(e) => setSimForm((f) => ({ ...f, channel: e.target.value }))}
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="email">Email</option>
            <option value="whatsapp">WhatsApp</option>
          </select>
          <input
            type="text"
            value={simForm.text}
            onChange={(e) => setSimForm((f) => ({ ...f, text: e.target.value }))}
            placeholder="Message text..."
            className="flex-1 rounded border border-slate-300 px-3 py-1.5 text-sm"
            onKeyDown={(e) => e.key === "Enter" && handleSimulate()}
          />
          <button
            onClick={handleSimulate}
            className="rounded bg-slate-800 px-4 py-1.5 text-sm text-white hover:bg-slate-700"
          >
            Send
          </button>
        </div>
        {status && <p className="mt-1 text-xs text-slate-500">{status}</p>}
      </section>

      {/* Inbound Events */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 mb-2">Inbound Events</h2>
        <div className="rounded border border-slate-200 overflow-auto max-h-64">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs text-slate-500">
              <tr>
                <th className="px-3 py-2">Event ID</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Received</th>
                <th className="px-3 py-2">Metadata</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {events.map((ev) => (
                <tr key={ev.id}>
                  <td className="px-3 py-2 font-mono text-xs">{ev.external_event_id.slice(0, 20)}...</td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs ${
                      ev.status === "processed" ? "bg-green-100 text-green-800" :
                      ev.status === "duplicate" ? "bg-yellow-100 text-yellow-800" :
                      "bg-red-100 text-red-800"
                    }`}>{ev.status}</span>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-500">{new Date(ev.received_at).toLocaleTimeString()}</td>
                  <td className="px-3 py-2 text-xs text-slate-500">{ev.safe_metadata ? JSON.stringify(ev.safe_metadata).slice(0, 40) : "—"}</td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr><td colSpan={4} className="px-3 py-6 text-center text-slate-400">No events yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Failed Deliveries */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 mb-2">Failed Deliveries</h2>
        {failed.length === 0 ? (
          <p className="text-sm text-slate-400">No failed deliveries</p>
        ) : (
          <div className="rounded border border-slate-200 divide-y divide-slate-100">
            {failed.map((m) => (
              <div key={m.id} className="flex items-center justify-between px-4 py-2 text-sm">
                <span className="font-mono text-xs">{m.id.slice(0, 8)}</span>
                <span className="text-xs text-slate-500">{m.status}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Handoff Queue */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 mb-2">Handoff Queue</h2>
        {handoff.length === 0 ? (
          <p className="text-sm text-slate-400">No items in queue</p>
        ) : (
          <div className="rounded border border-slate-200 divide-y divide-slate-100">
            {handoff.map((h) => (
              <div key={h.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <span className="text-sm text-slate-800">{h.summary.slice(0, 60)}</span>
                  <span className="ml-2 text-xs text-slate-500">{h.status}</span>
                </div>
                <span className="text-xs text-slate-400">{new Date(h.created_at).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
