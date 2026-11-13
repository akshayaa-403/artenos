"use client";
import { useEffect, useState } from "react";
import { api, cell, ms, usd } from "../lib";

type Mention = { text: string; start: number; end: number; ok: boolean; fact: string | null; kind: string };
type Fact = { id: string; label: string; value: unknown; unit: string };
type Digest = {
  week_end: string; version: string; text: string; facts: Fact[];
  check: { mentions: Mention[]; stated: number; unsupported: number };
  first_draft: { text: string; stated: number; unsupported: number } | null;
  latency_ms: number; cost_usd: number; llm_calls: number; trace_id: string;
};

function Highlighted({ text, mentions, facts }: { text: string; mentions: Mention[]; facts: Fact[] }) {
  const label = (id: string | null) => facts.find((f) => f.id === id)?.label ?? "";
  const parts: React.ReactNode[] = [];
  let at = 0;
  mentions.forEach((m, i) => {
    parts.push(text.slice(at, m.start));
    parts.push(
      <mark key={i} className={m.ok ? "ok" : "no"} title={m.ok ? `Matches: ${label(m.fact)}` : "Not found in the week's figures"}>
        {text.slice(m.start, m.end)}
      </mark>);
    at = m.end;
  });
  parts.push(text.slice(at));
  return <p className="summary">{parts}</p>;
}

export default function DigestPage() {
  const [weeks, setWeeks] = useState<string[]>([]);
  const [versions, setVersions] = useState<string[]>(["v3"]);
  const [week, setWeek] = useState("");
  const [version, setVersion] = useState("v3");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Digest | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<{ weeks: string[]; versions: string[]; current: string }>("/api/weeks")
      .then((w) => { setWeeks(w.weeks); setWeek(w.weeks[0]); setVersions(w.versions); setVersion(w.current); })
      .catch((e) => setErr((e as Error).message));
  }, []);

  async function run() {
    setBusy(true); setErr(""); setRes(null);
    try { setRes(await api<Digest>("/api/digest", { week_end: week, version })); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  }

  return (
    <div className="stack">
      <div>
        <h1>Monday sales summary</h1>
        <p className="lede">
          The figures come from SQL; the model only writes the sentences. Then every number in the text is
          checked against the figures: <mark className="ok">green</mark> is in the data,{" "}
          <mark className="no">red</mark> is not. Version v3 asks for one rewrite when anything is red.
        </p>
      </div>
      <div className="panel row">
        <label className="meta" htmlFor="w">Week ending</label>
        <select id="w" value={week} onChange={(e) => setWeek(e.target.value)}>
          {weeks.map((w) => <option key={w}>{w}</option>)}
        </select>
        <label className="meta" htmlFor="v">Prompt</label>
        <select id="v" value={version} onChange={(e) => setVersion(e.target.value)}>
          {versions.map((v) => <option key={v}>{v}</option>)}
        </select>
        <button className="primary" onClick={run} disabled={busy || !week}>{busy ? "Writing…" : "Write the summary"}</button>
      </div>

      {err && <p className="error" role="alert">{err}</p>}

      {res && (
        <section className="panel stack" aria-live="polite">
          <div className="row">
            <span className={`pill ${res.check.unsupported ? "no" : "ok"}`}>
              {res.check.unsupported} of {res.check.stated} numbers not in the data
            </span>
            {res.first_draft && (
              <span className="pill">first draft had {res.first_draft.unsupported} of {res.first_draft.stated}; rewritten once</span>
            )}
          </div>
          <Highlighted text={res.text} mentions={res.check.mentions} facts={res.facts} />
          {res.first_draft && (
            <details>
              <summary>First draft</summary>
              <p className="summary">{res.first_draft.text}</p>
            </details>
          )}
          <details>
            <summary>The week&apos;s figures ({res.facts.length})</summary>
            <div className="tablewrap"><table>
              <tbody>{res.facts.map((f) => (
                <tr key={f.id}><td>{f.label}</td><td className="num">{cell(f.value)}</td></tr>
              ))}</tbody>
            </table></div>
          </details>
          <span className="meta">{ms(res.latency_ms)} · {res.llm_calls} model call{res.llm_calls === 1 ? "" : "s"} · {usd(res.cost_usd, 5)}</span>
        </section>
      )}
    </div>
  );
}
