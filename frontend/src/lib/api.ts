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
