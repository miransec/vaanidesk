import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-12 px-4 pb-16 pt-8 md:pt-16">
      <section className="max-w-2xl space-y-5">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-800">
          Multilingual AI customer support
        </p>
        <h1 className="font-display text-4xl leading-tight text-slate-950 md:text-6xl">
          VaaniDesk
        </h1>
        <p className="text-lg text-slate-700 md:text-xl">
          Multilingual AI customer support that can answer policy questions, retrieve customer
          information, perform approved actions, and escalate safely — with citations, confirmation
          gates, and engineering observability for demos and portfolio review.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/chat"
            className="rounded-md bg-teal-800 px-5 py-2.5 text-sm font-medium text-white"
          >
            Try the demo
          </Link>
          <Link
            href="/admin/observability"
            className="rounded-md border border-slate-300 bg-white/70 px-5 py-2.5 text-sm text-slate-800"
          >
            View engineering
          </Link>
        </div>
      </section>

      <section className="grid gap-8 md:grid-cols-3">
        <div>
          <h2 className="font-display text-xl text-slate-900">Policy answers with sources</h2>
          <p className="mt-2 text-sm text-slate-600">
            Hybrid RAG retrieves customer-facing policy evidence and cites sources. Low-confidence
            evidence abstains instead of inventing policy.
          </p>
        </div>
        <div>
          <h2 className="font-display text-xl text-slate-900">Approved actions</h2>
          <p className="mt-2 text-sm text-slate-600">
            Order lookups, cancellations, and address changes run through authorization and
            confirmation — not free-form tool calling.
          </p>
        </div>
        <div>
          <h2 className="font-display text-xl text-slate-900">Safe escalation</h2>
          <p className="mt-2 text-sm text-slate-600">
            When confidence is low or the request is unclear, VaaniDesk creates a support ticket.
            The demo does not connect to a live agent.
          </p>
        </div>
      </section>
    </main>
  );
}
