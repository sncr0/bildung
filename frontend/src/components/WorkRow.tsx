import { Link } from "react-router-dom";
import { type Work } from "../services/api";
import { STATUS_COLORS } from "./constants";

interface WorkRowProps {
  work: Work;
  order?: number | null;
}

export function WorkRow({ work, order = null }: WorkRowProps) {
  return (
    <Link
      to={`/works/${work.id}`}
      className="flex items-center gap-3 py-2 hover:bg-stone-50 -mx-2 px-2 rounded transition-colors group"
    >
      {order != null && (
        <span className="text-xs text-stone-400 font-mono w-5 shrink-0 text-right">{order}</span>
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium group-hover:text-stone-700 truncate">{work.title}</div>
        <div className="text-xs text-stone-400 truncate">
          {work.authors.map((a) => a.name).join(", ")}
          {work.date_read && <span className="ml-1">· {work.date_read}</span>}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {work.significance === "major" && <span className="text-xs text-amber-600">★</span>}
        <span className={`text-xs px-1.5 py-0.5 rounded-full ${STATUS_COLORS[work.status] ?? "bg-stone-100"}`}>
          {work.status.replace("_", " ")}
        </span>
      </div>
    </Link>
  );
}
