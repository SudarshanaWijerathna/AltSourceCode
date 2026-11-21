"use client";
// Staff page: private enquiries (Req 7) and AI-written content awaiting approval (Req 8).
// The staff key is kept in sessionStorage for this tab only; every permission is enforced by the
// backend (mira/auth) — the UI only hides buttons a role can't use.
import { useCallback, useEffect, useState } from "react";

type Me = { name: string; role: "staff" | "approver"; can_publish: boolean };
type Enquiry = {
  id: string; created_at: string; status: string; needs_specialist: boolean; reason: string | null;
  tour_id: string | null; tour_name: string | null; start_date: string | null;
  adults: number | null; children: number | null; infants: number | null;
  price_usd: string | null; deposit_usd: string | null; cost_usd: string | null; gross_profit_pct: string | null;
  contact_name: string | null; contact_email: string | null; contact_phone: string | null; booking_ref: string | null;
  follow_up_status: string; notes: string; trace_url: string | null; request: Record<string, unknown> | null;
};
type Draft = {
  id: string; tour_id: string; command: string; title: string; markdown: string; staff_notes: string;
  status: "draft" | "published" | "rejected"; created_by: string; created_at: string;
  decided_by: string | null; trace_url: string | null;
};

const FOLLOW_UP = ["new", "contacted", "awaiting_traveller", "booked", "payment_failed", "booking_failed", "closed"];

function useStaffApi() {
  const [key, setKey] = useState<string | null>(null);
  useEffect(() => { try { setKey(sessionStorage.getItem("mira.staffKey")); } catch { /* ignore */ } }, []);
  const call = useCallback(async (path: string, init?: RequestInit) => {
    const res = await fetch(`/backend${path}`, {
      ...init,
      headers: { "content-type": "application/json", "x-staff-key": key ?? "", ...(init?.headers ?? {}) },
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail ?? `Request failed (${res.status})`);
    return body;
  }, [key]);
  const save = (k: string | null) => {
    try { k ? sessionStorage.setItem("mira.staffKey", k) : sessionStorage.removeItem("mira.staffKey"); } catch { /* ignore */ }
    setKey(k);
  };
  return { key, save, call };
}

function Login({ onKey, error }: { onKey: (k: string) => void; error: string | null }) {
  const [value, setValue] = useState("");
  return (
    <form className="staff-login mira-card" onSubmit={(e) => { e.preventDefault(); onKey(value.trim()); }}>
      <p className="mira-card__label">Staff sign in</p>
      <label className="mira-form">Staff key<input value={value} onChange={(e) => setValue(e.target.value)} type="password" required /></label>
      {error && <p className="staff-error">{error}</p>}
      <button className="mira-button">Sign in</button>
      {process.env.NODE_ENV !== "production" && (
        <p className="mira-source">Local demo keys: <code>demo-staff-key</code> (staff), <code>demo-approver-key</code> (approver).</p>
      )}
    </form>
  );
}

function EnquiryRow({ e, onSave }: { e: Enquiry; onSave: (id: string, patch: Partial<Enquiry>) => Promise<void> }) {
  const [notes, setNotes] = useState(e.notes);
  const [status, setStatus] = useState(e.follow_up_status);
  const [saved, setSaved] = useState(false);
  const dirty = notes !== e.notes || status !== e.follow_up_status;
  const party = [e.adults && `${e.adults}A`, e.children && `${e.children}C`, e.infants && `${e.infants}I`].filter(Boolean).join(" ");
  return (
    <tr className={e.needs_specialist ? "flagged" : ""}>
      <td><code>{e.id}</code><div className="mira-source">{e.created_at.replace("T", " ").slice(0, 16)}</div></td>
      <td>
        <strong>{e.tour_name ?? (e.request ? String(e.request.requested ?? e.status) : e.tour_id)}</strong>
        <div className="mira-source">{[e.tour_id, e.start_date, party].filter(Boolean).join(" · ")}</div>
      </td>
      <td>
        {e.needs_specialist
          ? <span className="pill pill--flag" title={e.reason ?? ""}>Specialist: {e.status.replace(/_/g, " ")}</span>
          : <span className="pill">{e.status}</span>}
        {e.reason && e.needs_specialist && <div className="mira-source">{e.reason}</div>}
      </td>
      <td className="num">{e.price_usd ? `$${e.price_usd}` : "—"}<div className="mira-source">{e.deposit_usd ? `dep $${e.deposit_usd}` : ""}</div></td>
      <td className="num">{e.cost_usd ? `$${e.cost_usd}` : "—"}<div className="mira-source">{e.gross_profit_pct ? `GP ${e.gross_profit_pct}%` : ""}</div></td>
      <td>
        {e.contact_name ? <>{e.contact_name}<div className="mira-source">{e.contact_email}{e.booking_ref ? ` · ${e.booking_ref}` : ""}</div></> : <span className="mira-source">—</span>}
      </td>
      <td>
        <select value={status} onChange={(ev) => { setStatus(ev.target.value); setSaved(false); }}>
          {FOLLOW_UP.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <textarea value={notes} onChange={(ev) => { setNotes(ev.target.value); setSaved(false); }} rows={2} placeholder="Notes" />
        <button className="mira-button mira-button--ghost" disabled={!dirty}
                onClick={async () => { await onSave(e.id, { notes, follow_up_status: status }); setSaved(true); }}>
          {saved ? "Saved" : "Save"}
        </button>
      </td>
      <td>{e.trace_url ? <a href={e.trace_url} target="_blank" rel="noreferrer">trace</a> : "—"}</td>
    </tr>
  );
}

function Enquiries({ call }: { call: (p: string, i?: RequestInit) => Promise<any> }) {
  const [rows, setRows] = useState<Enquiry[] | null>(null);
  const [filter, setFilter] = useState<"all" | "flagged" | "priced">("all");
  const load = useCallback(() => call("/staff/enquiries").then(setRows), [call]);
  useEffect(() => { load(); }, [load]);
  const save = async (id: string, patch: Partial<Enquiry>) => {
    const updated = await call(`/staff/enquiries/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
    setRows((rs) => rs?.map((r) => (r.id === id ? updated : r)) ?? null);
  };
  const shown = (rows ?? []).filter((r) => filter === "all" || (filter === "flagged" ? r.needs_specialist : r.status === "priced"));
  return (
    <section>
      <div className="staff-toolbar">
        {(["all", "flagged", "priced"] as const).map((f) => (
          <button key={f} className={`mira-chip ${filter === f ? "is-active" : ""}`} onClick={() => setFilter(f)}>{f}</button>
        ))}
        <button className="mira-button mira-button--ghost" onClick={load}>Refresh</button>
        <span className="mira-source">{rows ? `${shown.length} of ${rows.length}` : "Loading…"}</span>
      </div>
      <div className="table-wrap">
        <table className="staff-table">
          <thead><tr><th>Enquiry</th><th>Trip</th><th>Status</th><th>Price</th><th>Cost / GP</th><th>Contact</th><th>Follow-up</th><th>Trace</th></tr></thead>
          <tbody>{shown.map((e) => <EnquiryRow key={e.id} e={e} onSave={save} />)}</tbody>
        </table>
      </div>
    </section>
  );
}

function Content({ call, me }: { call: (p: string, i?: RequestInit) => Promise<any>; me: Me }) {
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [command, setCommand] = useState("Add a 5-day Hill Country tour using the Ella photos");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => call("/staff/drafts").then(setDrafts), [call]);
  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); await load(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <section>
      <form className="staff-command" onSubmit={(e) => { e.preventDefault(); run(() => call("/staff/drafts", { method: "POST", body: JSON.stringify({ command }) })); }}>
        <input value={command} onChange={(e) => setCommand(e.target.value)} aria-label="Content command" />
        <button className="mira-button" disabled={busy}>{busy ? "Working…" : "Create draft"}</button>
      </form>
      <p className="mira-source">The content agent writes a draft from our published pages only. Only an Approver can publish it; until then Mira never uses it.</p>
      {error && <p className="staff-error">{error}</p>}
      {(drafts ?? []).map((d) => (
        <article key={d.id} className={`draft draft--${d.status}`}>
          <header className="draft__head">
            <div>
              <strong>{d.title}</strong> <code>{d.tour_id}</code>
              <div className="mira-source">“{d.command}” · by {d.created_by} · {d.created_at.slice(0, 16).replace("T", " ")}
                {d.trace_url && <> · <a href={d.trace_url} target="_blank" rel="noreferrer">trace</a></>}</div>
            </div>
            <span className={`pill ${d.status === "draft" ? "pill--flag" : ""}`}>{d.status}{d.decided_by ? ` by ${d.decided_by}` : ""}</span>
          </header>
          {d.staff_notes && <ul className="draft__notes">{d.staff_notes.split("\n").map((n) => <li key={n}>{n}</li>)}</ul>}
          <details><summary>Preview page</summary><pre className="draft__md">{d.markdown}</pre></details>
          {d.status === "draft" && (
            <div className="draft__actions">
              <button className="mira-button" disabled={busy || !me.can_publish}
                      title={me.can_publish ? "" : "Only an Approver can publish"}
                      onClick={() => run(() => call(`/staff/drafts/${d.id}/publish`, { method: "POST" }))}>Publish</button>
              <button className="mira-button mira-button--ghost" disabled={busy || !me.can_publish}
                      onClick={() => run(() => call(`/staff/drafts/${d.id}/reject`, { method: "POST" }))}>Reject</button>
              {!me.can_publish && <span className="mira-source">Only an Approver can publish or reject.</span>}
            </div>
          )}
        </article>
      ))}
      {drafts?.length === 0 && <p className="muted">No drafts yet.</p>}
    </section>
  );
}

export default function StaffPage() {
  const { key, save, call } = useStaffApi();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"enquiries" | "content">("enquiries");

  useEffect(() => {
    if (!key) { setMe(null); return; }
    call("/staff/me").then(setMe).catch((e) => { setError(e.message); save(null); });
  }, [key, call]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="staff">
      <header className="topbar">
        <span className="topbar__mark" aria-hidden>◆</span>
        <span className="topbar__name">Ceylon Compass · Staff</span>
        {me && (
          <>
            <nav className="staff-tabs">
              <button className={tab === "enquiries" ? "is-active" : ""} onClick={() => setTab("enquiries")}>Enquiries</button>
              <button className={tab === "content" ? "is-active" : ""} onClick={() => setTab("content")}>Content</button>
            </nav>
            <span className="topbar__tag">{me.name} ({me.role})</span>
            <button className="topbar__forget" onClick={() => save(null)}>Sign out</button>
          </>
        )}
      </header>
      <main className="page page--wide">
        {!me ? <Login onKey={(k) => { setError(null); save(k); }} error={error} />
          : tab === "enquiries" ? <Enquiries call={call} /> : <Content call={call} me={me} />}
      </main>
    </div>
  );
}
