interface ProgressBarProps {
  read: number;
  total: number;
  color?: string;
  height?: string;
}

export function ProgressBar({ read, total, color = "#10b981", height = "h-2" }: ProgressBarProps) {
  const pct = total > 0 ? (read / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <div className={`flex-1 bg-stone-100 rounded-full ${height} overflow-hidden`}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs text-stone-500 shrink-0">{read}/{total}</span>
    </div>
  );
}
