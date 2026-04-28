import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getWorks, getStreams, type Work, type Stream } from "../services/api";

const STATUS_LABELS: Record<string, string> = {
  read: "Read",
  reading: "Reading",
  to_read: "To read",
  abandoned: "Abandoned",
  unread: "Unread",
};

const STATUS_COLORS: Record<string, string> = {
  read: "bg-emerald-100 text-emerald-800",
  reading: "bg-blue-100 text-blue-800",
  to_read: "bg-stone-100 text-stone-600",
  abandoned: "bg-red-100 text-red-700",
  unread: "bg-stone-100 text-stone-500",
};

export default function WorkList() {
  const [works, setWorks] = useState<Work[]>([]);
  const [streams, setStreams] = useState<Stream[]>([]);
  const [status, setStatus] = useState("");
  const [author, setAuthor] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStreams().then(setStreams).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    getWorks({ status: status || undefined, author: author || undefined })
      .then(setWorks)
      .finally(() => setLoading(false));
  }, [status, author]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Books</h1>

      {/* Filters */}
      <div className="flex gap-3 mb-6 flex-wrap">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="border border-stone-300 rounded px-3 py-1.5 text-sm bg-white"
        >
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Filter by author…"
          value={author}
          onChange={(e) => setAuthor(e.target.value)}
          className="border border-stone-300 rounded px-3 py-1.5 text-sm w-52"
        />
        <span className="text-sm text-stone-500 self-center">
          {works.length} {works.length === 1 ? "work" : "works"}
        </span>
      </div>

      {loading ? (
        <p className="text-stone-400">Loading…</p>
      ) : (
        <div className="divide-y divide-stone-200">
          {works.map((w) => (
            <Link
              key={w.id}
              to={`/works/${w.id}`}
              className="flex items-start gap-4 py-3 hover:bg-stone-100 -mx-2 px-2 rounded transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{w.title}</div>
                <div className="text-sm text-stone-500">
                  {w.authors.map((a) => a.name).join(", ")}
                  {w.date_read && (
                    <span className="ml-2 text-stone-400">· {w.date_read}</span>
                  )}
                  {w.language_read_in && (
                    <span className="ml-2 text-stone-400">· {w.language_read_in}</span>
                  )}
                </div>
              </div>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 mt-0.5 ${STATUS_COLORS[w.status] ?? "bg-stone-100"}`}
              >
                {STATUS_LABELS[w.status] ?? w.status}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
