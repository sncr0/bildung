import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getCollection, type CollectionDetail } from "../services/api";
import { WorkRow } from "../components/WorkRow";
import { ProgressBar } from "../components/ProgressBar";
import { TYPE_LABELS } from "../components/constants";

export default function CollectionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [collection, setCollection] = useState<CollectionDetail | null>(null);

  useEffect(() => {
    if (!id) return;
    getCollection(id).then(setCollection).catch(console.error);
  }, [id]);

  if (!collection) return <p className="text-stone-400">Loading…</p>;

  const complete = collection.read_count === collection.work_count && collection.work_count > 0;
  const color = complete ? "#10b981" : "#3b82f6";

  const sortedWorks = [...collection.works].sort((a, b) => {
    const ao = a.collections.find((c) => c.id === collection.id)?.order ?? 99;
    const bo = b.collections.find((c) => c.id === collection.id)?.order ?? 99;
    if (ao !== bo) return ao - bo;
    return a.title.localeCompare(b.title);
  });

  return (
    <div className="max-w-2xl">
      <Link to="/streams" className="text-sm text-stone-400 hover:text-stone-600 mb-4 inline-block">
        ← Streams
      </Link>

      <div className="mb-2">
        <span className="text-xs text-stone-400 uppercase tracking-widest">
          {TYPE_LABELS[collection.type] ?? collection.type}
        </span>
      </div>
      <h1 className="text-2xl font-bold mb-1">{collection.name}</h1>
      {collection.description && (
        <p className="text-stone-500 text-sm mb-4">{collection.description}</p>
      )}

      {/* Progress */}
      <div className="bg-white border border-stone-200 rounded-xl p-4 mb-8">
        <div className="flex items-baseline justify-between mb-2">
          <span className="text-sm font-semibold">Progress</span>
          <div className="flex items-center gap-2">
            {complete && <span className="text-xs text-emerald-600 font-medium">✓ complete</span>}
            <span className="text-2xl font-bold">
              {collection.work_count > 0 ? Math.round((collection.read_count / collection.work_count) * 100) : 0}%
            </span>
          </div>
        </div>
        <ProgressBar read={collection.read_count} total={collection.work_count} color={color} />
        <p className="text-xs text-stone-400 mt-2">
          {collection.read_count} of {collection.work_count} works read
        </p>
      </div>

      {/* Works list */}
      <div className="divide-y divide-stone-100">
        {sortedWorks.map((w) => {
          const order = w.collections.find((c) => c.id === collection.id)?.order ?? null;
          return <WorkRow key={w.id} work={w} order={order} />;
        })}
      </div>

      {sortedWorks.length === 0 && (
        <p className="text-stone-400 text-sm">No works in this collection yet.</p>
      )}
    </div>
  );
}
