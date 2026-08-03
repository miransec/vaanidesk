"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  ConfirmationOut,
  DemoUser,
  MessageOut,
  WorkflowOut,
  confirmAction,
  getApiBaseUrl,
  getConversation,
  listConversations,
  listDemoUsers,
  sendMessage,
} from "@/lib/api";

type ChatRow = MessageOut & { providerLabel?: string };

export function ChatPanel() {
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [demoKey, setDemoKey] = useState("demo-anya");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatRow[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [providerNote, setProviderNote] = useState(
    "Phase 3 controlled workflow + knowledge RAG (heuristic — not a production model)",
  );
  const [workflow, setWorkflow] = useState<WorkflowOut | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<ConfirmationOut | null>(null);
  const [showDevDetails, setShowDevDetails] = useState(false);

  const selectedUser = useMemo(
    () => users.find((u) => u.demo_key === demoKey) ?? null,
    [users, demoKey],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const demoUsers = await listDemoUsers();
        if (cancelled) return;
        setUsers(demoUsers);
        if (demoUsers.length && !demoUsers.some((u) => u.demo_key === demoKey)) {
          setDemoKey(demoUsers[0].demo_key);
        }
      } catch (err) {
        if (!cancelled) {
          setBootError(
            err instanceof Error
              ? err.message
              : "Could not load demo users. Is the backend running?",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [demoKey]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!demoKey || bootError) return;
      try {
        const convos = await listConversations(demoKey);
        if (cancelled) return;
        if (convos.length === 0) {
          setConversationId(null);
          setMessages([]);
          return;
        }
        const latest = convos[0];
        setConversationId(latest.id);
        const detail = await getConversation(demoKey, latest.id);
        if (cancelled) return;
        setMessages(detail.messages);
      } catch (err) {
        if (!cancelled) {
          setSendError(err instanceof Error ? err.message : "Failed to load conversations");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [demoKey, bootError]);

  function applyWorkflow(next: WorkflowOut | null | undefined) {
    if (!next) {
      setWorkflow(null);
      setPendingConfirmation(null);
      return;
    }
    setWorkflow(next);
    setPendingConfirmation(next.confirmation ?? null);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim() || loading) return;
    setLoading(true);
    setSendError(null);
    try {
      const result = await sendMessage({
        demoKey,
        content: input.trim(),
        conversationId,
      });
      setConversationId(result.conversation_id);
      setMessages((prev) => [
        ...prev,
        result.user_message,
        {
          ...result.assistant_message,
          providerLabel: `${result.provider.provider}/${result.provider.model}`,
        },
      ]);
      applyWorkflow(result.workflow);
      setProviderNote(
        result.provider.is_mock
          ? `Workflow active — ${result.provider.model}${
              result.provider.language_hint ? ` · lang: ${result.provider.language_hint}` : ""
            }`
          : `${result.provider.provider}/${result.provider.model}`,
      );
      setInput("");
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Send failed");
    } finally {
      setLoading(false);
    }
  }

  async function onConfirm(approved: boolean) {
    if (!pendingConfirmation || loading) return;
    setLoading(true);
    setSendError(null);
    try {
      const result = await confirmAction({
        demoKey,
        confirmationToken: pendingConfirmation.token,
        approved,
      });
      setConversationId(result.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          ...result.assistant_message,
          providerLabel: `${result.provider.provider}/${result.provider.model}`,
        },
      ]);
      applyWorkflow(result.workflow);
      setPendingConfirmation(null);
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Confirmation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6 md:py-10">
      <header className="space-y-2 border-b border-teal-900/10 pb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-800">VaaniDesk</p>
        <h1 className="font-display text-3xl text-slate-900 md:text-4xl">Support chat</h1>
        <p className="text-sm text-slate-600">
          Phase 3 demo auth via <code className="rounded bg-slate-100 px-1">X-Demo-User-Key</code>.
          Not production authentication. API: {getApiBaseUrl()}
        </p>
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-950">{providerNote}</p>
      </header>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="flex flex-1 flex-col gap-1 text-sm text-slate-700">
          Demo user
          <select
            className="rounded-md border border-slate-300 bg-white px-3 py-2"
            value={demoKey}
            onChange={(e) => {
              setConversationId(null);
              setMessages([]);
              setWorkflow(null);
              setPendingConfirmation(null);
              setDemoKey(e.target.value);
            }}
          >
            {users.map((user) => (
              <option key={user.id} value={user.demo_key}>
                {user.display_name} ({user.demo_key})
              </option>
            ))}
          </select>
        </label>
        {selectedUser ? (
          <p className="text-xs text-slate-500 sm:pb-2">
            {selectedUser.email}
            <br />
            id: {selectedUser.id}
          </p>
        ) : null}
      </div>

      {workflow ? (
        <div className="grid gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700 sm:grid-cols-2">
          <p>
            Language: <strong>{workflow.detected_language ?? "—"}</strong> ({workflow.script ?? "—"})
          </p>
          <p>
            Intent: <strong>{workflow.intent ?? "—"}</strong>
            {workflow.intent_confidence != null
              ? ` (${workflow.intent_confidence.toFixed(2)})`
              : ""}
          </p>
          <p>
            Tool: <strong>{workflow.selected_tool ?? "—"}</strong>
          </p>
          <p>
            Tool status: <strong>{workflow.tool_execution_status ?? "—"}</strong>
          </p>
          {workflow.clarification_required ? (
            <p className="sm:col-span-2 text-amber-900">Clarification required</p>
          ) : null}
          {workflow.escalation_required ? (
            <p className="sm:col-span-2 text-rose-900">
              Escalation queued
              {workflow.escalation_reason ? ` — ${workflow.escalation_reason}` : ""}
            </p>
          ) : null}
          {workflow.retrieval_strategy ? (
            <p>
              Retrieval: <strong>{workflow.retrieval_strategy}</strong>
              {workflow.retrieval_confidence != null
                ? ` (${workflow.retrieval_confidence.toFixed(3)})`
                : ""}
            </p>
          ) : null}
          {workflow.no_answer ? (
            <p className="sm:col-span-2 text-amber-900">
              No-answer
              {workflow.no_answer_reason ? ` — ${workflow.no_answer_reason}` : ""}
            </p>
          ) : null}
          {workflow.citations && workflow.citations.length > 0 ? (
            <div className="sm:col-span-2 space-y-1">
              <p className="font-medium">Citations</p>
              <ul className="text-xs">
                {workflow.citations.map((c) => (
                  <li key={c.chunk_id}>
                    {c.document_title} v{c.document_version} · {c.section_label} ·{" "}
                    {c.score.toFixed(3)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <label className="sm:col-span-2 flex items-center gap-2 text-xs text-slate-500">
            <input
              type="checkbox"
              checked={showDevDetails}
              onChange={(e) => setShowDevDetails(e.target.checked)}
            />
            Developer details
          </label>
          {showDevDetails && workflow.trace_id ? (
            <p className="sm:col-span-2 font-mono text-xs">trace_id: {workflow.trace_id}</p>
          ) : null}
          {showDevDetails && workflow.retrieval_trace_id ? (
            <p className="sm:col-span-2 font-mono text-xs">
              retrieval_trace_id: {workflow.retrieval_trace_id}
            </p>
          ) : null}
          {showDevDetails && workflow.suspicious_evidence ? (
            <p className="sm:col-span-2 text-xs text-amber-800">
              Advisory: suspicious evidence patterns flagged (data only — no tools executed).
            </p>
          ) : null}
        </div>
      ) : null}

      {pendingConfirmation ? (
        <div className="space-y-3 rounded-md border border-teal-800/30 bg-teal-50 px-4 py-3 text-sm text-teal-950">
          <p className="font-medium">Confirmation required</p>
          <p>{pendingConfirmation.summary}</p>
          <p className="text-xs opacity-70">Expires: {pendingConfirmation.expires_at}</p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={loading}
              onClick={() => onConfirm(true)}
              className="rounded-md bg-teal-800 px-3 py-2 text-white disabled:opacity-50"
            >
              Approve
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => onConfirm(false)}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-800 disabled:opacity-50"
            >
              Deny
            </button>
          </div>
        </div>
      ) : null}

      {bootError ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">
          {bootError}
        </div>
      ) : null}
      {sendError ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">
          {sendError}
        </div>
      ) : null}

      <div className="min-h-[320px] flex-1 space-y-3 rounded-lg border border-slate-200 bg-white/80 p-4">
        {messages.length === 0 ? (
          <p className="text-sm text-slate-500">
            Try: where is my order VD-10001 · what is your return policy · warranty terms ·
            cancel order VD-10001
          </p>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`max-w-[90%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                message.role === "user"
                  ? "ml-auto bg-teal-800 text-teal-50"
                  : "mr-auto bg-slate-100 text-slate-900"
              }`}
            >
              <p className="mb-1 text-[10px] uppercase tracking-wide opacity-70">{message.role}</p>
              <p className="whitespace-pre-wrap">{message.content}</p>
              {message.providerLabel ? (
                <p className="mt-1 text-[10px] opacity-60">{message.providerLabel}</p>
              ) : null}
            </div>
          ))
        )}
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-2 sm:flex-row">
        <input
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-slate-900"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={loading || Boolean(bootError)}
          aria-label="Message"
        />
        <button
          type="submit"
          disabled={loading || Boolean(bootError) || !input.trim()}
          className="rounded-md bg-teal-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Sending…" : "Send"}
        </button>
      </form>
    </div>
  );
}
