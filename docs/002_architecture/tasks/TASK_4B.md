# Task 4B — Page Updates + Error Boundaries + Pagination

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **No next task spec** — this is the end of Chain 2 (Frontend). After this, the frontend is clean, reactive, and error-resilient.
3. **Architecture reference:** `02_target_architecture.md` → "Frontend Target Architecture" section — error handling, shared components, TanStack Query patterns.
4. **Hooks reference:** `frontend/src/hooks/` (created in Task 4A). Read every hook file to understand the interface: `{ data, isLoading, error }` for queries, `{ mutate, isPending }` for mutations.
5. **Components reference:** `frontend/src/components/` (created in Task 0A). These are the shared UI components your pages will import.

### Pre-conditions
- [ ] Task 4A is complete (hooks exist)
- [ ] `npm run build` succeeds
- [ ] All pages render correctly
- [ ] TanStack Query is installed and QueryClientProvider is in main.tsx

### Lessons from Previous Task
_To be populated by Task 4A implementer._

---

## Spec

### Goal

Rewrite every page component to use TanStack Query hooks instead of `useEffect` + `useState`. Add an error boundary component for route-level error handling. Add pagination to the work list. After this task, the frontend has a proper data layer, error handling, and pagination.

### What This Enables

This completes the frontend chain. Pages are reactive (automatic refetching after mutations), error-resilient (error boundaries catch failures), and paginated (work list handles large datasets). The frontend is ready for future features.

### Files to Modify

```
frontend/src/pages/WorkList.tsx
frontend/src/pages/WorkDetail.tsx
frontend/src/pages/AuthorList.tsx
frontend/src/pages/AuthorDetail.tsx
frontend/src/pages/StreamList.tsx
frontend/src/pages/StreamDetail.tsx
frontend/src/pages/CollectionDetail.tsx
frontend/src/pages/StatsPage.tsx
frontend/src/pages/AddWork.tsx
frontend/src/App.tsx               — Add error boundary wrapper
```

### Files to Create

```
frontend/src/components/ErrorFallback.tsx
frontend/src/components/LoadingSpinner.tsx
```

### Files NOT to Modify

```
frontend/src/services/api.ts          — DO NOT CHANGE.
frontend/src/hooks/*.ts               — DO NOT CHANGE (unless fixing a bug from Task 4A).
frontend/src/components/constants.ts  — DO NOT CHANGE.
frontend/src/components/StatusBadge.tsx — DO NOT CHANGE.
frontend/src/components/WorkRow.tsx    — DO NOT CHANGE.
frontend/src/components/ProgressBar.tsx — DO NOT CHANGE.
frontend/src/components/CollectionBlock.tsx — DO NOT CHANGE.
```

### Exact Changes

#### Pattern: Replace `useEffect` + `useState` with hooks

Every page currently has this pattern:

```tsx
// Before:
const [works, setWorks] = useState<Work[]>([]);
const [loading, setLoading] = useState(true);

useEffect(() => {
  getWorks({ status }).then(setWorks).finally(() => setLoading(false));
}, [status]);

if (loading) return <p>Loading...</p>;
```

Replace with:

```tsx
// After:
const { data: works, isLoading, error } = useWorks({ status });

if (isLoading) return <LoadingSpinner />;
if (error) return <p>Failed to load works.</p>;
if (!works) return null;
```

**Apply this pattern to every page.** The specific hook differs per page (`useWorks`, `useAuthors`, `useStream`, etc.), but the structure is the same.

#### `components/ErrorFallback.tsx`

A simple error fallback component for error boundaries:

```tsx
interface ErrorFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
}

export function ErrorFallback({ error, resetErrorBoundary }: ErrorFallbackProps) {
  return (
    <div className="text-center py-12">
      <h2 className="text-lg font-semibold text-stone-700 mb-2">Something went wrong</h2>
      <p className="text-stone-500 mb-4">{error.message}</p>
      <button
        onClick={resetErrorBoundary}
        className="px-4 py-2 bg-stone-800 text-white rounded hover:bg-stone-700"
      >
        Try again
      </button>
    </div>
  );
}
```

**Note:** React error boundaries require a class component (or `react-error-boundary` library). Use whichever approach is simpler:

Option A — Install `react-error-boundary` (`npm install react-error-boundary`) and use `<ErrorBoundary>`.

Option B — Write a minimal class component error boundary (no library needed).

**Prefer Option A** — `react-error-boundary` is 2KB, well-maintained, and provides `resetErrorBoundary` for free. If you go with Option B, do NOT implement retry/reset logic — just render the fallback.

#### `components/LoadingSpinner.tsx`

A minimal loading indicator:

```tsx
export function LoadingSpinner() {
  return (
    <div className="flex justify-center py-12">
      <div className="text-stone-400">Loading...</div>
    </div>
  );
}
```

Do NOT add a CSS spinner animation. A text "Loading..." is sufficient. Do NOT install a spinner library.

#### `App.tsx` — Error Boundary

Wrap routes in an error boundary:

```tsx
import { ErrorBoundary } from "react-error-boundary";
import { ErrorFallback } from "./components/ErrorFallback";

// In the render:
<main className="max-w-5xl mx-auto px-6 py-8">
  <ErrorBoundary FallbackComponent={ErrorFallback}>
    <Routes>
      {/* ... existing routes ... */}
    </Routes>
  </ErrorBoundary>
</main>
```

#### Page Rewrites

For each page, the changes are:

1. **Remove** `useState` for data and loading state
2. **Remove** `useEffect` for data fetching
3. **Add** hook import and call
4. **Add** loading/error handling at the top of the component
5. **Keep** all JSX structure and styling identical

**`WorkList.tsx` — also add pagination:**

```tsx
const [page, setPage] = useState(0);
const PAGE_SIZE = 50;
const { data: works, isLoading } = useWorks({
  status: statusFilter,
  author: authorFilter,
  // limit: PAGE_SIZE, offset: page * PAGE_SIZE  -- if the API supports it
});

// At the bottom of the list:
<div className="flex justify-between mt-4">
  <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>
    Previous
  </button>
  <span>Page {page + 1}</span>
  <button onClick={() => setPage(p => p + 1)} disabled={!works || works.length < PAGE_SIZE}>
    Next
  </button>
</div>
```

**The API already supports `limit` and `offset` query parameters.** Check if the `getWorks` function in `api.ts` passes them through. If not, add `limit` and `offset` parameters to `getWorks` and update the `useWorks` hook to accept them. This is the ONE exception to "do not modify api.ts" — pagination requires parameter support.

**`AddWork.tsx` — use mutation hook:**

```tsx
const createWork = useCreateWork();

const handleSubmit = async (e: FormEvent) => {
  e.preventDefault();
  createWork.mutate(formData, {
    onSuccess: () => navigate("/"),
  });
};

// Disable submit button while pending:
<button disabled={createWork.isPending}>
  {createWork.isPending ? "Creating..." : "Add Work"}
</button>
```

### Key Design Decisions (and why)

**1. Error boundary at the route level, not per-component.**
A single boundary around `<Routes>` catches any unhandled error on any page. Per-component error boundaries add complexity without benefit at this scale. If a single component fails, the whole page is likely broken anyway.

**2. Pagination on WorkList only.**
AuthorList and StreamList have fewer items (<100 each). WorkList can grow to hundreds. Paginate where it matters, don't add pagination infrastructure to every list.

**3. `react-error-boundary` over custom class component.**
It's 2KB, handles the boilerplate (resetErrorBoundary, fallback rendering), and is the React community standard. Building a custom one saves nothing.

**4. `LoadingSpinner` is text, not an animated spinner.**
An animated spinner requires either CSS or a library. "Loading..." text is honest, fast to implement, and not worse UX for a personal app.

### DO NOT

1. **Do not change the visual appearance of any page.** The layout, colors, spacing, and content must be identical before and after. The only visible changes are: loading indicator (replacing bare "Loading..."), error messages (new), and pagination controls (new on WorkList).

2. **Do not add optimistic updates to mutations.** Invalidation-based refetching is simpler and sufficient.

3. **Do not add toast notifications.** Error handling is via the error boundary and inline error messages. Toasts require a toast library and context provider — not worth it.

4. **Do not add Suspense boundaries.** TanStack Query supports Suspense mode, but adding it requires restructuring the component tree. Use the standard `isLoading` / `error` pattern.

5. **Do not add skeleton loading states.** "Loading..." text is sufficient. Skeleton screens are a nice-to-have for a future task.

6. **Do not refactor page component structure.** Keep the same component boundaries. If a page has inline JSX for a section, leave it inline. Don't extract new sub-components.

7. **Do not remove the `api.ts` functions or mark them as deprecated.** The hooks wrap them; they're still the API client.

8. **Do not add infinite scroll.** Button-based pagination is simpler and works for this use case.

### Acceptance Criteria

- [ ] Every page uses TanStack Query hooks instead of `useEffect` + `useState` for data fetching
- [ ] No page component imports `useEffect` for data fetching (some may still use `useEffect` for non-data concerns)
- [ ] `ErrorFallback.tsx` and `LoadingSpinner.tsx` exist in `components/`
- [ ] `App.tsx` has an error boundary around routes
- [ ] WorkList has pagination controls
- [ ] AddWork uses mutation hook with loading state
- [ ] `npm run build` succeeds with zero errors
- [ ] Every page renders identically to before (visual check):
  - [ ] `/` — Work list with filters and pagination
  - [ ] `/works/{id}` — Work detail
  - [ ] `/authors` — Author list
  - [ ] `/authors/{id}` — Author detail with collections
  - [ ] `/streams` — Stream list
  - [ ] `/streams/{id}` — Stream detail
  - [ ] `/collections/{id}` — Collection detail
  - [ ] `/stats` — Stats page
  - [ ] `/add` — Add work form (test create flow)
- [ ] Loading states display while data is fetching
- [ ] Error boundary catches and displays errors (test by temporarily breaking an API URL)

### Verification

```bash
cd frontend

# Build succeeds
npm run build

# TypeScript passes
npx tsc --noEmit

# No useEffect for data fetching
grep -rn "useEffect.*get\|useEffect.*fetch" src/pages/
# Expected: 0 results (or only non-data useEffects like scroll handlers)

# Dev server
npm run dev
# Check every page listed in acceptance criteria
# Test pagination on work list
# Test add work flow
# Test error boundary (temporarily change API base URL to trigger errors)
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "Used react-error-boundary library, not custom class component" -->

### Harder Than Expected
<!-- E.g., "WorkList pagination required adding limit/offset to the api.ts getWorks function" -->

### Watch Out
<!-- E.g., "StatsPage chart still re-renders on every refetch — may need memo" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
