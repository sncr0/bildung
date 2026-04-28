import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAuthors, type AuthorSummary } from "../services/api";

function CompletionBar({ pct, total, read }: {
  pct: number; total: number; read: number;
}) {
  const color = pct >= 1 ? "#10b981" : pct >= 0.5 ? "#3b82f6" : "#a8a29e";
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="flex-1 bg-stone-100 rounded-full h-1.5 overflow-hidden min-w-[60px]">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.min(pct * 100, 100)}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs text-stone-400 shrink-0 w-20">
        {read}/{total} works
      </span>
    </div>
  );
}

export default function AuthorList() {
  const [authors, setAuthors] = useState<AuthorSummary[]>([]);
  const [search, setSearch] = useState("");
  const [onlyStarted, setOnlyStarted] = useState(false);

  useEffect(() => { getAuthors().then(setAuthors).catch(console.error); }, []);

  const filtered = authors.filter((a) => {
    if (onlyStarted && a.completion_pct === 0) return false;
    if (search && !a.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  // Sort: in-progress first (0 < pct < 1), then not started, then complete
  const sorted = [...filtered].sort((a, b) => {
    const aInProgress = a.completion_pct > 0 && a.completion_pct < 1;
    const bInProgress = b.completion_pct > 0 && b.completion_pct < 1;
    if (aInProgress && !bInProgress) return -1;
    if (!aInProgress && bInProgress) return 1;
    if (a.completion_pct !== b.completion_pct) return a.completion_pct - b.completion_pct;
    return a.name.localeCompare(b.name);
  });

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">Authors</h1>

      <div className="flex gap-3 mb-6 flex-wrap items-center">
        <input
          type="text"
          placeholder="Search author…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-stone-300 rounded px-3 py-1.5 text-sm w-52"
        />
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={onlyStarted}
            onChange={(e) => setOnlyStarted(e.target.checked)}
            className="accent-stone-900"
          />
          <span className="text-stone-600">Started only</span>
        </label>
        <span className="text-sm text-stone-400 self-center ml-auto">
          {sorted.length} {sorted.length === 1 ? "author" : "authors"}
        </span>
      </div>

      <div className="divide-y divide-stone-100">
        {sorted.map((a) => (
          <Link
            key={a.id}
            to={`/authors/${a.id}`}
            className="flex items-center gap-4 py-3 hover:bg-stone-50 -mx-2 px-2 rounded transition-colors group"
          >
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm group-hover:text-stone-700">{a.name}</div>
              {a.total_works > 0 && (
                <CompletionBar pct={a.completion_pct} total={a.total_works} read={a.read_works} />
              )}
            </div>
            <div className="text-right shrink-0">
              <div className="text-sm font-medium">
                {a.completion_pct > 0
                  ? `${Math.round(a.completion_pct * 100)}%`
                  : `${a.total_works}`}
              </div>
              <div className="text-xs text-stone-400">
                {a.completion_pct > 0 ? "complete" : "works"}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
