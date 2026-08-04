"use client";

import type { ChangeEvent, FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ConfirmationOut,
  DemoUser,
  MessageOut,
  VoiceMessageOut,
  WorkflowOut,
  confirmAction,
  confirmTranscript,
  editTranscript,
  getAudioDownloadUrl,
  getConversation,
  listConversations,
  listDemoUsers,
  requestTts,
  sendMessage,
  submitTranscript,
  transcribe,
  uploadAudio,
} from "@/lib/api";
import { DEV_INSPECTOR_ENABLED, SUGGESTION_CHIPS, brand } from "@/lib/brand";

type ChatRow = MessageOut & {
  synthesisId?: string | null;
};

function formatTime(iso: string | undefined): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function OrderResultCard({ toolResult }: { toolResult: Record<string, unknown> }) {
  const orderRef = String(toolResult.order_ref ?? toolResult.order_number ?? "");
  if (!orderRef) return null;
  const status = toolResult.status != null ? String(toolResult.status) : null;
  const address =
    toolResult.delivery_address != null ? String(toolResult.delivery_address) : null;
  const shipping =
    toolResult.shipping_method != null ? String(toolResult.shipping_method) : null;
  const eta =
    toolResult.expected_delivery != null
      ? String(toolResult.expected_delivery)
      : toolResult.eta != null
        ? String(toolResult.eta)
        : null;

  return (
    <div className="mt-3 rounded-lg border border-teal-900/15 bg-white px-4 py-3 text-sm text-slate-800">
      <p className="font-medium text-slate-900">Order {orderRef}</p>
      <dl className="mt-2 grid gap-1.5 sm:grid-cols-2">
        {status ? (
          <>
            <dt className="text-slate-500">Status</dt>
            <dd className="capitalize text-slate-900">{status.replace(/_/g, " ")}</dd>
          </>
        ) : null}
        {eta ? (
          <>
            <dt className="text-slate-500">Expected delivery</dt>
            <dd className="text-slate-900">{eta}</dd>
          </>
        ) : null}
        {shipping ? (
          <>
            <dt className="text-slate-500">Shipping method</dt>
            <dd className="text-slate-900">{shipping}</dd>
          </>
        ) : null}
        {address ? (
          <>
            <dt className="text-slate-500">Delivery address</dt>
            <dd className="text-slate-900 sm:col-span-1">{address}</dd>
          </>
        ) : null}
      </dl>
    </div>
  );
}

function SupportRequestCard({ toolResult }: { toolResult: Record<string, unknown> }) {
  const ticketRef = String(toolResult.ticket_ref ?? "");
  if (!ticketRef) return null;
  const status = toolResult.status != null ? String(toolResult.status) : "queued";
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800">
      <p className="font-medium text-slate-900">Support request created</p>
      <dl className="mt-2 grid gap-1.5 sm:grid-cols-2">
        <dt className="text-slate-500">Ticket</dt>
        <dd className="font-medium text-slate-900">{ticketRef}</dd>
        <dt className="text-slate-500">Status</dt>
        <dd className="capitalize text-slate-900">{status.replace(/_/g, " ")}</dd>
      </dl>
      <p className="mt-2 text-slate-600">A support specialist can review this request.</p>
      <p className="mt-1 text-xs text-slate-500">
        This demo creates the support ticket, but does not connect to a live support agent.
      </p>
    </div>
  );
}

function SourcesBlock({ workflow }: { workflow: WorkflowOut }) {
  const citations = workflow.citations ?? [];
  if (!citations.length) return null;
  return (
    <details className="mt-3 rounded-lg border border-slate-200 bg-white/80 px-3 py-2 text-sm">
      <summary className="cursor-pointer font-medium text-slate-800">Sources</summary>
      <ul className="mt-2 space-y-1 text-slate-700">
        {citations.map((c) => (
          <li key={`${c.document_title}-${c.section_label}-${c.chunk_id}`}>
            <span className="font-medium">{c.document_title}</span>
            {c.section_label ? (
              <span className="text-slate-500"> · {c.section_label}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

function DevInspector({ workflow }: { workflow: WorkflowOut }) {
  if (!DEV_INSPECTOR_ENABLED) return null;
  return (
    <details className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-600">
      <summary className="cursor-pointer font-medium">Developer inspector</summary>
      <dl className="mt-2 grid gap-1 sm:grid-cols-2">
        <dt>Intent</dt>
        <dd>
          {workflow.intent ?? "—"}
          {workflow.intent_confidence != null
            ? ` (${workflow.intent_confidence.toFixed(2)})`
            : ""}
        </dd>
        <dt>Tool</dt>
        <dd>
          {workflow.selected_tool ?? "—"} / {workflow.tool_execution_status ?? "—"}
        </dd>
        <dt>Evidence confidence</dt>
        <dd>
          {workflow.evidence_confidence_band ?? "—"}
          {workflow.retrieval_confidence != null
            ? ` (${workflow.retrieval_confidence.toFixed(2)})`
            : ""}
        </dd>
        <dt>Retrieval</dt>
        <dd>{workflow.retrieval_strategy ?? "—"}</dd>
        {workflow.trace_id ? (
          <>
            <dt>Trace</dt>
            <dd className="font-mono break-all">{workflow.trace_id}</dd>
          </>
        ) : null}
      </dl>
    </details>
  );
}

export function ChatPanel() {
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [demoKey, setDemoKey] = useState("demo-anya");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatRow[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowOut | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<ConfirmationOut | null>(null);
  const [personaPicked, setPersonaPicked] = useState(false);

  const [voiceMessage, setVoiceMessage] = useState<VoiceMessageOut | null>(null);
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [recording, setRecording] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  const selectedUser = useMemo(
    () => users.find((u) => u.demo_key === demoKey) ?? null,
    [users, demoKey],
  );

  const canUseMediaRecorder =
    typeof window !== "undefined" &&
    typeof MediaRecorder !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia);

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
              : "Could not load demo customers. Is the backend running?",
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
      if (!demoKey || bootError || !personaPicked) return;
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
  }, [demoKey, bootError, personaPicked]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, pendingConfirmation]);

  function applyWorkflow(next: WorkflowOut | null | undefined) {
    if (!next) {
      setWorkflow(null);
      setPendingConfirmation(null);
      return;
    }
    setWorkflow(next);
    setPendingConfirmation(next.confirmation ?? null);
  }

  function resetVoiceReview() {
    setVoiceMessage(null);
    setTranscriptDraft("");
  }

  function syncVoiceState(vm: VoiceMessageOut) {
    setVoiceMessage(vm);
    setTranscriptDraft(vm.transcript ?? "");
    if (vm.conversation_id) {
      setConversationId(vm.conversation_id);
    }
  }

  function selectPersona(key: string) {
    setConversationId(null);
    setMessages([]);
    setWorkflow(null);
    setPendingConfirmation(null);
    resetVoiceReview();
    setDemoKey(key);
    setPersonaPicked(true);
    setSendError(null);
  }

  async function processVoiceBlob(blob: Blob, filename: string) {
    setVoiceBusy(true);
    setSendError(null);
    resetVoiceReview();
    try {
      const uploaded = await uploadAudio({
        demoKey,
        file: blob,
        filename,
        conversationId,
      });
      syncVoiceState(uploaded.voice_message);

      const tx = await transcribe({
        demoKey,
        voiceMessageId: uploaded.voice_message.id,
        autoSubmit: false,
      });
      syncVoiceState(tx.voice_message);
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Voice upload failed");
    } finally {
      setVoiceBusy(false);
    }
  }

  async function onFileSelected(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || voiceBusy) return;
    await processVoiceBlob(file, file.name || "upload.wav");
  }

  async function startRecording() {
    if (!canUseMediaRecorder || recording || voiceBusy) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        await processVoiceBlob(blob, "recording.webm");
        setRecording(false);
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Microphone access denied");
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
  }

  async function onConfirmTranscript() {
    if (!voiceMessage?.transcript_hash || voiceBusy) return;
    setVoiceBusy(true);
    setSendError(null);
    try {
      const edited =
        transcriptDraft.trim() !== (voiceMessage.transcript ?? "").trim()
          ? await editTranscript({
              demoKey,
              voiceMessageId: voiceMessage.id,
              transcript: transcriptDraft.trim(),
            })
          : null;
      const vm = edited?.voice_message ?? voiceMessage;
      const confirmed = await confirmTranscript({
        demoKey,
        voiceMessageId: vm.id,
        transcriptHash: vm.transcript_hash ?? voiceMessage.transcript_hash,
      });
      syncVoiceState(confirmed.voice_message);
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Transcript confirm failed");
    } finally {
      setVoiceBusy(false);
    }
  }

  async function onSubmitTranscript() {
    if (!voiceMessage || voiceBusy) return;
    setVoiceBusy(true);
    setSendError(null);
    try {
      let vm = voiceMessage;
      if (transcriptDraft.trim() !== (voiceMessage.transcript ?? "").trim()) {
        const edited = await editTranscript({
          demoKey,
          voiceMessageId: voiceMessage.id,
          transcript: transcriptDraft.trim(),
        });
        vm = edited.voice_message;
        syncVoiceState(vm);
      }
      if (!vm.transcript_confirmed_at && vm.transcript_hash) {
        const confirmed = await confirmTranscript({
          demoKey,
          voiceMessageId: vm.id,
          transcriptHash: vm.transcript_hash,
        });
        vm = confirmed.voice_message;
        syncVoiceState(vm);
      }
      const result = await submitTranscript({
        demoKey,
        voiceMessageId: vm.id,
        transcriptHash: vm.transcript_hash,
      });
      syncVoiceState(result.voice_message);
      if (result.user_message && result.assistant_message) {
        setMessages((prev) => [...prev, result.user_message!, result.assistant_message!]);
      }
      applyWorkflow(result.workflow);
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Voice submit failed");
    } finally {
      setVoiceBusy(false);
    }
  }

  async function onPlayTts(messageId: string, rowIndex: number) {
    setVoiceBusy(true);
    setSendError(null);
    try {
      const synth = await requestTts({ demoKey, messageId, language: workflow?.detected_language });
      setMessages((prev) =>
        prev.map((m, i) => (i === rowIndex ? { ...m, synthesisId: synth.id } : m)),
      );
      const url = getAudioDownloadUrl("synthesis", synth.id);
      const res = await fetch(url, { headers: { "X-Demo-User-Key": demoKey } });
      if (!res.ok) throw new Error(`Playback failed (${res.status})`);
      const blob = await res.blob();
      const audio = new Audio(URL.createObjectURL(blob));
      await audio.play();
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Voice playback failed");
    } finally {
      setVoiceBusy(false);
    }
  }

  async function sendText(text: string) {
    const content = text.trim();
    if (!content || loading) return;
    setLoading(true);
    setSendError(null);
    try {
      const result = await sendMessage({
        demoKey,
        content,
        conversationId,
      });
      setConversationId(result.conversation_id);
      setMessages((prev) => [...prev, result.user_message, result.assistant_message]);
      applyWorkflow(result.workflow);
      setInput("");
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Send failed");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await sendText(input);
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
      setMessages((prev) => [...prev, result.assistant_message]);
      applyWorkflow(result.workflow);
      setPendingConfirmation(null);
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Confirmation failed");
    } finally {
      setLoading(false);
    }
  }

  const isCancelAction =
    pendingConfirmation?.action?.toLowerCase().includes("cancel") ||
    pendingConfirmation?.summary?.toLowerCase().includes("cancel");

  const showEmptyGreeting = personaPicked && messages.length === 0 && !loading;

  if (!personaPicked && !bootError) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8 md:py-12">
        <header className="space-y-2">
          <h1 className="font-display text-3xl text-slate-900 md:text-4xl">{brand.assistantName}</h1>
          <p className="text-sm text-slate-600">{brand.supportSubtext}</p>
          <p className="text-sm text-slate-500">
            Continue as a demo customer for {brand.companyName}.
          </p>
        </header>
        {users.length === 0 ? (
          <p className="text-sm text-slate-500">Loading demo customers…</p>
        ) : (
          <ul className="space-y-3" aria-label="Demo customers">
            {users.map((user) => (
              <li key={user.demo_key}>
                <button
                  type="button"
                  onClick={() => selectPersona(user.demo_key)}
                  className="flex w-full flex-col items-start gap-0.5 rounded-xl border border-slate-200 bg-white/90 px-4 py-3 text-left transition hover:border-teal-700/40 hover:bg-teal-50/40"
                  aria-label={`Continue as ${user.display_name}`}
                >
                  <span className="text-xs font-medium uppercase tracking-wide text-teal-800">
                    Demo customer
                  </span>
                  <span className="font-display text-lg text-slate-900">{user.display_name}</span>
                  <span className="text-sm text-slate-600">{user.email}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6 md:py-8">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-teal-900/10 pb-4">
        <div className="space-y-1">
          <h1 className="font-display text-2xl text-slate-900 md:text-3xl">{brand.assistantName}</h1>
          <p className="text-sm text-slate-600">{brand.supportSubtext}</p>
          {selectedUser ? (
            <p className="text-xs text-slate-500">
              Signed in as {selectedUser.display_name} · {selectedUser.email}
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden />
            Online
          </span>
          <button
            type="button"
            className="text-xs text-slate-500 underline-offset-2 hover:underline"
            onClick={() => {
              setPersonaPicked(false);
              setMessages([]);
              setWorkflow(null);
              setPendingConfirmation(null);
            }}
            aria-label="Switch demo customer"
          >
            Switch customer
          </button>
        </div>
      </header>

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

      <div
        className="flex min-h-[380px] flex-1 flex-col gap-3 rounded-2xl border border-slate-200/80 bg-white/70 p-4 md:min-h-[420px]"
        aria-label="Conversation"
      >
        {showEmptyGreeting ? (
          <div className="flex flex-1 flex-col justify-center gap-4 py-6">
            <p className="font-display text-2xl text-slate-900">{brand.supportGreeting}</p>
            <div className="flex flex-wrap gap-2" aria-label="Suggestions">
              {SUGGESTION_CHIPS.map((chip) => (
                <button
                  key={chip}
                  type="button"
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 hover:border-teal-700/40 hover:bg-teal-50/50"
                  onClick={() => void sendText(chip)}
                  disabled={loading || Boolean(bootError)}
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message, index) => {
            const isCustomer = message.role === "user";
            const isLastAssistant =
              !isCustomer && index === messages.length - 1 && workflow != null;
            return (
              <div
                key={message.id}
                className={`flex max-w-[92%] flex-col gap-1 ${
                  isCustomer ? "ml-auto items-end" : "mr-auto items-start"
                }`}
              >
                <div className="flex items-baseline gap-2 text-[11px] uppercase tracking-wide text-slate-500">
                  <span>{isCustomer ? "Customer" : brand.productName}</span>
                  {message.created_at ? <span>{formatTime(message.created_at)}</span> : null}
                </div>
                <div
                  className={`rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    isCustomer
                      ? "bg-teal-800 text-teal-50"
                      : "bg-slate-100 text-slate-900"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {isLastAssistant && workflow?.tool_result ? (
                    <>
                      <OrderResultCard toolResult={workflow.tool_result} />
                      {(workflow.escalation_required ||
                        workflow.selected_tool === "transfer_to_human" ||
                        workflow.selected_tool === "create_support_ticket") && (
                        <SupportRequestCard toolResult={workflow.tool_result} />
                      )}
                    </>
                  ) : null}
                  {isLastAssistant && workflow ? <SourcesBlock workflow={workflow} /> : null}
                  {!isCustomer ? (
                    <button
                      type="button"
                      className="mt-2 text-[11px] text-slate-500 underline-offset-2 hover:underline disabled:opacity-50"
                      aria-label="Play voice reply"
                      disabled={voiceBusy}
                      onClick={() => onPlayTts(message.id, index)}
                    >
                      {message.synthesisId ? "Replay voice" : "Play voice"}
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
        {loading ? (
          <p className="text-sm text-slate-500" aria-live="polite">
            {brand.productName} is typing…
          </p>
        ) : null}
        <div ref={bottomRef} />
      </div>

      {pendingConfirmation ? (
        <div
          className="space-y-3 rounded-xl border border-teal-800/25 bg-teal-50/80 px-4 py-4 text-sm text-teal-950"
          aria-label="Confirmation required"
        >
          <p className="font-display text-lg text-slate-900">
            {isCancelAction ? "Confirm cancellation" : "Please confirm"}
          </p>
          <p>{pendingConfirmation.summary}</p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={loading}
              onClick={() => onConfirm(false)}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-800 disabled:opacity-50"
              aria-label="Keep order"
            >
              {isCancelAction ? "Keep order" : "Cancel"}
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => onConfirm(true)}
              className="rounded-md bg-teal-800 px-3 py-2 text-white disabled:opacity-50"
              aria-label={isCancelAction ? "Confirm cancellation" : "Approve confirmation"}
            >
              {isCancelAction ? "Confirm cancellation" : "Confirm"}
            </button>
          </div>
        </div>
      ) : null}

      {workflow && DEV_INSPECTOR_ENABLED ? <DevInspector workflow={workflow} /> : null}

      <section className="space-y-2" aria-label="Voice message">
        <div className="flex flex-wrap gap-2">
          <label className="cursor-pointer rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
            Upload audio
            <input
              type="file"
              accept="audio/*,.wav,.mp3,.webm,.m4a"
              className="sr-only"
              aria-label="Upload audio"
              disabled={voiceBusy || Boolean(bootError)}
              onChange={onFileSelected}
            />
          </label>
          {canUseMediaRecorder ? (
            recording ? (
              <button
                type="button"
                className="rounded-md bg-rose-700 px-3 py-2 text-sm text-white disabled:opacity-50"
                aria-label="Stop recording"
                disabled={voiceBusy}
                onClick={stopRecording}
              >
                Stop recording
              </button>
            ) : (
              <button
                type="button"
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 disabled:opacity-50"
                aria-label="Record"
                disabled={voiceBusy || Boolean(bootError)}
                onClick={startRecording}
              >
                Record
              </button>
            )
          ) : null}
        </div>
        {voiceMessage ? (
          <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-3 text-sm">
            <p className="text-xs font-medium text-slate-500">Voice message</p>
            <label className="flex flex-col gap-1 text-slate-700">
              Review transcript
              <textarea
                className="min-h-[72px] rounded-md border border-slate-300 px-2 py-2 text-slate-900"
                value={transcriptDraft}
                onChange={(e) => setTranscriptDraft(e.target.value)}
                aria-label="Edit transcript"
                disabled={Boolean(voiceMessage.submitted_at) || voiceBusy}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-50"
                aria-label="Confirm transcript"
                disabled={
                  voiceBusy ||
                  !voiceMessage.transcript_hash ||
                  Boolean(voiceMessage.submitted_at)
                }
                onClick={onConfirmTranscript}
              >
                Confirm transcript
              </button>
              <button
                type="button"
                className="rounded-md bg-teal-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                aria-label="Send voice message"
                disabled={voiceBusy || Boolean(voiceMessage.submitted_at)}
                onClick={onSubmitTranscript}
              >
                Send voice message
              </button>
            </div>
          </div>
        ) : null}
      </section>

      <form onSubmit={onSubmit} className="flex flex-col gap-2 sm:flex-row">
        <input
          className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-slate-900 shadow-sm"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message…"
          disabled={loading || Boolean(bootError)}
          aria-label="Message"
        />
        <button
          type="submit"
          disabled={loading || Boolean(bootError) || !input.trim()}
          className="rounded-xl bg-teal-800 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          aria-label="Send message"
        >
          {loading ? "Sending…" : "Send"}
        </button>
      </form>
    </div>
  );
}
