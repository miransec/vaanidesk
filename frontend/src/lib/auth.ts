const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let accessToken: string | null = null;
let tokenExpiresAt = 0;

export function getAccessToken(): string | null {
  if (accessToken && Date.now() < tokenExpiresAt) {
    return accessToken;
  }
  return null;
}

export function setAccessToken(token: string, expiresIn: number): void {
  accessToken = token;
  tokenExpiresAt = Date.now() + expiresIn * 1000 - 30_000;
}

export function clearAccessToken(): void {
  accessToken = null;
  tokenExpiresAt = 0;
}

export type AuthHeaders = Record<string, string>;

export function authHeaders(demoKey?: string): AuthHeaders {
  const token = getAccessToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  if (demoKey) {
    return { "X-Demo-User-Key": demoKey };
  }
  return {};
}

export type RegisterInput = {
  email: string;
  password: string;
  display_name: string;
};

export type LoginInput = {
  email: string;
  password: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type UserProfile = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  is_disabled: boolean;
  created_at: string;
};

export type SessionInfo = {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  created_at: string;
  expires_at: string;
  is_current: boolean;
};

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function register(input: RegisterInput): Promise<UserProfile> {
  const res = await fetch(`${API_URL}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return handleResponse<UserProfile>(res);
}

export async function login(input: LoginInput): Promise<TokenResponse> {
  const res = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  const data = await handleResponse<TokenResponse>(res);
  setAccessToken(data.access_token, data.expires_in);
  return data;
}

export async function refreshToken(): Promise<TokenResponse | null> {
  try {
    const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return null;
    const data = (await res.json()) as TokenResponse;
    setAccessToken(data.access_token, data.expires_in);
    return data;
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  const token = getAccessToken();
  await fetch(`${API_URL}/api/v1/auth/logout`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: "include",
  }).catch(() => {});
  clearAccessToken();
}

export async function getMe(): Promise<UserProfile | null> {
  const token = getAccessToken();
  if (!token) return null;
  const res = await fetch(`${API_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return null;
  return res.json() as Promise<UserProfile>;
}

export async function listSessions(): Promise<SessionInfo[]> {
  const token = getAccessToken();
  if (!token) return [];
  const res = await fetch(`${API_URL}/api/v1/auth/sessions`, {
    headers: { Authorization: `Bearer ${token}` },
    credentials: "include",
  });
  if (!res.ok) return [];
  return res.json() as Promise<SessionInfo[]>;
}

export async function revokeSession(sessionId: string): Promise<void> {
  const token = getAccessToken();
  if (!token) return;
  await fetch(`${API_URL}/api/v1/auth/sessions/${sessionId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const token = getAccessToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetch(`${API_URL}/api/v1/auth/password`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message ?? "Password change failed");
  }
  clearAccessToken();
}
