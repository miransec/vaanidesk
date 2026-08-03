import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 pb-16 pt-8 md:pt-16">
      <section className="max-w-2xl space-y-5">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-800">
          Multilingual AI support
        </p>
        <h1 className="font-display text-4xl leading-tight text-slate-950 md:text-6xl">
          VaaniDesk
        </h1>
        <p className="text-lg text-slate-700 md:text-xl">
          Chat, voice and images for customer support — starting with a Phase 1 multilingual mock
          chat foundation for English, Hindi, Hinglish and Marathi.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/chat"
            className="rounded-md bg-teal-800 px-5 py-2.5 text-sm font-medium text-white"
          >
            Open chat demo
          </Link>
          <a
            href="http://localhost:8000/docs"
            className="rounded-md border border-slate-300 bg-white/70 px-5 py-2.5 text-sm text-slate-800"
          >
            API docs
          </a>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        <div>
          <h2 className="font-display text-xl text-slate-900">Mock provider</h2>
          <p className="mt-2 text-sm text-slate-600">
            Deterministic offline responses. Not a production model. Swap providers later via
            environment configuration.
          </p>
        </div>
        <div>
          <h2 className="font-display text-xl text-slate-900">Demo auth</h2>
          <p className="mt-2 text-sm text-slate-600">
            Use seeded users like <code>demo-anya</code>. Phase 1 demo identity headers are not
            production authentication.
          </p>
        </div>
        <div>
          <h2 className="font-display text-xl text-slate-900">What&apos;s next</h2>
          <p className="mt-2 text-sm text-slate-600">
            Phase 2 adds controlled tools, confirmations and traces. RAG, voice, MCP and evals
            follow in later phases.
          </p>
        </div>
      </section>
    </main>
  );
}
