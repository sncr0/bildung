import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getStream, updateStream, type StreamDetail, type CollectionDetail, type Work } from "../services/api";

const STATUS_COLORS: Record<string, string> = {
  read: "bg-emerald-100 text-emerald-800",
  reading: "bg-blue-100 text-blue-800",
  to_read: "bg-stone-100 text-stone-500",
  abandoned: "bg-red-100 text-red-700",
  unread: "bg-stone-100 text-stone-400",
};

const TYPE_LABEL: Record<string, string> = {
  major_works: "Major Works",
  minor_works: "Minor Works",
  series: "Series",
  anthology: "Anthology",
};

function ProgressBar({ read, total, color }: { read: number; total: number; color: string }) {
  const pct = total > 0 ? (read / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-stone-100 rounded-full h-1.5 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs text-stone-400 shrink-0">{read}/{total}</span>
    </div>
  );
}

function WorkRow({ work }: { work: Work }) {
  return (
    <Link
      to={`/works/${work.id}`}
      className="flex items-center gap-3 py-2 hover:bg-stone-50 -mx-2 px-2 rounded transition-colors"
    >
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{work.title}</div>
        <div className="text-xs text-stone-400 truncate">
          {work.authors.map((a) => a.name).join(", ")}
          {work.date_read && <span className="ml-1">· {work.date_read}</span>}
        </div>
      </div>
      <span className={`text-xs px-1.5 py-0.5 rounded-full shrink-0 ${STATUS_COLORS[work.status] ?? "bg-stone-100"}`}>
        {work.status.replace("_", " ")}
      </span>
    </Link>
  );
}

function CollectionBlock({ collection, accentColor }: { collection: CollectionDetail; accentColor: string }) {
  const complete = collection.read_count === collection.work_count && collection.work_count > 0;
  const sortedWorks = [...collection.works].sort((a, b) => {
    const ao = a.collections.find((c) => c.id === collection.id)?.order ?? 99;
    const bo = b.collections.find((c) => c.id === collection.id)?.order ?? 99;
    if (ao !== bo) return ao - bo;
    return a.title.localeCompare(b.title);
  });

  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs text-stone-400 uppercase tracking-wide">{TYPE_LABEL[collection.type] ?? collection.type}</span>
        <span className="text-stone-300">·</span>
        <Link
          to={`/collections/${collection.id}`}
          className="text-sm font-semibold text-stone-700 hover:text-stone-900"
        >
          {collection.name}
        </Link>
        {complete && <span className="text-xs text-emerald-600 font-medium ml-1">✓</span>}
      </div>
      <div className="mb-2">
        <ProgressBar
          read={collection.read_count}
          total={collection.work_count}
          color={complete ? "#10b981" : accentColor}
        />
      </div>
      <div className="pl-3 border-l-2 border-stone-100 space-y-0">
        {sortedWorks.map((w) => <WorkRow key={w.id} work={w} />)}
      </div>
    </div>
  );
}

export default function StreamDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [stream, setStream] = useState<StreamDetail | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", color: "" });
  const [saving, setSaving] = useState(false);

  const load = () => {
    if (!id) return;
    getStream(id).then((s) => {
      setStream(s);
      setForm({ name: s.name, description: s.description ?? "", color: s.color ?? "#6366f1" });
    }).catch(console.error);
  };

  useEffect(() => { load(); }, [id]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setSaving(true);
    try {
      await updateStream(id, { name: form.name, description: form.description || undefined, color: form.color });
      setEditing(false);
      load();
    } finally {
      setSaving(false);
    }
  };

  if (!stream) return <p className="text-stone-400">Loading…</p>;

  const accentColor = stream.color ?? "#6366f1";

  // Group collections by type for ordering
  const majorColls = stream.collections.filter((c) => c.type === "major_works");
  const minorColls = stream.collections.filter((c) => c.type === "minor_works");
  const seriesColls = stream.collections.filter((c) => c.type === "series");
  const anthologyColls = stream.collections.filter((c) => c.type === "anthology");

  const totalRead = stream.collections.reduce((sum, c) => sum + c.read_count, 0)
    + stream.works.filter((w) => w.status === "read").length;

  return (
    <div className="max-w-2xl">
      <Link to="/streams" className="text-sm text-stone-400 hover:text-stone-600 mb-4 inline-block">← Streams</Link>

      <div className="flex items-center gap-3 mb-1">
        <span className="w-4 h-4 rounded-full shrink-0" style={{ backgroundColor: accentColor }} />
        <h1 className="text-2xl font-bold">{stream.name}</h1>
        <button
          onClick={() => setEditing(!editing)}
          className="ml-auto text-sm px-3 py-1 border border-stone-300 rounded hover:bg-stone-100"
        >
          {editing ? "Cancel" : "Edit"}
        </button>
      </div>

      {stream.description && (
        <p className="text-stone-500 mb-4 ml-7">{stream.description}</p>
      )}

      {editing && (
        <form onSubmit={save} className="mb-6 p-4 border border-stone-200 rounded-lg bg-white space-y-3">
          <label className="block text-sm">
            <span className="text-stone-500 text-xs">Name</span>
            <input type="text" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="block w-full border border-stone-300 rounded px-2 py-1.5 mt-0.5" />
          </label>
          <label className="block text-sm">
            <span className="text-stone-500 text-xs">Description</span>
            <input type="text" value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="block w-full border border-stone-300 rounded px-2 py-1.5 mt-0.5" />
          </label>
          <label className="block text-sm">
            <span className="text-stone-500 text-xs">Colour</span>
            <div className="flex gap-2 items-center mt-0.5">
              <input type="color" value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
                className="h-8 w-14 border border-stone-300 rounded" />
            </div>
          </label>
          <button type="submit" disabled={saving}
            className="bg-stone-900 text-white text-sm px-4 py-1.5 rounded hover:bg-stone-700 disabled:opacity-50">
            {saving ? "Saving…" : "Save"}
          </button>
        </form>
      )}

      {/* Summary bar */}
      <div className="flex gap-4 text-sm text-stone-500 mb-6 ml-7">
        <span>{stream.work_count} works total</span>
        <span>·</span>
        <span>{totalRead} read</span>
        {stream.collection_count > 0 && (
          <>
            <span>·</span>
            <span>{stream.collection_count} collections</span>
          </>
        )}
      </div>

      {/* Major Works */}
      {majorColls.length > 0 && (
        <section className="mb-4">
          <h2 className="font-semibold text-stone-700 mb-3 uppercase text-xs tracking-widest flex items-center gap-1">
            <span className="text-amber-500">★</span> Major Works
          </h2>
          {majorColls.map((c) => <CollectionBlock key={c.id} collection={c} accentColor={accentColor} />)}
        </section>
      )}

      {/* Series */}
      {seriesColls.length > 0 && (
        <section className="mb-4">
          <h2 className="font-semibold text-stone-700 mb-3 uppercase text-xs tracking-widest">Series</h2>
          {seriesColls.map((c) => <CollectionBlock key={c.id} collection={c} accentColor={accentColor} />)}
        </section>
      )}

      {/* Minor Works */}
      {minorColls.length > 0 && (
        <section className="mb-4">
          <h2 className="font-semibold text-stone-600 mb-3 uppercase text-xs tracking-widest">Minor Works</h2>
          {minorColls.map((c) => <CollectionBlock key={c.id} collection={c} accentColor={accentColor} />)}
        </section>
      )}

      {/* Anthologies */}
      {anthologyColls.length > 0 && (
        <section className="mb-4">
          <h2 className="font-semibold text-stone-500 mb-3 uppercase text-xs tracking-widest">Anthologies</h2>
          {anthologyColls.map((c) => <CollectionBlock key={c.id} collection={c} accentColor={accentColor} />)}
        </section>
      )}

      {/* Direct works (not in any collection) */}
      {stream.works.length > 0 && (
        <section className="mb-4">
          {(stream.collections.length > 0) && (
            <h2 className="font-semibold text-stone-400 mb-2 uppercase text-xs tracking-widest">Other Works</h2>
          )}
          <div className="divide-y divide-stone-100">
            {stream.works.map((w) => <WorkRow key={w.id} work={w} />)}
          </div>
        </section>
      )}

      {stream.collections.length === 0 && stream.works.length === 0 && (
        <p className="text-stone-400 text-sm">No works assigned yet.</p>
      )}
    </div>
  );
}
