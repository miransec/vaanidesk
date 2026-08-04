import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 pb-16 pt-8 md:pt-16">
      <section className="max-w-2xl space-y-5">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-800">
          Multilingual AI support across chat, voice and images
        </p>
        <h1 className="font-display text-4xl leading-tight text-slate-950 md:text-6xl">
          VaaniDesk
        </h1>
        <p className="text-lg text-slate-700 md:text-xl">
          Production-oriented customer support for English, Hindi, Hinglish and Marathi — with
          controlled tools, hybrid RAG citations, sensitive-action confirmation, voice transport,
          evaluations and security gates. Default providers are deterministic mocks.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/chat"
            className="rounded-md bg-teal-800 px-5 py-2.5 text-sm font-medium text-white"
          >
            Open chat demo
          </Link>
          <Link
            href="/login"
            className="rounded-md border border-slate-300 bg-white/70 px-5 py-2.5 text-sm text-slate-800"
          >
            Sign in
          </Link>
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/docs`}
            className="rounded-md border border-slate-300 bg-white/70 px-5 py-2.5 text-sm text-slate-800"
          >
            API docs
          </a>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        <div>
          <h2 className="font-display text-xl text-slate-900">Mock providers</h2>
          <p className="mt-2 text-sm text-slate-600">
            Deterministic LLM, STT and TTS for local demos and CI. Not production model quality.
            Swap providers later via environment configuration.
          </p>
        </div>
        <div>
          <h2 className="font-display text-xl text-slate-900">Auth options</h2>
          <p className="mt-2 text-sm text-slate-600">
            Register or sign in with JWT sessions, or continue with seeded demo users such as{" "}
            <code>demo-anya</code> when demo mode is enabled.
          </p>
        </div>
        <div>
          <h2 className="font-display text-xl text-slate-900">Verified v1.0.0</h2>
          <p className="mt-2 text-sm text-slate-600">
            197 backend tests, 113 deterministic evaluations, 9 Playwright E2E tests — plus Ruff,
            mypy and Docker health gates.
          </p>
        </div>
      </section>
    </main>
  );
}
