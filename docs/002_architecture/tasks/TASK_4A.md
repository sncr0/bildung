# Task 4A — TanStack Query + Custom Hooks

## Kickoff

### Read Before Starting
1. **This spec** (you're reading it)
2. **Next task spec:** `TASK_4B.md` — Page updates + error boundaries + pagination. That task rewrites every page to use the hooks you create here. If the hook interfaces are wrong (wrong query keys, wrong parameter shapes, missing mutation hooks), every page rewrite in Task 4B will be fighting the data layer instead of simplifying the UI.
3. **Architecture reference:** `02_target_architecture.md` → "Frontend Target Architecture → Data layer: TanStack Query (React Query)" section.
4. **Component reference:** `frontend/src/components/` (created in Task 0A). The shared components already exist. This task adds the data layer.

### Pre-conditions
- [ ] Task 0A is complete (shared components extracted)
- [ ] Frontend builds: `cd frontend && npm run build`
- [ ] All pages render without console errors
- [ ] `api.ts` is unchanged and working

### Lessons from Previous Task
_To be populated by Task 0A implementer._

---

## Spec

### Goal

Install TanStack Query, set up the QueryClient provider, and create custom hooks that wrap every API function in `api.ts`. Pages will continue to use `useEffect` + `useState` in this task — Task 4B will rewrite them to use hooks. This task creates the data layer without changing any existing page behavior.

### What This Enables

Task 4B will replace every `useEffect` + `useState` pattern with a single hook call. Without the hooks existing first, Task 4B would have to both create the data layer and rewrite pages simultaneously — too much scope for one task.

### Files to Modify

```
frontend/package.json      — Add @tanstack/react-query dependency
frontend/src/main.tsx      — Add QueryClientProvider
```

### Files to Create

```
frontend/src/hooks/useWorks.ts
frontend/src/hooks/useAuthors.ts
frontend/src/hooks/useStreams.ts
frontend/src/hooks/useCollections.ts
frontend/src/hooks/useStats.ts
```

### Files NOT to Modify

```
frontend/src/services/api.ts        — DO NOT CHANGE.
frontend/src/pages/*.tsx             — DO NOT CHANGE. Task 4B rewrites pages.
frontend/src/components/*.tsx        — DO NOT CHANGE.
frontend/src/App.tsx                 — DO NOT CHANGE.
```

### Exact Changes

#### Install TanStack Query

```bash
cd frontend && npm install @tanstack/react-query
```

**Do not install `@tanstack/react-query-devtools`.** It's useful for development but adds bundle size. The user can install it later if wanted.

#### `main.tsx` — Add QueryClientProvider

Wrap the app in `QueryClientProvider`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,          // 30s — data is fresh for 30s before refetching
      retry: 1,                    // retry failed queries once
      refetchOnWindowFocus: false, // don't refetch when tab regains focus
    },
  },
});

// In the render:
<QueryClientProvider client={queryClient}>
  <BrowserRouter>
    <App />
  </BrowserRouter>
</QueryClientProvider>
```

**`staleTime: 30_000`** — 30 seconds. This is a personal single-user app. Data doesn't change unless the user changes it. 30 seconds prevents unnecessary refetches while still keeping data relatively fresh.

**`refetchOnWindowFocus: false`** — Disabled because this is a single-user app. The data doesn't change in the background (no other users are modifying it).

#### `hooks/useWorks.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getWorks,
  getWork,
  createWork,
  updateWork,
  type Work,
  type Status,
  type Density,
  type SourceType,
  type Significance,
} from "../services/api";

export function useWorks(params?: { status?: string; author?: string }) {
  return useQuery({
    queryKey: ["works", params],
    queryFn: () => getWorks(params),
  });
}

export function useWork(id: string) {
  return useQuery({
    queryKey: ["works", id],
    queryFn: () => getWork(id),
    enabled: !!id,
  });
}

export function useCreateWork() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createWork,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["works"] });
      queryClient.invalidateQueries({ queryKey: ["authors"] });
    },
  });
}

export function useUpdateWork(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Work>) => updateWork(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["works"] });
      queryClient.invalidateQueries({ queryKey: ["works", id] });
      queryClient.invalidateQueries({ queryKey: ["authors"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}
```

**Query key convention:** `["entity", ...params]` for lists, `["entity", id]` for details. This enables targeted invalidation — updating a work invalidates both the list and the detail.

#### `hooks/useAuthors.ts`

```typescript
import { useQuery } from "@tanstack/react-query";
import { getAuthors, getAuthor } from "../services/api";

export function useAuthors() {
  return useQuery({
    queryKey: ["authors"],
    queryFn: getAuthors,
  });
}

export function useAuthor(id: string) {
  return useQuery({
    queryKey: ["authors", id],
    queryFn: () => getAuthor(id),
    enabled: !!id,
  });
}
```

#### `hooks/useStreams.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getStreams,
  getStream,
  createStream,
  updateStream,
  deleteStream,
  addToStream,
  removeFromStream,
} from "../services/api";

export function useStreams() {
  return useQuery({
    queryKey: ["streams"],
    queryFn: getStreams,
  });
}

export function useStream(id: string) {
  return useQuery({
    queryKey: ["streams", id],
    queryFn: () => getStream(id),
    enabled: !!id,
  });
}

export function useCreateStream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createStream,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
    },
  });
}

export function useUpdateStream(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof updateStream>[1]) => updateStream(id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
      queryClient.invalidateQueries({ queryKey: ["streams", id] });
    },
  });
}

export function useDeleteStream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteStream,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
    },
  });
}

export function useAddToStream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workId, streamId, position }: { workId: string; streamId: string; position?: number }) =>
      addToStream(workId, streamId, position),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
      queryClient.invalidateQueries({ queryKey: ["works"] });
    },
  });
}

export function useRemoveFromStream() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workId, streamId }: { workId: string; streamId: string }) =>
      removeFromStream(workId, streamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["streams"] });
      queryClient.invalidateQueries({ queryKey: ["works"] });
    },
  });
}
```

#### `hooks/useCollections.ts`

Same pattern — wrap every collection API function. Include mutations for:
- `useCreateCollection`
- `useUpdateCollection`
- `useDeleteCollection`
- `useAddToCollection`
- `useRemoveFromCollection`
- `useAddCollectionToStream`
- `useRemoveCollectionFromStream`

Each mutation invalidates the relevant query keys.

#### `hooks/useStats.ts`

```typescript
import { useQuery } from "@tanstack/react-query";
import { getStats } from "../services/api";

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
  });
}
```

### Key Design Decisions (and why)

**1. One hook file per entity domain, not one file per hook.**
`useWorks.ts` contains `useWorks`, `useWork`, `useCreateWork`, `useUpdateWork`. This groups related queries and mutations. Task 4B will `import { useWorks, useCreateWork } from "../hooks/useWorks"` — clean and discoverable.

**2. `staleTime: 30_000` as a global default.**
For a single-user app, 30 seconds of staleness is fine. Individual hooks can override this if needed (e.g., stats might want longer staleness).

**3. Mutation `onSuccess` invalidates related queries.**
Creating a work invalidates both `["works"]` and `["authors"]` (because the author list shows work counts). This ensures the UI stays consistent without manual refetching.

**4. `enabled: !!id` on detail queries.**
Prevents the query from firing when `id` is undefined (e.g., during initial render before route params are available).

**5. No optimistic updates.**
For a single-user personal app, optimistic updates add complexity without meaningful UX benefit. The queries refetch after mutation success — the UI updates within 100ms.

### DO NOT

1. **Do not modify any page component.** Pages continue using `useEffect` + `useState`. Task 4B will rewrite them.

2. **Do not modify `api.ts`.** The hooks wrap the existing API functions without changing them.

3. **Do not add `@tanstack/react-query-devtools`.** Not needed for production. The user can add it later.

4. **Do not create hooks for API functions that don't exist.** Only wrap functions that are already in `api.ts`.

5. **Do not add loading/error UI components.** That's Task 4B's job.

6. **Do not use `suspense: true` or React Suspense.** The codebase doesn't use Suspense boundaries. Adding them would require restructuring pages.

7. **Do not create a barrel export (`hooks/index.ts`).** Named imports from specific files are clearer.

8. **Do not add retry logic beyond the global default.** One retry is sufficient for a local dev setup.

### Acceptance Criteria

- [ ] `@tanstack/react-query` is in `package.json` dependencies
- [ ] `main.tsx` has `QueryClientProvider` wrapping the app
- [ ] 5 hook files exist in `frontend/src/hooks/`
- [ ] Every API function in `api.ts` has a corresponding hook
- [ ] Every mutation hook invalidates relevant query keys on success
- [ ] `npm run build` succeeds with zero errors
- [ ] All pages still render and function identically (hooks exist but aren't used yet)
- [ ] No page files were modified

### Verification

```bash
cd frontend

# Build succeeds
npm run build

# Hooks are importable (check TypeScript compilation)
npx tsc --noEmit

# No page changes
git diff src/pages/
# Expected: no changes

# Hook files exist
ls src/hooks/
# Expected: useWorks.ts, useAuthors.ts, useStreams.ts, useCollections.ts, useStats.ts

# Dev server starts
npm run dev
# Open browser, verify all pages work identically to before
```

---

## Handoff

_Fill in after completing this task:_

### Decisions Made
<!-- E.g., "Set staleTime to 30s globally — can be overridden per hook" -->

### Harder Than Expected
<!-- E.g., "TypeScript inference on mutation parameters was tricky" -->

### Watch Out (for Task 4B)
<!-- E.g., "useWork returns { data, isLoading, error } — pages need to handle all three states" -->

### Deviations from Spec
<!-- Did you deviate? Why? -->
