export const STATUS_LABELS: Record<string, string> = {
  read: "Read",
  reading: "Reading",
  to_read: "To read",
  abandoned: "Abandoned",
  unread: "Unread",
};

export const STATUS_COLORS: Record<string, string> = {
  read: "bg-emerald-100 text-emerald-800",
  reading: "bg-blue-100 text-blue-800",
  to_read: "bg-stone-100 text-stone-500",
  abandoned: "bg-red-100 text-red-700",
  unread: "bg-stone-100 text-stone-400",
};

// Hex colors used in StatsPage chart bars
export const STATUS_HEX_COLORS: Record<string, string> = {
  read: "#10b981",
  reading: "#3b82f6",
  to_read: "#a8a29e",
  abandoned: "#ef4444",
};

export const TYPE_LABELS: Record<string, string> = {
  major_works: "Major Works",
  minor_works: "Minor Works",
  series: "Series",
  anthology: "Anthology",
};
