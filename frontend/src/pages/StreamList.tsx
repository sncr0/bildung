import { useState } from "react";
import { Link } from "react-router-dom";
import { useStreams, useCreateStream, useDeleteStream } from "../hooks/useStreams";
import { LoadingSpinner } from "../components/LoadingSpinner";

export default function StreamList() {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", color: "#6366f1" });

  const { data: streams, isLoading } = useStreams();
  const createStream = useCreateStream();
  const deleteStream = useDeleteStream();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    createStream.mutate(
      { name: form.name, description: form.description || undefined, color: form.color },
      {
        onSuccess: () => {
          setForm({ name: "", description: "", color: "#6366f1" });
          setShowForm(false);
        },
      }
    );
  };

  const remove = (id: string, name: string) => {
    if (!confirm(`Delete stream "${name}"? This will not delete the works.`)) return;
    deleteStream.mutate(id);
  };

  if (isLoading) return <LoadingSpinner />;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Streams</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="text-sm px-3 py-1.5 bg-stone-900 text-white rounded hover:bg-stone-700"
        >
          {showForm ? "Cancel" : "+ New stream"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={submit} className="mb-6 p-4 border border-stone-200 rounded-lg bg-white space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm col-span-2">
              <span className="text-stone-500 text-xs">Name *</span>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="block w-full border border-stone-300 rounded px-2 py-1.5 mt-0.5"
                placeholder="My Kant Path"
              />
            </label>
            <label className="block text-sm col-span-2">
              <span className="text-stone-500 text-xs">Description</span>
              <input
                type="text"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="block w-full border border-stone-300 rounded px-2 py-1.5 mt-0.5"
              />
            </label>
            <label className="block text-sm">
              <span className="text-stone-500 text-xs">Colour</span>
              <div className="flex gap-2 items-center mt-0.5">
                <input
                  type="color"
                  value={form.color}
                  onChange={(e) => setForm({ ...form, color: e.target.value })}
                  className="h-8 w-14 border border-stone-300 rounded cursor-pointer"
                />
                <span className="text-stone-500 text-xs">{form.color}</span>
              </div>
            </label>
          </div>
          <button
            type="submit"
            disabled={createStream.isPending}
            className="bg-stone-900 text-white text-sm px-4 py-1.5 rounded hover:bg-stone-700 disabled:opacity-50"
          >
            {createStream.isPending ? "Creating…" : "Create stream"}
          </button>
        </form>
      )}

      {(streams ?? []).length === 0 ? (
        <p className="text-stone-400">No streams yet. Create your first one above.</p>
      ) : (
        <div className="space-y-2">
          {(streams ?? []).map((s) => (
            <div key={s.id} className="flex items-center gap-3 p-3 bg-white border border-stone-200 rounded-lg hover:border-stone-300 transition-colors">
              <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: s.color ?? "#999" }} />
              <Link to={`/streams/${s.id}`} className="flex-1 font-medium hover:text-stone-600">
                {s.name}
              </Link>
              <span className="text-sm text-stone-400">
                {s.work_count} works{s.collection_count > 0 ? ` · ${s.collection_count} collections` : ""}
              </span>
              {s.description && (
                <span className="text-sm text-stone-400 truncate max-w-xs hidden md:block">{s.description}</span>
              )}
              <button
                onClick={() => remove(s.id, s.name)}
                className="text-stone-300 hover:text-red-500 text-sm transition-colors"
                title="Delete stream"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
