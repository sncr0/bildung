import { Link } from "react-router-dom";
import { type CollectionDetail } from "../services/api";
import { TYPE_LABELS } from "./constants";
import { WorkRow } from "./WorkRow";
import { ProgressBar } from "./ProgressBar";

interface CollectionBlockProps {
  collection: CollectionDetail;
  accentColor: string;
}

export function CollectionBlock({ collection, accentColor }: CollectionBlockProps) {
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
        <span className="text-xs text-stone-400 uppercase tracking-wide">
          {TYPE_LABELS[collection.type] ?? collection.type}
        </span>
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
      <div className="pl-3 border-l-2 border-stone-100">
        {sortedWorks.map((w) => <WorkRow key={w.id} work={w} />)}
      </div>
    </div>
  );
}
