import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createWork } from "../services/api";

const LANGS = ["EN", "NL", "FR", "DE", "Other"];
const STATUS_OPTIONS = ["to_read", "reading", "read"];
const SOURCE_OPTIONS = ["fiction", "primary", "secondary"];

export default function AddWork() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: "",
    author: "",
    language_read_in: "EN",
    status: "to_read" as const,
    date_read: "",
    source_type: "fiction" as const,
    personal_note: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (field: string, value: string) =>
    setForm((f) => ({ ...f, [field]: value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim() || !form.author.trim()) {
      setError("Title and author are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const work = await createWork({
        ...form,
        date_read: form.date_read || undefined,
        personal_note: form.personal_note || undefined,
      });
      navigate(`/works/${work.id}`);
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold mb-6">Add a book</h1>

      <form onSubmit={submit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium">Title *</span>
          <input
            type="text"
            value={form.title}
            onChange={(e) => set("title", e.target.value)}
            className="block w-full border border-stone-300 rounded px-3 py-2 mt-1 text-sm"
            placeholder="Crime and Punishment"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium">Author *</span>
          <input
            type="text"
            value={form.author}
            onChange={(e) => set("author", e.target.value)}
            className="block w-full border border-stone-300 rounded px-3 py-2 mt-1 text-sm"
            placeholder="Fyodor Dostoyevsky"
          />
        </label>

        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-sm font-medium">Status</span>
            <select
              value={form.status}
              onChange={(e) => set("status", e.target.value)}
              className="block w-full border border-stone-300 rounded px-3 py-2 mt-1 text-sm bg-white"
            >
              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium">Language</span>
            <select
              value={form.language_read_in}
              onChange={(e) => set("language_read_in", e.target.value)}
              className="block w-full border border-stone-300 rounded px-3 py-2 mt-1 text-sm bg-white"
            >
              {LANGS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium">Source type</span>
            <select
              value={form.source_type}
              onChange={(e) => set("source_type", e.target.value)}
              className="block w-full border border-stone-300 rounded px-3 py-2 mt-1 text-sm bg-white"
            >
              {SOURCE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium">Year / date read</span>
            <input
              type="text"
              value={form.date_read}
              onChange={(e) => set("date_read", e.target.value)}
              placeholder="2024 or 2024-03-15"
              className="block w-full border border-stone-300 rounded px-3 py-2 mt-1 text-sm"
            />
          </label>
        </div>

        <label className="block">
          <span className="text-sm font-medium">Personal note</span>
          <textarea
            value={form.personal_note}
            onChange={(e) => set("personal_note", e.target.value)}
            rows={3}
            className="block w-full border border-stone-300 rounded px-3 py-2 mt-1 text-sm resize-none"
            placeholder="Optional personal note…"
          />
        </label>

        {error && <p className="text-red-600 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={saving}
          className="w-full bg-stone-900 text-white py-2 rounded hover:bg-stone-700 disabled:opacity-50 font-medium"
        >
          {saving ? "Adding…" : "Add book"}
        </button>
      </form>
    </div>
  );
}
