"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  KnowledgeDocument,
  KnowledgeDocumentDetail,
  RetrievalTestResponse,
  getKnowledgeDocument,
  ingestKnowledgeDocument,
  listDemoUsers,
  listKnowledgeDocuments,
  testRetrieval,
} from "@/lib/api";

export default function KnowledgePage() {
  const [demoKey, setDemoKey] = useState("demo-anya");
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [selected, setSelected] = useState<KnowledgeDocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [query, setQuery] = useState("What is the return procedure?");
  const [strategy, setStrategy] = useState("hybrid");
  const [retrieval, setRetrieval] = useState<RetrievalTestResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const list = await listKnowledgeDocuments(demoKey);
      setDocs(list);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    }
  }, [demoKey]);

  useEffect(() => {
    void listDemoUsers().catch(() => undefined);
    void refresh();
  }, [refresh]);

  async function onSelect(id: string) {
    try {
      const detail = await getKnowledgeDocument(demoKey, id);
      setSelected(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load document");
    }
  }

  async function onIngest(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !content.trim()) return;
    setBusy(true);
    try {
      await ingestKnowledgeDocument({
        demoKey,
        title: title.trim(),
        content: content.trim(),
      });
      setTitle("");
      setContent("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRetrieve(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await testRetrieval({ demoKey, query, strategy });
      setRetrieval(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retrieval failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8">
      <header className="space-y-2 border-b border-teal-900/10 pb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-800">VaaniDesk</p>
        <h1 className="font-display text-3xl text-slate-900">Knowledge</h1>
        <p className="text-sm text-slate-600">
          Phase 3 document ingestion, versions, and retrieval testing. Embeddings are deterministic
          lexical mocks — not production semantic embeddings.
        </p>
      </header>

      <label className="flex max-w-xs flex-col gap-1 text-sm text-slate-700">
        Demo user
        <select
          className="rounded-md border border-slate-300 bg-white px-3 py-2"
          value={demoKey}
          onChange={(e) => {
            setDemoKey(e.target.value);
            setSelected(null);
            setRetrieval(null);
          }}
        >
          <option value="demo-anya">demo-anya</option>
          <option value="demo-rahul">demo-rahul</option>
          <option value="demo-priya">demo-priya</option>
          <option value="demo-arjun">demo-arjun</option>
        </select>
      </label>

      {error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">
          {error}
        </div>
      ) : null}

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 className="font-display text-xl text-slate-900">Documents</h2>
          <ul className="max-h-80 space-y-2 overflow-y-auto text-sm">
            {docs.map((doc) => (
              <li key={doc.id}>
                <button
                  type="button"
                  onClick={() => void onSelect(doc.id)}
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-left hover:border-teal-700"
                >
                  <span className="font-medium text-slate-900">{doc.title}</span>
                  <span className="mt-1 block text-xs text-slate-500">
                    v{doc.current_version ?? "—"} · {doc.access_level} ·{" "}
                    {doc.is_active ? "active" : "inactive"} · {doc.language}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {selected ? (
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3 text-sm">
              <p className="font-medium">{selected.title}</p>
              <ul className="mt-2 space-y-1 text-xs text-slate-600">
                {selected.versions.map((v) => (
                  <li key={v.id}>
                    v{v.version_number} · {v.processing_status} ·{" "}
                    {v.is_active ? "active" : "inactive"} · {v.chunk_count} chunks
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <form onSubmit={onIngest} className="space-y-3">
          <h2 className="font-display text-xl text-slate-900">Ingest Markdown / text</h2>
          <input
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <textarea
            className="min-h-40 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
            placeholder="# Policy&#10;&#10;Body…"
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <button
            type="submit"
            disabled={busy || !title.trim() || !content.trim()}
            className="rounded-md bg-teal-800 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {busy ? "Working…" : "Ingest"}
          </button>
        </form>
      </section>

      <section className="space-y-3 border-t border-slate-200 pt-6">
        <h2 className="font-display text-xl text-slate-900">Retrieval test</h2>
        <form onSubmit={onRetrieve} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex flex-1 flex-col gap-1 text-sm">
            Query
            <input
              className="rounded-md border border-slate-300 px-3 py-2"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Strategy
            <select
              className="rounded-md border border-slate-300 px-3 py-2"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            >
              <option value="keyword">keyword</option>
              <option value="vector">vector</option>
              <option value="hybrid">hybrid</option>
              <option value="hybrid_rerank">hybrid_rerank</option>
            </select>
          </label>
          <button
            type="submit"
            disabled={busy || !query.trim()}
            className="rounded-md bg-teal-800 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            Retrieve
          </button>
        </form>

        {retrieval ? (
          <div className="space-y-3 text-sm">
            <p>
              Strategy <strong>{retrieval.strategy}</strong> · confidence{" "}
              <strong>{retrieval.confidence.toFixed(3)}</strong> · {retrieval.latency_ms} ms
              {retrieval.no_answer ? (
                <span className="text-amber-900">
                  {" "}
                  · no-answer ({retrieval.no_answer_reason})
                </span>
              ) : null}
            </p>
            <p className="text-xs text-slate-500">{retrieval.embedding_disclaimer}</p>
            {retrieval.citations.length > 0 ? (
              <div>
                <p className="font-medium">Citations</p>
                <ul className="mt-1 space-y-1 text-xs">
                  {retrieval.citations.map((c) => (
                    <li key={c.chunk_id}>
                      {c.document_title} v{c.document_version} · {c.section_label} · score{" "}
                      {c.score.toFixed(4)}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <ul className="space-y-2">
              {retrieval.chunks.map((ch) => (
                <li
                  key={ch.chunk_id}
                  className="rounded-md border border-slate-200 bg-white px-3 py-2"
                >
                  <p className="text-xs text-slate-500">
                    {ch.document_title} v{ch.document_version} · {ch.section_label} ·{" "}
                    {ch.score.toFixed(4)}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap text-slate-800">{ch.text}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>
    </div>
  );
}
