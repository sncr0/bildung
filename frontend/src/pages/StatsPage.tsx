import { useStats } from "../hooks/useStats";
import { STATUS_HEX_COLORS } from "../components/constants";
import { LoadingSpinner } from "../components/LoadingSpinner";

function Bar({ label, value, max, color }: { label: string; value: number; max: number; color?: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="w-28 shrink-0 text-stone-500 text-right">{label}</span>
      <div className="flex-1 bg-stone-100 rounded-full h-3 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color ?? "#292524" }}
        />
      </div>
      <span className="w-8 text-right font-medium">{value}</span>
    </div>
  );
}

export default function StatsPage() {
  const { data: stats, isLoading } = useStats();

  if (isLoading) return <LoadingSpinner />;
  if (!stats) return null;

  const maxYear = Math.max(...Object.values(stats.by_year), 1);
  const maxLang = Math.max(...Object.values(stats.by_language), 1);

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-8">Stats</h1>

      {/* Headline numbers */}
      <div className="grid grid-cols-3 gap-4 mb-10">
        {[
          { label: "Works", value: stats.total_works },
          { label: "Authors", value: stats.total_authors },
          { label: "Streams", value: stats.total_streams },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white border border-stone-200 rounded-xl p-4 text-center">
            <div className="text-3xl font-bold">{value}</div>
            <div className="text-sm text-stone-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* By status */}
      <section className="mb-8">
        <h2 className="font-semibold mb-3">By status</h2>
        <div className="space-y-2">
          {Object.entries(stats.by_status)
            .sort(([, a], [, b]) => b - a)
            .map(([status, n]) => (
              <Bar key={status} label={status} value={n} max={stats.total_works} color={STATUS_HEX_COLORS[status]} />
            ))}
        </div>
      </section>

      {/* By year */}
      <section className="mb-8">
        <h2 className="font-semibold mb-3">Books read per year</h2>
        <div className="space-y-1.5">
          {Object.entries(stats.by_year)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([yr, n]) => (
              <Bar key={yr} label={yr} value={n} max={maxYear} color="#c0392b" />
            ))}
        </div>
      </section>

      {/* By language */}
      <section>
        <h2 className="font-semibold mb-3">By language</h2>
        <div className="space-y-1.5">
          {Object.entries(stats.by_language)
            .sort(([, a], [, b]) => b - a)
            .map(([lang, n]) => (
              <Bar key={lang} label={lang} value={n} max={maxLang} color="#2563eb" />
            ))}
        </div>
      </section>
    </div>
  );
}
