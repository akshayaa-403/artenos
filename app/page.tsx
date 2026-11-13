"use client";
import { useEffect, useState } from "react";
import { api, cell, ms, usd } from "./lib";

type Answer = {
  question: string; version: string; sql: string | null; columns: string[]; rows: unknown[][];
  truncated: boolean; answer: string; abstained: boolean; reason: string; error: string | null;
  latency_ms: number; cost_usd: number; llm_calls: number; trace_id: string;
};
type Examples = { examples: string[]; versions: string[]; current: string };

function Chart({ columns, rows }: { columns: string[]; rows: unknown[][] }) {
  // A bar per row when the answer is "a name and a number" and short enough to read.
  if (columns.length !== 2 || rows.length < 2 || rows.length > 20) return null;
  if (!rows.every((r) => typeof r[1] === "number")) return null;
  const max = Math.max(...rows.map((r) => Math.abs(r[1] as number))) || 1;
  return (
    <div className="chart" aria-hidden="true">
      {rows.map((r, i) => (
        <div className="bar" key={i}>
          <span>{cell(r[0])}</span>
          <i style={{ width: `${(Math.abs(r[1] as number) / max) * 100}%` }} />
          <b>{cell(r[1])}</b>
        </div>
      ))}
    </div>
  );
}

export default function Ask() {
  const [q, setQ] = useState("");
  const [meta, setMeta] = useState<Examples | null>(null);
  const [version, setVersion] = useState("v5");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Answer | null>(null);
  const [err, setErr] = useState("");
  const [rated, setRated] = useState<"" | "up" | "down">("");

  useEffect(() => { api<Examples>("/api/examples").then((m) => { setMeta(m); setVersion(m.current); }).catch(() => {}); }, []);

  async function run(question: string) {
    if (question.trim().length < 3) return;
    setQ(question); setBusy(true); setErr(""); setRes(null); setRated("");
    try { setRes(await api<Answer>("/api/ask", { question, version })); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  }

  async function rate(helpful: boolean) {
    if (!res) return;
    try { await api("/api/feedback", { trace_id: res.trace_id, helpful }); setRated(helpful ? "up" : "down"); } catch {}
  }

  return (
    <div className="stack">
      <div>
        <h1>Ask the CRM</h1>
        <p className="lede">
          Ask a sales question in plain English. The model writes SQL, a guard runs it read-only, and the answer
          comes back with the query and the rows it came from. If the data can&apos;t answer, it says so.
        </p>
      </div>

      <form className="panel stack" onSubmit={(e) => { e.preventDefault(); run(q); }}>
        <label htmlFor="q" className="meta">Your question</label>
        <textarea id="q" value={q} maxLength={300} onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. Which agent won the most revenue in Q1 2026?"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); run(q); } }} />
        <div className="row">
          <button className="primary" type="submit" disabled={busy}>{busy ? "Asking…" : "Ask"}</button>
          <label className="meta" htmlFor="v">Prompt</label>
          <select id="v" value={version} onChange={(e) => setVersion(e.target.value)}>
            {(meta?.versions ?? ["v5"]).map((v) => <option key={v} value={v}>{v}{v === meta?.current ? " (live)" : ""}</option>)}
          </select>
        </div>
        {meta && (
          <div className="row" aria-label="Example questions">
            {meta.examples.map((x) => (
              <button type="button" className="chip" key={x} onClick={() => run(x)} disabled={busy}>{x}</button>
            ))}
          </div>
        )}
      </form>

      {err && <p className="error" role="alert">{err}</p>}

      {res && (
        <section className="panel stack" aria-live="polite">
          {res.error
            ? <p className="error">{res.error}</p>
            : <p className={`answer${res.abstained ? " declined" : ""}`}>{res.answer}</p>}
          {!res.abstained && !res.error && <Chart columns={res.columns} rows={res.rows} />}
          {res.sql && (
            <details open>
              <summary>SQL that ran</summary>
              <pre>{res.sql}</pre>
            </details>
          )}
          {res.columns.length > 0 && (
            <details open={res.rows.length <= 12}>
              <summary>{res.rows.length}{res.truncated ? "+" : ""} row{res.rows.length === 1 ? "" : "s"}</summary>
              <div className="tablewrap">
                <table>
                  <thead><tr>{res.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>{res.rows.map((r, i) => (
                    <tr key={i}>{r.map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""}>{cell(v)}</td>)}</tr>
                  ))}</tbody>
                </table>
              </div>
            </details>
          )}
          <div className="row">
            <span className="meta">{ms(res.latency_ms)} · {res.llm_calls} model call{res.llm_calls === 1 ? "" : "s"} · {usd(res.cost_usd, 5)} · prompt {res.version}</span>
            <span style={{ flex: 1 }} />
            {rated
              ? <span className="meta">Thanks, noted.</span>
              : <>
                  <button className="chip" onClick={() => rate(true)}>Helpful</button>
                  <button className="chip" onClick={() => rate(false)}>Not helpful</button>
                </>}
          </div>
        </section>
      )}
    </div>
  );
}
