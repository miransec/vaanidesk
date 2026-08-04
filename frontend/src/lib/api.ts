const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type DemoUser = {
  id: string;
  email: string;
  display_name: string;
  demo_key: string;
};

export type ProviderMetadata = {
  provider: string;
  model: string;
  is_mock: boolean;
  language_hint?: string | null;
  disclaimer?: string | null;
};

export type MessageOut = {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  request_id?: string | null;
  provider_metadata?: Record<string, unknown> | null;
  created_at: string;
};

export type ConfirmationOut = {
  token: string;
  action: string;
  summary: string;
  expires_at: string;
};

export type CitationOut = {
  document_title: string;
  document_version: number;
  section_label: string;
  chunk_id: string;
  source_type: string;
  score: number;
};

export type WorkflowOut = {
  status: string;
  detected_language?: string | null;
  script?: string | null;
  intent?: string | null;
  intent_confidence?: number | null;
  selected_tool?: string | null;
  tool_execution_status?: string | null;
  clarification_required?: boolean;
  confirmation_required?: boolean;
  escalation_required?: boolean;
  escalation_reason?: string | null;
  trace_id?: string | null;
  confirmation?: ConfirmationOut | null;
  citations?: CitationOut[];
  retrieval_strategy?: string | null;
  retrieval_confidence?: number | null;
  no_answer?: boolean;
  no_answer_reason?: string | null;
  retrieval_trace_id?: string | null;
  suspicious_evidence?: boolean;
};

export type ChatMessageResponse = {
  request_id: string;
  conversation_id: string;
  user_message: MessageOut;
  assistant_message: MessageOut;
  provider: ProviderMetadata;
  workflow?: WorkflowOut | null;
};

export type ConfirmActionResponse = {
  request_id: string;
  conversation_id: string;
  assistant_message: MessageOut;
  provider: ProviderMetadata;
  workflow: WorkflowOut;
};

export type ConversationSummary = {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type ConversationDetail = {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: MessageOut[];
};

export type ApiError = {
  error: {
    code: string;
    message: string;
    request_id?: string | null;
  };
};

async function parseJson<T>(res: Response): Promise<T> {
  const data = (await res.json()) as T | ApiError;
  if (!res.ok) {
    const err = data as ApiError;
    throw new Error(err.error?.message ?? `Request failed (${res.status})`);
  }
  return data as T;
}

export async function listDemoUsers(): Promise<DemoUser[]> {
  const res = await fetch(`${API_URL}/api/v1/demo-users`, { cache: "no-store" });
  return parseJson<DemoUser[]>(res);
}

export async function listConversations(demoKey: string): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_URL}/api/v1/conversations`, {
    headers: { "X-Demo-User-Key": demoKey },
    cache: "no-store",
  });
  return parseJson<ConversationSummary[]>(res);
}

export async function getConversation(
  demoKey: string,
  conversationId: string,
): Promise<ConversationDetail> {
  const res = await fetch(`${API_URL}/api/v1/conversations/${conversationId}`, {
    headers: { "X-Demo-User-Key": demoKey },
    cache: "no-store",
  });
  return parseJson<ConversationDetail>(res);
}

export async function sendMessage(input: {
  demoKey: string;
  content: string;
  conversationId?: string | null;
  idempotencyKey?: string | null;
}): Promise<ChatMessageResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Demo-User-Key": input.demoKey,
  };
  if (input.idempotencyKey) {
    headers["Idempotency-Key"] = input.idempotencyKey;
  }
  const res = await fetch(`${API_URL}/api/v1/chat/messages`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      content: input.content,
      conversation_id: input.conversationId ?? null,
    }),
  });
  return parseJson<ChatMessageResponse>(res);
}

export async function confirmAction(input: {
  demoKey: string;
  confirmationToken: string;
  approved: boolean;
  idempotencyKey?: string | null;
}): Promise<ConfirmActionResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Demo-User-Key": input.demoKey,
  };
  if (input.idempotencyKey) {
    headers["Idempotency-Key"] = input.idempotencyKey;
  }
  const res = await fetch(`${API_URL}/api/v1/actions/confirm`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      confirmation_token: input.confirmationToken,
      approved: input.approved,
    }),
  });
  return parseJson<ConfirmActionResponse>(res);
}

export function getApiBaseUrl(): string {
  return API_URL;
}

export type KnowledgeDocument = {
  id: string;
  title: string;
  source_type: string;
  language: string;
  is_active: boolean;
  access_level: string;
  current_version: number | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeVersion = {
  id: string;
  document_id: string;
  version_number: number;
  content_hash: string;
  original_filename: string | null;
  mime_type: string;
  processing_status: string;
  is_active: boolean;
  created_at: string;
  chunk_count: number;
};

export type KnowledgeDocumentDetail = KnowledgeDocument & {
  versions: KnowledgeVersion[];
};

export type RetrievalTestResponse = {
  strategy: string;
  confidence: number;
  no_answer: boolean;
  no_answer_reason?: string | null;
  suspicious_evidence?: boolean;
  latency_ms: number;
  trace_id?: string | null;
  citations: CitationOut[];
  chunks: Array<{
    chunk_id: string;
    document_title: string;
    document_version: number;
    section_label: string;
    text: string;
    score: number;
  }>;
  candidate_chunk_ids: string[];
  fused_scores: Record<string, number>;
  embedding_disclaimer: string;
};

export async function listKnowledgeDocuments(demoKey: string): Promise<KnowledgeDocument[]> {
  const res = await fetch(`${API_URL}/api/v1/knowledge/documents`, {
    headers: { "X-Demo-User-Key": demoKey },
    cache: "no-store",
  });
  return parseJson<KnowledgeDocument[]>(res);
}

export async function getKnowledgeDocument(
  demoKey: string,
  documentId: string,
): Promise<KnowledgeDocumentDetail> {
  const res = await fetch(`${API_URL}/api/v1/knowledge/documents/${documentId}`, {
    headers: { "X-Demo-User-Key": demoKey },
    cache: "no-store",
  });
  return parseJson<KnowledgeDocumentDetail>(res);
}

export async function ingestKnowledgeDocument(input: {
  demoKey: string;
  title: string;
  content: string;
  mimeType?: string;
  language?: string;
  accessLevel?: string;
}): Promise<{ document_id: string; version_id: string; status: string; chunk_count?: number }> {
  const res = await fetch(`${API_URL}/api/v1/knowledge/documents`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Demo-User-Key": input.demoKey,
    },
    body: JSON.stringify({
      title: input.title,
      content: input.content,
      mime_type: input.mimeType ?? "text/markdown",
      language: input.language ?? "en",
      access_level: input.accessLevel ?? "authenticated",
      activate: true,
    }),
  });
  return parseJson(res);
}

export async function testRetrieval(input: {
  demoKey: string;
  query: string;
  strategy: string;
}): Promise<RetrievalTestResponse> {
  const res = await fetch(`${API_URL}/api/v1/knowledge/retrieval/test`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Demo-User-Key": input.demoKey,
    },
    body: JSON.stringify({
      query: input.query,
      strategy: input.strategy,
      top_k: 5,
      persist_trace: true,
    }),
  });
  return parseJson<RetrievalTestResponse>(res);
}

// --- Phase 4 voice ---

export type VoiceProviderOut = {
  provider: string;
  is_mock: boolean;
  disclaimer: string;
};

export type VoiceMessageOut = {
  id: string;
  conversation_id: string;
  user_id: string;
  message_id: string | null;
  requested_language: string | null;
  detected_language: string | null;
  original_filename: string | null;
  mime_type: string;
  audio_format: string;
  duration_ms: number | null;
  size_bytes: number;
  content_hash: string;
  transcription_status: string;
  transcript: string | null;
  transcript_confidence: number | null;
  transcript_hash: string | null;
  transcript_confirmed_at: string | null;
  submitted_at: string | null;
  auto_submitted: boolean;
  requires_transcript_confirmation: boolean;
  can_auto_submit: boolean;
  error_code: string | null;
  created_at: string;
  updated_at: string;
};

export type VoiceUploadResponse = {
  request_id: string;
  voice_message: VoiceMessageOut;
  provider: VoiceProviderOut;
};

export type VoiceStatusResponse = {
  request_id: string;
  voice_message: VoiceMessageOut;
  provider: VoiceProviderOut;
};

export type VoiceSubmitResponse = VoiceStatusResponse & {
  conversation_id: string;
  user_message: MessageOut | null;
  assistant_message: MessageOut | null;
  provider: ProviderMetadata;
  workflow: WorkflowOut | null;
};

export type SpeechSynthesisOut = {
  id: string;
  message_id: string;
  user_id: string;
  language: string;
  provider: string;
  voice_name: string | null;
  audio_format: string;
  duration_ms: number | null;
  size_bytes: number | null;
  content_hash: string | null;
  status: string;
  download_url: string | null;
  expires_at: string | null;
  is_mock: boolean;
  disclaimer: string;
  created_at: string;
};

function voiceHeaders(demoKey: string): Record<string, string> {
  return { "X-Demo-User-Key": demoKey };
}

export async function uploadAudio(input: {
  demoKey: string;
  file: Blob;
  filename?: string;
  conversationId?: string | null;
  requestedLanguage?: string | null;
}): Promise<VoiceUploadResponse> {
  const form = new FormData();
  form.append("file", input.file, input.filename ?? "recording.wav");
  if (input.conversationId) {
    form.append("conversation_id", input.conversationId);
  }
  if (input.requestedLanguage) {
    form.append("requested_language", input.requestedLanguage);
  }
  const res = await fetch(`${API_URL}/api/v1/voice/upload`, {
    method: "POST",
    headers: voiceHeaders(input.demoKey),
    body: form,
  });
  return parseJson<VoiceUploadResponse>(res);
}

export async function transcribe(input: {
  demoKey: string;
  voiceMessageId: string;
  autoSubmit?: boolean;
  fixtureKey?: string | null;
}): Promise<VoiceStatusResponse | VoiceSubmitResponse> {
  const params = new URLSearchParams();
  if (input.autoSubmit !== undefined) {
    params.set("auto_submit", String(input.autoSubmit));
  }
  if (input.fixtureKey) {
    params.set("fixture_key", input.fixtureKey);
  }
  const qs = params.toString();
  const res = await fetch(
    `${API_URL}/api/v1/voice/messages/${input.voiceMessageId}/transcribe${qs ? `?${qs}` : ""}`,
    {
      method: "POST",
      headers: voiceHeaders(input.demoKey),
    },
  );
  return parseJson(res);
}

export async function confirmTranscript(input: {
  demoKey: string;
  voiceMessageId: string;
  transcriptHash: string;
}): Promise<VoiceStatusResponse> {
  const res = await fetch(
    `${API_URL}/api/v1/voice/messages/${input.voiceMessageId}/confirm`,
    {
      method: "POST",
      headers: {
        ...voiceHeaders(input.demoKey),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ transcript_hash: input.transcriptHash }),
    },
  );
  return parseJson<VoiceStatusResponse>(res);
}

export async function editTranscript(input: {
  demoKey: string;
  voiceMessageId: string;
  transcript: string;
}): Promise<VoiceStatusResponse> {
  const res = await fetch(`${API_URL}/api/v1/voice/messages/${input.voiceMessageId}/edit`, {
    method: "POST",
    headers: {
      ...voiceHeaders(input.demoKey),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ transcript: input.transcript }),
  });
  return parseJson<VoiceStatusResponse>(res);
}

export async function submitTranscript(input: {
  demoKey: string;
  voiceMessageId: string;
  transcriptHash?: string | null;
  idempotencyKey?: string | null;
}): Promise<VoiceSubmitResponse> {
  const params = new URLSearchParams();
  if (input.transcriptHash) {
    params.set("transcript_hash", input.transcriptHash);
  }
  const qs = params.toString();
  const headers: Record<string, string> = voiceHeaders(input.demoKey);
  if (input.idempotencyKey) {
    headers["Idempotency-Key"] = input.idempotencyKey;
  }
  const res = await fetch(
    `${API_URL}/api/v1/voice/messages/${input.voiceMessageId}/submit${qs ? `?${qs}` : ""}`,
    {
      method: "POST",
      headers,
    },
  );
  return parseJson<VoiceSubmitResponse>(res);
}

export async function requestTts(input: {
  demoKey: string;
  messageId: string;
  language?: string | null;
  voiceName?: string | null;
}): Promise<SpeechSynthesisOut> {
  const res = await fetch(`${API_URL}/api/v1/voice/tts`, {
    method: "POST",
    headers: {
      ...voiceHeaders(input.demoKey),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message_id: input.messageId,
      language: input.language ?? null,
      voice_name: input.voiceName ?? null,
    }),
  });
  return parseJson<SpeechSynthesisOut>(res);
}

export function getAudioDownloadUrl(
  kind: "recording" | "synthesis",
  id: string,
): string {
  const base = `${API_URL}/api/v1/voice`;
  if (kind === "recording") {
    return `${base}/messages/${id}/download`;
  }
  return `${base}/synthesis/${id}/download`;
}

// --- Phase 5 channels ---

export type ChannelConnectionOut = {
  id: string;
  channel_type: string;
  display_name: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type InboundEventOut = {
  id: string;
  channel_connection_id: string;
  external_event_id: string;
  status: string;
  received_at: string;
  processed_at: string | null;
  error_code: string | null;
  safe_metadata: Record<string, unknown> | null;
};

export type OutboundMessageOut = {
  id: string;
  conversation_id: string;
  channel_connection_id: string;
  message_type: string;
  rendered_content: string;
  status: string;
  created_at: string;
  sent_at: string | null;
  failed_at: string | null;
};

export type HandoffQueueItemOut = {
  id: string;
  conversation_id: string;
  status: string;
  assigned_agent_id: string | null;
  summary: string;
  created_at: string;
};

export async function listChannelConnections(demoKey: string): Promise<ChannelConnectionOut[]> {
  const res = await fetch(`${API_URL}/api/v1/channels/connections`, {
    headers: { "X-Demo-User-Key": demoKey },
    cache: "no-store",
  });
  return parseJson<ChannelConnectionOut[]>(res);
}

export async function toggleChannelConnection(
  demoKey: string,
  connectionId: string,
  enabled: boolean,
): Promise<ChannelConnectionOut> {
  const res = await fetch(`${API_URL}/api/v1/channels/connections/${connectionId}/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Demo-User-Key": demoKey },
    body: JSON.stringify({ enabled }),
  });
  return parseJson<ChannelConnectionOut>(res);
}

export async function listInboundEvents(demoKey: string): Promise<InboundEventOut[]> {
  const res = await fetch(`${API_URL}/api/v1/channels/events`, {
    headers: { "X-Demo-User-Key": demoKey },
    cache: "no-store",
  });
  return parseJson<InboundEventOut[]>(res);
}

export async function listFailedOutbound(demoKey: string): Promise<OutboundMessageOut[]> {
  const res = await fetch(`${API_URL}/api/v1/channels/outbound/failed`, {
    headers: { "X-Demo-User-Key": demoKey },
    cache: "no-store",
  });
  return parseJson<OutboundMessageOut[]>(res);
}

export async function retryOutbound(demoKey: string, messageId: string): Promise<unknown> {
  const res = await fetch(`${API_URL}/api/v1/channels/outbound/${messageId}/retry`, {
    method: "POST",
    headers: { "X-Demo-User-Key": demoKey },
  });
  return parseJson(res);
}

export async function listHandoffQueue(demoKey: string): Promise<HandoffQueueItemOut[]> {
  const res = await fetch(`${API_URL}/api/v1/channels/handoff`, {
    headers: { "X-Demo-User-Key": demoKey },
    cache: "no-store",
  });
  return parseJson<HandoffQueueItemOut[]>(res);
}

export async function assignHandoff(
  demoKey: string,
  handoffId: string,
  agentId: string,
): Promise<unknown> {
  const res = await fetch(`${API_URL}/api/v1/channels/handoff/${handoffId}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Demo-User-Key": demoKey },
    body: JSON.stringify({ agent_id: agentId }),
  });
  return parseJson(res);
}

export async function simulateEmailEvent(
  demoKey: string,
  event: { from_email: string; from_display: string; subject: string; text_body: string },
): Promise<unknown> {
  const res = await fetch(`${API_URL}/api/v1/channels/simulator/email`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Demo-User-Key": demoKey },
    body: JSON.stringify(event),
  });
  return parseJson(res);
}

export async function simulateWhatsAppEvent(
  demoKey: string,
  event: { from_phone: string; display_name: string; text: string },
): Promise<unknown> {
  const res = await fetch(`${API_URL}/api/v1/channels/simulator/whatsapp`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Demo-User-Key": demoKey },
    body: JSON.stringify(event),
  });
  return parseJson(res);
}

export async function seedChannelConnections(demoKey: string): Promise<unknown> {
  const res = await fetch(`${API_URL}/api/v1/channels/seed`, {
    method: "POST",
    headers: { "X-Demo-User-Key": demoKey },
  });
  return parseJson(res);
}
