"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  getMe,
  listSessions,
  revokeSession,
  changePassword,
  logout,
  type UserProfile,
  type SessionInfo,
} from "@/lib/auth";

export default function AccountPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [pwForm, setPwForm] = useState({ current: "", next: "" });
  const [pwMsg, setPwMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const me = await getMe();
    if (!me) {
      router.push("/login");
      return;
    }
    setUser(me);
    setSessions(await listSessions());
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleRevoke(id: string) {
    await revokeSession(id);
    await load();
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    setPwMsg(null);
    try {
      await changePassword(pwForm.current, pwForm.next);
      setPwMsg("Password changed — please log in again");
      setTimeout(() => router.push("/login"), 2000);
    } catch (err) {
      setPwMsg(err instanceof Error ? err.message : "Failed");
    }
  }

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  if (!user) return <main className="p-8 text-center text-slate-500">Loading…</main>;

  return (
    <main className="mx-auto max-w-2xl space-y-8 px-4 py-8">
      <h1 className="font-display text-2xl text-slate-900">Account</h1>

      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-medium text-slate-800">Profile</h2>
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-slate-500">Email</dt>
          <dd>{user.email}</dd>
          <dt className="text-slate-500">Name</dt>
          <dd>{user.display_name}</dd>
          <dt className="text-slate-500">Role</dt>
          <dd className="capitalize">{user.role.replace("_", " ")}</dd>
        </dl>
        <button
          onClick={handleLogout}
          className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
        >
          Sign out
        </button>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-medium text-slate-800">Change password</h2>
        <form onSubmit={handlePasswordChange} className="flex flex-col gap-3">
          <input
            type="password"
            placeholder="Current password"
            value={pwForm.current}
            onChange={(e) => setPwForm((f) => ({ ...f, current: e.target.value }))}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            required
          />
          <input
            type="password"
            placeholder="New password (min 8 chars)"
            value={pwForm.next}
            onChange={(e) => setPwForm((f) => ({ ...f, next: e.target.value }))}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            required
            minLength={8}
          />
          {pwMsg && <p className="text-sm text-slate-600">{pwMsg}</p>}
          <button
            type="submit"
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800"
          >
            Update password
          </button>
        </form>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-medium text-slate-800">Active sessions</h2>
        {sessions.length === 0 ? (
          <p className="text-sm text-slate-500">No active sessions</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {sessions.map((s) => (
              <li key={s.id} className="flex items-center justify-between py-2 text-sm">
                <div>
                  <p className="text-slate-700">
                    {s.user_agent?.slice(0, 60) ?? "Unknown device"}
                    {s.is_current && (
                      <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
                        Current
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-slate-400">
                    {s.ip_address} · Created {new Date(s.created_at).toLocaleString()}
                  </p>
                </div>
                {!s.is_current && (
                  <button
                    onClick={() => handleRevoke(s.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Revoke
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
