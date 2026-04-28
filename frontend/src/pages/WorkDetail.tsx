import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  getWork, getStreams, getAuthor,
  addToStream, removeFromStream, updateWork,
  type Work, type Stream, type AuthorDetail,
} from "../services/api";

// Flatten all works from an AuthorDetail (collections + uncollected)
function allAuthorWorks(a: AuthorDetail): Work[] {
  const seen = new Set<string>();
  const result: Work[] = [];
  for (const coll of a.collections) {
    for (const w of coll.works) {
      if (!seen.has(w.id)) { seen.add(w.id); result.push(w); }
    }
  }
  for (const w of a.works) {
    if (!seen.has(w.id)) { seen.add(w.id); result.push(w); }
  }
  return result;
}

const DENSITY_LABELS = ["light", "moderate", "dense", "grueling"];
const STATUS_OPTIONS = ["to_read", "reading", "read", "abandoned"];
const SIGNIFICANCE_OPTIONS = ["", "major", "minor"];

const STATUS_COLORS: Record<string, string> = {
  read: "bg-emerald-100 text-emerald-800",
  reading: "bg-blue-100 text-blue-800",
  to_read: "bg-stone-100 text-stone-500",
  abandoned: "bg-red-100 text-red-700",
};

export default function WorkDetail() {
  const { id } = useParams<{ id: string }>();
  const [work, setWork] = useState<Work | null>(null);
  const [streams, setStreams] = useState<Stream[]>([]);
  const [workStreamIds, setWorkStreamIds] = useState<Set<string>>(new Set());
  const [authorDetails, setAuthorDetails] = useState<AuthorDetail[]>([]);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<Work>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    getWork(id).then((w) => {
      setWork(w);
      setWorkStreamIds(new Set(w.stream_ids));
      setForm({
        status: w.status,
        density_rating: w.density_rating ?? undefined,
        language_read_in: w.language_read_in ?? "",
        personal_note: w.personal_note ?? "",
        date_read: w.date_read ?? "",
        significance: w.significance ?? undefined,
      });
      // Fetch other works by the same author(s)
      Promise.all(w.authors.map((a) => getAuthor(a.id))).then(setAuthorDetails);
    });
    getStreams().then(setStreams);
  }, [id]);

  const save = async () => {
    if (!id) return;
    setSaving(true);
    setError("");
    try {
      const updated = await updateWork(id, form);
      setWork(updated);
      setWorkStreamIds(new Set(updated.stream_ids));
      setEditing(false);
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const toggleStream = async (streamId: string, inStream: boolean) => {
    if (!id) return;
    try {
      if (inStream) {
        await removeFromStream(id, streamId);
        setWorkStreamIds((prev) => { const s = new Set(prev); s.delete(streamId); return s; });
      } else {
        await addToStream(id, streamId);
        setWorkStreamIds((prev) => new Set([...prev, streamId]));
      }
    } catch (e: unknown) {
      console.error(e);
    }
  };

  if (!work) return <p className="text-stone-400">Loading…</p>;

  // Other works by same authors, excluding current
  const otherWorks = authorDetails.flatMap((a) =>
    allAuthorWorks(a).filter((w) => w.id !== id).map((w) => ({ ...w, authorName: a.name }))
  );

  return (
    <div className="max-w-2xl">
      <Link to="/" className="text-sm text-stone-400 hover:text-stone-600 mb-4 inline-block">← Back</Link>

      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">{work.title}</h1>
          <p className="text-stone-500 mt-1">
            {work.authors.map((a) => (
              <Link key={a.id} to={`/authors/${a.id}`} className="hover:text-stone-700 underline-offset-2 hover:underline">
                {a.name}
              </Link>
            )).reduce((acc, el, i) => i === 0 ? [el] : [...acc, ", ", el] as React.ReactNode[], [] as React.ReactNode[])}
          </p>
        </div>
        <button
          onClick={() => setEditing(!editing)}
          className="text-sm px-3 py-1.5 border border-stone-300 rounded hover:bg-stone-100 shrink-0"
        >
          {editing ? "Cancel" : "Edit"}
        </button>
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-4 text-sm mb-6">
        {([
          ["Status", work.status],
          ["Language", work.language_read_in],
          ["Year read", work.date_read],
          ["Density", work.density_rating],
          ["Source type", work.source_type],
          ["Significance", work.significance],
        ] as [string, string | null][]).map(([label, value]) => value ? (
          <div key={label}>
            <dt className="text-stone-400 text-xs uppercase tracking-wide">{label}</dt>
            <dd className="mt-0.5 font-medium">{value}</dd>
          </div>
        ) : null)}
      </div>

      {/* Collection membership */}
      {work.collections.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {work.collections.map((c) => (
            <Link
              key={c.id}
              to={`/collections/${c.id}`}
              className="text-xs px-2.5 py-1 bg-indigo-50 text-indigo-700 rounded-full hover:bg-indigo-100 transition-colors"
            >
              {c.name}{c.order != null ? ` #${c.order}` : ""}
            </Link>
          ))}
        </div>
      )}

      {work.personal_note && (
        <div className="mb-6 p-3 bg-amber-50 border border-amber-200 rounded text-sm italic text-stone-700">
          "{work.personal_note}"
        </div>
      )}

      {/* Edit form */}
      {editing && (
        <div className="mb-6 p-4 border border-stone-200 rounded-lg bg-white space-y-3">
          <h2 className="font-semibold text-sm">Edit</h2>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <label className="block">
              <span className="text-stone-500 text-xs">Status</span>
              <select
                value={form.status ?? ""}
                onChange={(e) => setForm({ ...form, status: e.target.value as Work["status"] })}
                className="block w-full border border-stone-300 rounded px-2 py-1 mt-0.5"
              >
                {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>

            <label className="block">
              <span className="text-stone-500 text-xs">Significance</span>
              <select
                value={form.significance ?? ""}
                onChange={(e) => setForm({ ...form, significance: e.target.value as Work["significance"] || undefined })}
                className="block w-full border border-stone-300 rounded px-2 py-1 mt-0.5"
              >
                {SIGNIFICANCE_OPTIONS.map((s) => <option key={s} value={s}>{s || "—"}</option>)}
              </select>
            </label>

            <label className="block">
              <span className="text-stone-500 text-xs">Density</span>
              <select
                value={form.density_rating ?? ""}
                onChange={(e) => setForm({ ...form, density_rating: e.target.value as Work["density_rating"] })}
                className="block w-full border border-stone-300 rounded px-2 py-1 mt-0.5"
              >
                <option value="">—</option>
                {DENSITY_LABELS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>

            <label className="block">
              <span className="text-stone-500 text-xs">Language read in</span>
              <input
                type="text"
                value={form.language_read_in ?? ""}
                onChange={(e) => setForm({ ...form, language_read_in: e.target.value })}
                className="block w-full border border-stone-300 rounded px-2 py-1 mt-0.5"
                placeholder="EN / NL / FR…"
              />
            </label>

            <label className="block">
              <span className="text-stone-500 text-xs">Date read</span>
              <input
                type="text"
                value={form.date_read ?? ""}
                onChange={(e) => setForm({ ...form, date_read: e.target.value })}
                className="block w-full border border-stone-300 rounded px-2 py-1 mt-0.5"
                placeholder="2024 or 2024-03-15"
              />
            </label>
          </div>

          <label className="block text-sm">
            <span className="text-stone-500 text-xs">Personal note</span>
            <textarea
              value={form.personal_note ?? ""}
              onChange={(e) => setForm({ ...form, personal_note: e.target.value })}
              rows={3}
              className="block w-full border border-stone-300 rounded px-2 py-1 mt-0.5 resize-none"
              placeholder="Short personal note…"
            />
          </label>

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <button
            onClick={save}
            disabled={saving}
            className="bg-stone-900 text-white text-sm px-4 py-1.5 rounded hover:bg-stone-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      )}

      {/* Streams */}
      <div className="mb-8">
        <h2 className="font-semibold mb-2">Streams</h2>
        <div className="space-y-1">
          {streams.map((s) => {
            const inStream = workStreamIds.has(s.id);
            return (
              <label key={s.id} className="flex items-center gap-2 text-sm cursor-pointer group">
                <input
                  type="checkbox"
                  checked={inStream}
                  onChange={() => toggleStream(s.id, inStream)}
                  className="accent-stone-900"
                />
                <span className="w-2.5 h-2.5 rounded-full inline-block shrink-0" style={{ backgroundColor: s.color ?? "#999" }} />
                <span className="group-hover:text-stone-700">{s.name}</span>
                <span className="text-stone-400 text-xs">({s.work_count})</span>
              </label>
            );
          })}
          {streams.length === 0 && (
            <p className="text-stone-400 text-sm">No streams yet. <Link to="/streams" className="underline">Create one</Link>.</p>
          )}
        </div>
      </div>

      {/* Other works by this author */}
      {otherWorks.length > 0 && (
        <div>
          <h2 className="font-semibold mb-3">
            More by {work.authors.map((a) => a.name).join(" & ")}
          </h2>
          <div className="divide-y divide-stone-100">
            {otherWorks.slice(0, 12).map((w) => (
              <Link
                key={w.id}
                to={`/works/${w.id}`}
                className="flex items-center gap-3 py-2 hover:bg-stone-50 -mx-2 px-2 rounded transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{w.title}</div>
                  {w.date_read && <div className="text-xs text-stone-400">{w.date_read}</div>}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {w.significance === "major" && <span className="text-xs text-amber-500">★</span>}
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${STATUS_COLORS[w.status] ?? "bg-stone-100"}`}>
                    {w.status.replace("_", " ")}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
