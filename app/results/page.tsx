"use client";
import { useEffect, useState } from "react";
import { api, pct } from "../lib";

type VersionResult = {
  n: number; accuracy: number; ci95: [number, number]; answerable_accuracy: number | null;
  false_answer_rate: number | null; unanswerable_n: number;
};
type Split = { by_version: Record<string, VersionResult>; mcnemar: { from: string; to: string; only_from_right: number; only_to_right: number; p: number }[] };
type Results = {
  ask?: { model: string; run_at: string; splits: Record<string, Split>;
    current_dev_misses: { id: string; question: string; kind: string; sql: string | null; gold_sql: string | null }[] };
  injection?: { model: string; n: number; attack_success: Record<string, number> };
  digest?: { model: string; by_version: Record<string, { numbers_stated: number; unsupported: number; unsupported_rate: number; ci95: [number, number]; digests_with_any_unsupported: number; digests: number }> };
  checker?: { clean_summaries: number; false_alarm_rate: number; by_error: Record<string, { planted: number; caught: number }> };
};

const NOT_RUN = <p className="meta">Not run yet.</p>;

export default function ResultsPage() {
  const [r, setR] = useState<Results | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<Results>("/api/results").then(setR).catch((e) => setErr((e as Error).message)); }, []);

  return (
    <div className="stack">
      <div>
        <h1>Results</h1>
        <p className="lede">
          Measured on the public synthetic data in this repo, not on any company&apos;s data. Prompts were changed
          only while looking at the dev split; the test split was fixed before the first prompt ran.
        </p>
      </div>
      {err && <p className="error">{err}</p>}

      <h2>1. Ask the CRM: what each prompt change was worth</h2>
      {!r ? <p className="meta">Loading…</p> : !r.ask ? NOT_RUN : (
        <>
          <p className="meta">Model {r.ask.model}, run {r.ask.run_at}. v1 schema only · v2 + column notes · v3 + 6 examples · v4 + rules · v5 + may decline.</p>
          {(["test", "dev"] as const).filter((s) => r.ask!.splits[s]).map((s) => {
            const sp = r.ask!.splits[s];
            const first = Object.values(sp.by_version)[0];
            return (
              <div className="panel stack" key={s}>
                <strong>{s} split · {first.n} questions, {first.unanswerable_n} the data can&apos;t answer</strong>
                <div className="tablewrap"><table>
                  <thead><tr><th>version</th><th className="num">accuracy</th><th className="num">95% CI</th><th className="num">answerable right</th><th className="num">false answers when it should decline</th></tr></thead>
                  <tbody>{Object.entries(sp.by_version).map(([v, x]) => (
                    <tr key={v}><td>{v}</td><td className="num">{pct(x.accuracy)}</td>
                      <td className="num">{pct(x.ci95[0], 0)} – {pct(x.ci95[1], 0)}</td>
                      <td className="num">{pct(x.answerable_accuracy)}</td><td className="num">{pct(x.false_answer_rate, 0)}</td></tr>
                  ))}</tbody>
                </table></div>
                <div className="tablewrap"><table>
                  <thead><tr><th>change</th><th className="num">newly right</th><th className="num">newly wrong</th><th className="num">McNemar p</th></tr></thead>
                  <tbody>{sp.mcnemar.map((m) => (
                    <tr key={m.to}><td>{m.from} → {m.to}</td><td className="num">{m.only_to_right}</td><td className="num">{m.only_from_right}</td><td className="num">{m.p.toFixed(3)}</td></tr>
                  ))}</tbody>
                </table></div>
              </div>
            );
          })}
          {r.ask.current_dev_misses.length > 0 && (
            <details className="panel">
              <summary>What the live prompt still gets wrong on dev ({r.ask.current_dev_misses.length} shown)</summary>
              <div className="tablewrap"><table>
                <thead><tr><th>question</th><th>outcome</th><th>its SQL</th></tr></thead>
                <tbody>{r.ask.current_dev_misses.map((m) => (
                  <tr key={m.id}><td>{m.question}</td><td>{m.kind.replace(/_/g, " ")}</td><td><code>{m.sql ?? "—"}</code></td></tr>
                ))}</tbody>
              </table></div>
            </details>
          )}
        </>
      )}

      <h2>1b. Prompt injection through deal notes</h2>
      {!r ? null : !r.injection ? NOT_RUN : (
        <div className="panel tablewrap"><table>
          <thead><tr><th>defence</th><th className="num">attacks that got through (of {r.injection.n})</th></tr></thead>
          <tbody>
            <tr><td>none</td><td className="num">{pct(r.injection.attack_success.undefended, 0)}</td></tr>
            <tr><td>rows marked as data</td><td className="num">{pct(r.injection.attack_success.prompt_only, 0)}</td></tr>
            <tr><td>+ reply checked before showing</td><td className="num">{pct(r.injection.attack_success.prompt_and_check, 0)}</td></tr>
          </tbody>
        </table></div>
      )}

      <h2>2. Monday summary: numbers not in the data</h2>
      {!r ? null : !r.digest ? NOT_RUN : (
        <div className="panel tablewrap"><table>
          <thead><tr><th>version</th><th className="num">unsupported / stated</th><th className="num">rate</th><th className="num">95% CI</th><th className="num">summaries with any</th></tr></thead>
          <tbody>{Object.entries(r.digest.by_version).map(([v, x]) => (
            <tr key={v}><td>{v}</td><td className="num">{x.unsupported} / {x.numbers_stated}</td><td className="num">{pct(x.unsupported_rate)}</td>
              <td className="num">{pct(x.ci95[0])} – {pct(x.ci95[1])}</td><td className="num">{x.digests_with_any_unsupported} / {x.digests}</td></tr>
          ))}</tbody>
        </table></div>
      )}

      <h2>2b. How good is the checker?</h2>
      {!r ? null : !r.checker ? NOT_RUN : (
        <div className="panel stack">
          <span className="meta">False alarms on {r.checker.clean_summaries} clean summaries: {pct(r.checker.false_alarm_rate, 0)}</span>
          <div className="tablewrap"><table>
            <thead><tr><th>planted error</th><th className="num">caught</th></tr></thead>
            <tbody>{Object.entries(r.checker.by_error).map(([k, t]) => (
              <tr key={k}><td>{k}</td><td className="num">{t.caught} / {t.planted}</td></tr>
            ))}</tbody>
          </table></div>
          <span className="meta">&quot;swapped&quot; is the known blind spot: a real number next to the wrong label passes, because the checker checks values, not labels.</span>
        </div>
      )}
    </div>
  );
}
