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
  getApiBaseUrl,
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

type ChatRow = MessageOut & {
  providerLabel?: string;
  synthesisId?: string | null;
};

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
    "Phase 4 demo — controlled workflow + knowledge RAG + mock voice (not production STT/TTS)",
  );
  const [workflow, setWorkflow] = useState<WorkflowOut | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<ConfirmationOut | null>(null);
  const [showDevDetails, setShowDevDetails] = useState(false);

  const [voiceMessage, setVoiceMessage] = useState<VoiceMessageOut | null>(null);
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [recording, setRecording] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      setProviderNote(uploaded.provider.disclaimer);

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
        setMessages((prev) => [
          ...prev,
          result.user_message!,
          {
            ...result.assistant_message!,
            providerLabel: `${result.provider.provider}/${result.provider.model}`,
          },
        ]);
      }
      applyWorkflow(result.workflow);
      setProviderNote(result.provider.disclaimer ?? providerNote);
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
      setSendError(err instanceof Error ? err.message : "TTS playback failed");
    } finally {
      setVoiceBusy(false);
    }
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
          Phase 4 demo auth via <code className="rounded bg-slate-100 px-1">X-Demo-User-Key</code>.
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
              resetVoiceReview();
              setDemoKey(e.target.value);
            }}
            aria-label="Demo user"
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

      <section
        className="space-y-3 rounded-md border border-violet-200 bg-violet-50/60 px-4 py-3"
        aria-label="Voice input"
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded bg-violet-200 px-2 py-0.5 text-xs font-medium text-violet-950">
            Mock STT/TTS
          </span>
          <p className="text-sm text-violet-950">Upload audio or record (when supported).</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="cursor-pointer rounded-md border border-violet-300 bg-white px-3 py-2 text-sm text-violet-950 hover:bg-violet-50">
            Upload audio
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,.wav,.mp3,.webm,.m4a"
              className="sr-only"
              aria-label="Upload audio file"
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
                className="rounded-md border border-violet-400 bg-white px-3 py-2 text-sm text-violet-950 disabled:opacity-50"
                aria-label="Start voice recording"
                disabled={voiceBusy || Boolean(bootError)}
                onClick={startRecording}
              >
                Record
              </button>
            )
          ) : null}
        </div>

        {voiceMessage ? (
          <div className="space-y-2 rounded-md border border-violet-200 bg-white p-3 text-sm">
            <div className="flex flex-wrap gap-3 text-xs text-slate-600">
              <span>
                Status: <strong>{voiceMessage.transcription_status}</strong>
              </span>
              {voiceMessage.detected_language ? (
                <span>
                  Language: <strong>{voiceMessage.detected_language}</strong>
                </span>
              ) : null}
              {voiceMessage.transcript_confidence != null ? (
                <span>
                  Confidence:{" "}
                  <strong>{voiceMessage.transcript_confidence.toFixed(2)}</strong>
                </span>
              ) : null}
              {voiceMessage.can_auto_submit ? (
                <span className="text-emerald-700">Auto-submit eligible</span>
              ) : null}
            </div>
            <label className="flex flex-col gap-1 text-slate-700">
              Transcript review
              <textarea
                className="min-h-[80px] rounded-md border border-slate-300 px-2 py-2 text-slate-900"
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
                className="rounded-md bg-violet-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                aria-label="Submit transcript to workflow"
                disabled={voiceBusy || Boolean(voiceMessage.submitted_at)}
                onClick={onSubmitTranscript}
              >
                Submit to workflow
              </button>
            </div>
          </div>
        ) : null}
      </section>

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
              aria-label="Show developer details"
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
              aria-label="Approve confirmation"
            >
              Approve
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => onConfirm(false)}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-800 disabled:opacity-50"
              aria-label="Deny confirmation"
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
            cancel order VD-10001 · or upload a WAV for mock voice
          </p>
        ) : (
          messages.map((message, index) => (
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
              {message.role === "assistant" ? (
                <button
                  type="button"
                  className="mt-2 rounded border border-slate-300 bg-white px-2 py-0.5 text-[10px] text-slate-700 disabled:opacity-50"
                  aria-label="Play assistant reply with mock TTS"
                  disabled={voiceBusy}
                  onClick={() => onPlayTts(message.id, index)}
                >
                  {message.synthesisId ? "Replay mock TTS" : "Play mock TTS"}
                </button>
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
          aria-label="Send message"
        >
          {loading ? "Sending…" : "Send"}
        </button>
      </form>
    </div>
  );
}
