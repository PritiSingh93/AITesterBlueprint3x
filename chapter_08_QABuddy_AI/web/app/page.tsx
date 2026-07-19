"use client";

import { useEffect, useRef, useState } from "react";

const SOURCE_TYPES = [
  "selenium_code", "playwright_code", "test_case", "jira", "doc",
  "design", "meeting", "diagram", "prd", "jenkins",
];

const BADGES: Record<string, string> = {
  selenium_code: "🧩", playwright_code: "🎭", test_case: "✅",
  jira: "🐞", doc: "📄", design: "🎨", meeting: "🗒️",
  diagram: "🔀", prd: "📘", jenkins: "⚙️",
};

type Source = {
  n: number;
  source: string;
  source_type: string;
  score: number;
  module?: string;
  text: string;
};

type Message = { role: "user" | "assistant"; content: string; sources?: Source[] };
type Health = { healthy: boolean; services: Record<string, string>; error?: string };

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [pickedTypes, setPickedTypes] = useState<string[]>([]);
  const [module, setModule] = useState("");
  const [topK, setTopK] = useState(8);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthChecked, setHealthChecked] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((h) => setHealth(h))
      .catch(() => setHealth(null))
      .finally(() => setHealthChecked(true));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function toggleType(t: string) {
    setPickedTypes((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t],
    );
  }

  async function ask() {
    const q = question.trim();
    if (!q || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setQuestion("");
    setLoading(true);

    const filters: Record<string, unknown> = {};
    if (pickedTypes.length) filters.source_type = pickedTypes;
    if (module.trim()) filters.module = module.trim();

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          filters: Object.keys(filters).length ? filters : null,
          top_k: topK,
        }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer ?? "No answer returned.",
          sources: data.sources ?? [],
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Request failed: ${(err as Error).message}`, sources: [] },
      ]);
    } finally {
      setLoading(false);
    }
  }

  const degraded = healthChecked && (!health || !health.healthy);

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>🤝 QABuddyAI</h2>
        <p className="muted">
          Grounded, cited answers from our frameworks, test cases, JIRA history,
          PRDs &amp; Jenkins results.
        </p>

        <div className="health">
          {!healthChecked && <span className="badge gray">checking backend…</span>}
          {healthChecked && health?.healthy && (
            <span className="badge green">● backend healthy</span>
          )}
          {healthChecked && degraded && (
            <span className="badge amber">● backend unreachable</span>
          )}
          {health?.services && Object.keys(health.services).length > 0 && (
            <ul className="svc">
              {Object.entries(health.services).map(([k, v]) => (
                <li key={k}>
                  <span>{k}</span>
                  <span className={String(v).startsWith("ok") ? "ok" : "err"}>{v}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="field">
          <label>Source types</label>
          <div className="chips">
            {SOURCE_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                className={`chip ${pickedTypes.includes(t) ? "on" : ""}`}
                onClick={() => toggleType(t)}
              >
                {BADGES[t]} {t}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label>Module / component</label>
          <input
            value={module}
            onChange={(e) => setModule(e.target.value)}
            placeholder="e.g. AB Testing"
          />
        </div>

        <div className="field">
          <label>Context chunks: {topK}</label>
          <input
            type="range"
            min={3}
            max={15}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
          />
        </div>

        <button type="button" className="clear" onClick={() => setMessages([])}>
          Clear chat
        </button>
      </aside>

      <main className="chat">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">
              <p className="empty-title">Ask one question — get a cited answer.</p>
              <p className="muted">e.g. “What test cases exist for AB Testing?”</p>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className="bubble">
                <div className="who">{m.role === "user" ? "You" : "🤝 QABuddyAI"}</div>
                <div className="content">{m.content}</div>
                {m.sources && m.sources.length > 0 && (
                  <details className="sources">
                    <summary>📎 Sources ({m.sources.length})</summary>
                    {m.sources.map((s) => (
                      <div key={s.n} className="src">
                        <div className="src-head">
                          <b>
                            [{s.n}] {BADGES[s.source_type] ?? "📁"} {s.source}
                          </b>
                          <code>{s.source_type}</code>
                          <span className="muted">score {s.score}</span>
                          {s.module && <span className="muted">· {s.module}</span>}
                        </div>
                        <pre>
                          {s.text.slice(0, 1500)}
                          {s.text.length > 1500 ? "…" : ""}
                        </pre>
                      </div>
                    ))}
                  </details>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="msg assistant">
              <div className="bubble">
                <div className="who">🤝 QABuddyAI</div>
                <div className="content muted">Searching the QA knowledge base…</div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="composer">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask();
              }
            }}
            placeholder="Ask about test cases, requirements, frameworks…  (Enter to send, Shift+Enter for newline)"
            rows={2}
          />
          <button type="button" onClick={ask} disabled={loading || !question.trim()}>
            {loading ? "…" : "Ask"}
          </button>
        </div>
      </main>
    </div>
  );
}
