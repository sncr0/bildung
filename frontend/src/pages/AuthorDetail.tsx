import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getAuthor, type AuthorDetail, type CollectionDetail, type Work } from "../services/api";

const STATUS_COLORS: Record<string, string> = {
  read: "bg-emerald-100 text-emerald-800",
  reading: "bg-blue-100 text-blue-800",
  to_read: "bg-stone-100 text-stone-500",
  abandoned: "bg-red-100 text-red-700",
  unread: "bg-stone-100 text-stone-400",
};

const COLLECTION_TYPE_LABEL: Record<string, string> = {
  major_works: "Major Works",
  minor_works: "Minor Works",
  series: "Series",
  anthology: "Anthology",
};

function WorkRow({ work }: { work: Work }) {
  return (
    <Link
      to={`/works/${work.id}`}
      className="flex items-center gap-3 py-2 hover:bg-stone-50 -mx-2 px-2 rounded transition-colors group"
    >
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium group-hover:text-stone-700 truncate">{work.title}</div>
        {work.date_read && (
          <div className="text-xs text-stone-400">{work.date_read}</div>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {work.significance === "major" && (
          <span className="text-xs text-amber-600 font-medium">★</span>
        )}
        <span className={`text-xs px-1.5 py-0.5 rounded-full ${STATUS_COLORS[work.status] ?? "bg-stone-100"}`}>
          {work.status.replace("_", " ")}
        </span>
      </div>
    </Link>
  );
}

function ProgressBar({ read, total, color = "#10b981" }: { read: number; total: number; color?: string }) {
  const pct = total > 0 ? (read / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-stone-100 rounded-full h-2 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs text-stone-500 shrink-0">{read}/{total}</span>
    </div>
  );
}

function CollectionSection({ collection }: { collection: CollectionDetail }) {
  const complete = collection.read_count === collection.work_count && collection.work_count > 0;
  const sortedWorks = [...collection.works].sort((a, b) => {
    const ao = a.collections.find((c) => c.id === collection.id)?.order ?? 99;
    const bo = b.collections.find((c) => c.id === collection.id)?.order ?? 99;
    if (ao !== bo) return ao - bo;
    return a.title.localeCompare(b.title);
  });

  return (
    <div className="mb-5">
      <div className="flex items-center gap-2 mb-1.5">
        <Link
          to={`/collections/${collection.id}`}
          className="text-sm font-semibold text-stone-700 hover:text-stone-900"
        >
          {collection.name}
        </Link>
        {complete && <span className="text-xs text-emerald-600 font-medium">✓ complete</span>}
        {collection.description && (
          <span className="text-xs text-stone-400 truncate hidden sm:block">{collection.description}</span>
        )}
      </div>
      <div className="mb-2">
        <ProgressBar
          read={collection.read_count}
          total={collection.work_count}
          color={complete ? "#10b981" : "#3b82f6"}
        />
      </div>
      <div className="pl-2 border-l-2 border-stone-100">
        {sortedWorks.map((w) => <WorkRow key={w.id} work={w} />)}
      </div>
    </div>
  );
}

export default function AuthorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [author, setAuthor] = useState<AuthorDetail | null>(null);

  useEffect(() => {
    if (!id) return;
    getAuthor(id).then(setAuthor).catch(console.error);
  }, [id]);

  if (!author) return <p className="text-stone-400">Loading…</p>;

  const majorCollections = author.collections.filter((c) => c.type === "major_works");
  const minorCollections = author.collections.filter((c) => c.type === "minor_works");
  const seriesCollections = author.collections.filter((c) => c.type === "series");
  const anthologyCollections = author.collections.filter((c) => c.type === "anthology");

  // Stats from major_works collection
  const majorColl = majorCollections[0];
  const hasMajorColl = majorColl && majorColl.work_count > 0;
  const mainColor = author.completion_pct >= 1 ? "#10b981" : "#3b82f6";

  return (
    <div className="max-w-2xl">
      <Link to="/authors" className="text-sm text-stone-400 hover:text-stone-600 mb-4 inline-block">
        ← Authors
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-bold">{author.name}</h1>
        {(author.birth_year || author.nationality) && (
          <p className="text-stone-400 text-sm mt-0.5">
            {[
              author.birth_year && (author.death_year
                ? `${author.birth_year}–${author.death_year}`
                : `b. ${author.birth_year}`),
              author.nationality,
              author.primary_language,
            ].filter(Boolean).join(" · ")}
          </p>
        )}
      </div>

      {/* Completion card */}
      <div className="bg-white border border-stone-200 rounded-xl p-4 mb-8">
        {hasMajorColl ? (
          <>
            <div className="flex items-baseline justify-between mb-2">
              <span className="text-sm font-semibold">Major works progress</span>
              <span className="text-2xl font-bold">{Math.round(author.completion_pct * 100)}%</span>
            </div>
            <ProgressBar read={majorColl.read_count} total={majorColl.work_count} color={mainColor} />
            <p className="text-xs text-stone-400 mt-2">
              {majorColl.read_count} of {majorColl.work_count} major works read
              {author.total_works > majorColl.work_count && ` · ${author.total_works} total in library`}
            </p>
          </>
        ) : (
          <>
            <div className="flex items-baseline justify-between mb-2">
              <span className="text-sm font-semibold">Works read</span>
              <span className="text-2xl font-bold">{author.read_works}</span>
            </div>
            <ProgressBar read={author.read_works} total={author.total_works} color="#a8a29e" />
            <p className="text-xs text-stone-400 mt-2">{author.total_works} works in library</p>
          </>
        )}
      </div>

      {/* Major Works */}
      {majorCollections.length > 0 && (
        <section className="mb-6">
          <h2 className="font-semibold text-stone-700 mb-3 uppercase text-xs tracking-widest flex items-center gap-1">
            <span className="text-amber-500">★</span> Major Works
          </h2>
          {majorCollections.map((c) => <CollectionSection key={c.id} collection={c} />)}
        </section>
      )}

      {/* Series */}
      {seriesCollections.length > 0 && (
        <section className="mb-6">
          <h2 className="font-semibold text-stone-700 mb-3 uppercase text-xs tracking-widest">Series</h2>
          {seriesCollections.map((c) => <CollectionSection key={c.id} collection={c} />)}
        </section>
      )}

      {/* Minor Works */}
      {minorCollections.length > 0 && (
        <section className="mb-6">
          <h2 className="font-semibold text-stone-600 mb-3 uppercase text-xs tracking-widest">Minor Works</h2>
          {minorCollections.map((c) => <CollectionSection key={c.id} collection={c} />)}
        </section>
      )}

      {/* Anthologies */}
      {anthologyCollections.length > 0 && (
        <section className="mb-6">
          <h2 className="font-semibold text-stone-500 mb-3 uppercase text-xs tracking-widest">Anthologies</h2>
          {anthologyCollections.map((c) => <CollectionSection key={c.id} collection={c} />)}
        </section>
      )}

      {/* Uncollected works */}
      {author.works.length > 0 && (
        <section className="mb-6">
          <h2 className="font-semibold text-stone-400 mb-2 uppercase text-xs tracking-widest">Other Works</h2>
          {author.works.map((w) => <WorkRow key={w.id} work={w} />)}
        </section>
      )}
    </div>
  );
}
