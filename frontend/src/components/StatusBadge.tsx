import { STATUS_COLORS, STATUS_LABELS } from "./constants";

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded-full ${STATUS_COLORS[status] ?? "bg-stone-100"}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}
