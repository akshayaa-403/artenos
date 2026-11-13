"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ms, pct, usd } from "../lib";

type Window = { requests: number; failure_rate: number | null; p50_ms: number | null; p95_ms: number | null;
  cost_per_request_usd: number | null; total_cost_usd: number; abstain_rate: number | null;
  helpful_rate: number | null; rated: number };
type Trace = { id: string; ts: number; route: string; question: string | null; ok: number; error: string | null;
  latency_ms: number | null; cost_usd: number | null; abstained: number | null; feedback: number | null };
type T = { "24h": Window; "7d": Window; all: Window; recent: Trace[]; not_helpful: Trace[] };

const TARGET_P95_MS = 3000;

export default function Telemetry() {
  const [t, setT] = useState<T | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => { api<T>("/api/telemetry").then(setT).catch((e) => setErr((e as Error).message)); }, []);
  useEffect(load, [load]);

  return (
    <div className="stack">
      <div>
        <h1>Telemetry</h1>
        <p className="lede">
          Every request to this demo, traced. The target is a p95 under {TARGET_P95_MS / 1000} s for a question,
          because a person is waiting. Questions marked &quot;not helpful&quot; become new test cases
          (<code>python -m evals.promote_failures</code>).
        </p>
      </div>
      <div className="row"><button onClick={load}>Refresh</button></div>
      {err && <p className="error">{err}</p>}
      {t && (["24h", "7d", "all"] as const).map((k) => {
        const w = t[k];
        return (
          <section key={k} className="stack">
            <h2>{k === "all" ? "Since this instance started" : `Last ${k}`}</h2>
            <div className="cards">
              <div className="card"><b>{w.requests}</b><span>requests</span></div>
              <div className="card"><b>{ms(w.p50_ms)}</b><span>p50 latency</span></div>
              <div className="card"><b style={{ color: w.p95_ms != null && w.p95_ms > TARGET_P95_MS ? "var(--bad)" : undefined }}>{ms(w.p95_ms)}</b><span>p95 latency (target {TARGET_P95_MS / 1000} s)</span></div>
              <div className="card"><b>{pct(w.failure_rate)}</b><span>failed</span></div>
              <div className="card"><b>{usd(w.cost_per_request_usd, 5)}</b><span>cost per request</span></div>
              <div className="card"><b>{pct(w.abstain_rate)}</b><span>declined to answer</span></div>
              <div className="card"><b>{pct(w.helpful_rate, 0)}</b><span>rated helpful ({w.rated} rated)</span></div>
            </div>
          </section>
        );
      })}
      {t && (
        <>
          <h2>Recent requests</h2>
          <div className="panel tablewrap"><table>
            <thead><tr><th>when</th><th>route</th><th>question</th><th className="num">latency</th><th className="num">cost</th><th>outcome</th></tr></thead>
            <tbody>{t.recent.map((r) => (
              <tr key={r.id}>
                <td className="meta">{new Date(r.ts * 1000).toLocaleString()}</td><td>{r.route}</td><td>{r.question}</td>
                <td className="num">{ms(r.latency_ms)}</td><td className="num">{usd(r.cost_usd, 5)}</td>
                <td>{!r.ok ? <span className="pill no">failed</span> : r.abstained ? <span className="pill">declined</span> : <span className="pill ok">answered</span>}
                  {r.feedback === 0 && <> <span className="pill no">not helpful</span></>}
                  {r.feedback === 1 && <> <span className="pill ok">helpful</span></>}</td>
              </tr>
            ))}</tbody>
          </table></div>
        </>
      )}
    </div>
  );
}
