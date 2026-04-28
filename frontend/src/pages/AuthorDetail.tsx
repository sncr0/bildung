import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getAuthor, type AuthorDetail } from "../services/api";
import { WorkRow } from "../components/WorkRow";
import { ProgressBar } from "../components/ProgressBar";
import { CollectionBlock } from "../components/CollectionBlock";

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
          {majorCollections.map((c) => <CollectionBlock key={c.id} collection={c} accentColor="#3b82f6" />)}
        </section>
      )}

      {/* Series */}
      {seriesCollections.length > 0 && (
        <section className="mb-6">
          <h2 className="font-semibold text-stone-700 mb-3 uppercase text-xs tracking-widest">Series</h2>
          {seriesCollections.map((c) => <CollectionBlock key={c.id} collection={c} accentColor="#3b82f6" />)}
        </section>
      )}

      {/* Minor Works */}
      {minorCollections.length > 0 && (
        <section className="mb-6">
          <h2 className="font-semibold text-stone-600 mb-3 uppercase text-xs tracking-widest">Minor Works</h2>
          {minorCollections.map((c) => <CollectionBlock key={c.id} collection={c} accentColor="#3b82f6" />)}
        </section>
      )}

      {/* Anthologies */}
      {anthologyCollections.length > 0 && (
        <section className="mb-6">
          <h2 className="font-semibold text-stone-500 mb-3 uppercase text-xs tracking-widest">Anthologies</h2>
          {anthologyCollections.map((c) => <CollectionBlock key={c.id} collection={c} accentColor="#3b82f6" />)}
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
