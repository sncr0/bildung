import { useState } from "react";
import { Link } from "react-router-dom";
import { STATUS_LABELS, STATUS_COLORS } from "../components/constants";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { useWorks } from "../hooks/useWorks";

const PAGE_SIZE = 50;

export default function WorkList() {
  const [status, setStatus] = useState("");
  const [author, setAuthor] = useState("");
  const [page, setPage] = useState(0);

  const { data: works, isLoading } = useWorks({
    status: status || undefined,
    author: author || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  const handleStatusChange = (s: string) => { setStatus(s); setPage(0); };
  const handleAuthorChange = (a: string) => { setAuthor(a); setPage(0); };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Books</h1>

      {/* Filters */}
      <div className="flex gap-3 mb-6 flex-wrap">
        <select
          value={status}
          onChange={(e) => handleStatusChange(e.target.value)}
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
          onChange={(e) => handleAuthorChange(e.target.value)}
          className="border border-stone-300 rounded px-3 py-1.5 text-sm w-52"
        />
        <span className="text-sm text-stone-500 self-center">
          {works?.length ?? 0} {(works?.length ?? 0) === 1 ? "work" : "works"}
        </span>
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          <div className="divide-y divide-stone-200">
            {(works ?? []).map((w) => (
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

          {/* Pagination */}
          <div className="flex justify-between items-center mt-6 text-sm">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1.5 border border-stone-300 rounded hover:bg-stone-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ← Previous
            </button>
            <span className="text-stone-400">Page {page + 1}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={!works || works.length < PAGE_SIZE}
              className="px-3 py-1.5 border border-stone-300 rounded hover:bg-stone-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  );
}
