# Task 0A — Extract Shared Frontend Components

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_4A.md` — TanStack Query + hooks. That task will rewrite every page to use hooks instead of `useEffect`. If you leave components tightly coupled to page-level state here, Task 4A has to untangle it. Extract components cleanly with clear props interfaces.
3. **Architecture reference:** `02_target_architecture.md` → "Frontend Target Architecture → Shared components" section

### Pre-conditions
- [ ] Frontend dev server starts: `cd frontend && npm run dev`
- [ ] All pages render without console errors: /, /authors, /streams, /stats, /add

### Lessons from Previous Task
_This is the first task in the frontend chain. No prior context._

---

## Spec

### Goal

Extract duplicated UI components and constants from 5 page files into a shared `components/` directory. This is a mechanical refactor — no logic changes, no new features, no redesign.

### What This Enables

Task 4A (TanStack Query) will rewrite every page to use data-fetching hooks. If STATUS_COLORS is defined in 5 files, that task has to update 5 files. If it's in one `constants.ts`, the task is simpler and less error-prone. Similarly, Task 4A will pass `isLoading` and `error` props into components — those components need to exist as shared code first.

### Files to Create

```
frontend/src/components/constants.ts
frontend/src/components/StatusBadge.tsx
frontend/src/components/WorkRow.tsx
frontend/src/components/ProgressBar.tsx
frontend/src/components/CollectionBlock.tsx
```

### Files to Modify

```
frontend/src/pages/WorkList.tsx         — import from components/
frontend/src/pages/WorkDetail.tsx       — import from components/
frontend/src/pages/AuthorList.tsx       — import from components/
frontend/src/pages/AuthorDetail.tsx     — import from components/
frontend/src/pages/StreamList.tsx       — import from components/ (only constants)
frontend/src/pages/StreamDetail.tsx     — import from components/
frontend/src/pages/CollectionDetail.tsx — import from components/
frontend/src/pages/StatsPage.tsx        — import from components/ (only constants)
```

### Exact Changes

#### `components/constants.ts`
Consolidate these duplicated definitions into one file:

```typescript
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

// Used in StatsPage — hex colors for chart bars
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
```

**Note:** `WorkList.tsx` currently has slightly different `STATUS_COLORS` values (it uses `text-stone-600` for `to_read` and `text-stone-500` for `unread`). The other 4 files use `text-stone-500` / `text-stone-400`. **Use the majority version** (`text-stone-500` / `text-stone-400`). Do NOT create per-page variants.

#### `components/StatusBadge.tsx`
Extract the status pill that appears in WorkList, WorkDetail, and all detail pages:

```typescript
import { STATUS_COLORS, STATUS_LABELS } from "./constants";

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded-full ${STATUS_COLORS[status] ?? "bg-stone-100"}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}
```

**WorkList.tsx** uses a slightly wider variant (`px-2 py-0.5 rounded-full font-medium`). Pass an optional `size` prop if needed, or just standardize on the smaller version. Do NOT create two badge components.

#### `components/WorkRow.tsx`
This component exists in AuthorDetail, StreamDetail, and CollectionDetail with slight variations. The core is identical: a `<Link>` with title, author names, date_read, and a status badge.

Props interface:
```typescript
import { type Work } from "../services/api";

interface WorkRowProps {
  work: Work;
  order?: number | null;  // CollectionDetail passes this
}
```

**Important:** The `order` prop is only used by CollectionDetail. AuthorDetail and StreamDetail don't pass it. Default to `null` and conditionally render the order number.

#### `components/ProgressBar.tsx`
Three pages have this. The interface varies slightly:
- AuthorList: `h-1.5`, dynamic color based on completion
- AuthorDetail: `h-2`, receives explicit `color` prop
- StreamDetail: `h-1.5`, receives explicit `color` prop
- CollectionDetail: `h-2`, receives explicit `color` prop

Unify with:
```typescript
interface ProgressBarProps {
  read: number;
  total: number;
  color?: string;   // defaults to "#10b981"
  height?: string;  // defaults to "h-2"
}
```

#### `components/CollectionBlock.tsx`
This exists in StreamDetail and AuthorDetail. It renders a collection header, progress bar, and work list. Extract once, import twice.

Props should take the collection data, an accent color, and nothing else. Do NOT make it depend on page-specific state.

### DO NOT

1. **Do not change any component's visual appearance.** The goal is extraction, not redesign. If a component looks a certain way today, it should look identical after extraction. Pixel-test by eye.

2. **Do not add new props "for future use."** If WorkRow doesn't currently accept an `onClick` prop, don't add one because "Task 4A might need it." Task 4A will add what it needs.

3. **Do not create a barrel export (`components/index.ts`).** Named imports from specific files are clearer than barrel exports that hide what's actually used.

4. **Do not install any new npm packages.** This task uses only React and the existing api types.

5. **Do not create abstract base components.** No `<Card>`, `<List>`, `<Badge>` generic wrappers. Extract the specific, concrete components that are currently duplicated.

6. **Do not change the api.ts types.** The component props should reference the existing types from `services/api.ts`.

7. **Do not refactor page logic.** Pages should change only their imports — from local definitions to component imports. Do not rearrange JSX structure, change data fetching, or modify state management. That's Task 4A's job.

### Acceptance Criteria

- [ ] `frontend/src/components/` directory exists with 5 files
- [ ] No page file defines `STATUS_COLORS`, `STATUS_LABELS`, `TYPE_LABELS`, or `STATUS_HEX_COLORS` locally
- [ ] No page file defines a `WorkRow` or `ProgressBar` component locally
- [ ] `npm run build` succeeds with zero errors
- [ ] Every page renders identically to before (visual check):
  - [ ] `/` — Book list with status badges and filters
  - [ ] `/works/{any-id}` — Work detail with metadata, streams, other works
  - [ ] `/authors` — Author list with completion bars
  - [ ] `/authors/{any-id}` — Author detail with collections and progress
  - [ ] `/streams` — Stream list
  - [ ] `/streams/{any-id}` — Stream detail with collection blocks
  - [ ] `/collections/{any-id}` — Collection detail with ordered works
  - [ ] `/stats` — Stats page with charts
  - [ ] `/add` — Add work form

### Verification

```bash
cd frontend
npm run build          # Must succeed with 0 errors
npm run dev            # Start dev server, then manually check all pages above
```

Also verify no local duplicates remain:
```bash
grep -r "STATUS_COLORS" frontend/src/pages/    # Should return 0 results
grep -r "WorkRow" frontend/src/pages/          # Should return only import lines
grep -r "ProgressBar" frontend/src/pages/      # Should return only import lines
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- What choices did you make? E.g., "Standardized ProgressBar height to h-2 everywhere" -->

### Harder Than Expected
<!-- What was tricky? E.g., "CollectionBlock in StreamDetail had an extra accentColor prop" -->

### Watch Out (for Task 4A)
<!-- What should the next implementer know? E.g., "WorkRow accepts Work type directly, no wrapper needed" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
