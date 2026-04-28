const BASE = "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ---- Types ----------------------------------------------------------------

export type Status = "unread" | "reading" | "read" | "abandoned" | "to_read";
export type Density = "light" | "moderate" | "dense" | "grueling";
export type SourceType = "primary" | "secondary" | "fiction";
export type Significance = "major" | "minor";
export type CollectionType = "major_works" | "minor_works" | "series" | "anthology";

export interface Author {
  id: string;
  name: string;
}

export interface CollectionSummary {
  id: string;
  name: string;
  type: CollectionType;
  order: number | null;
}

export interface Work {
  id: string;
  title: string;
  status: Status;
  language_read_in: string | null;
  date_read: string | null;
  density_rating: Density | null;
  source_type: SourceType;
  personal_note: string | null;
  edition_note: string | null;
  significance: Significance | null;
  authors: Author[];
  stream_ids: string[];
  collections: CollectionSummary[];
}

export interface Collection {
  id: string;
  name: string;
  description: string | null;
  type: CollectionType;
  author_id: string | null;
  work_count: number;
  read_count: number;
}

export interface CollectionDetail extends Collection {
  works: Work[];
}

export interface Stream {
  id: string;
  name: string;
  description: string | null;
  color: string | null;
  created_at: string;
  work_count: number;
  collection_count: number;
}

export interface StreamDetail extends Stream {
  collections: CollectionDetail[];
  works: Work[];  // direct-only works not covered by a collection
}

export interface AuthorSummary {
  id: string;
  name: string;
  birth_year: number | null;
  death_year: number | null;
  nationality: string | null;
  primary_language: string | null;
  total_works: number;
  read_works: number;
  completion_pct: number;
}

export interface AuthorDetail extends AuthorSummary {
  collections: CollectionDetail[];
  works: Work[];  // uncollected works
}

export interface Stats {
  total_works: number;
  total_authors: number;
  total_streams: number;
  by_status: Record<string, number>;
  by_year: Record<string, number>;
  by_language: Record<string, number>;
}

// ---- Works ----------------------------------------------------------------

export const getWorks = (params?: { status?: string; author?: string; limit?: number; offset?: number }) => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.author) qs.set("author", params.author);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  return req<Work[]>(`/works${qs.toString() ? "?" + qs : ""}`);
};

export const getWork = (id: string) => req<Work>(`/works/${id}`);

export const createWork = (body: {
  title: string;
  author: string;
  language_read_in?: string;
  status?: Status;
  date_read?: string;
  density_rating?: Density;
  source_type?: SourceType;
  personal_note?: string;
  significance?: Significance;
}) => req<Work>("/works", { method: "POST", body: JSON.stringify(body) });

export const updateWork = (id: string, body: Partial<Work>) =>
  req<Work>(`/works/${id}`, { method: "PATCH", body: JSON.stringify(body) });

// ---- Streams --------------------------------------------------------------

export const getStreams = () => req<Stream[]>("/streams");
export const getStream = (id: string) => req<StreamDetail>(`/streams/${id}`);

export const createStream = (body: { name: string; description?: string; color?: string }) =>
  req<Stream>("/streams", { method: "POST", body: JSON.stringify(body) });

export const updateStream = (id: string, body: Partial<Stream>) =>
  req<StreamDetail>(`/streams/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteStream = (id: string) =>
  req<void>(`/streams/${id}`, { method: "DELETE" });

/** PUT /works/{workId}/streams/{streamId} — idempotent add */
export const addToStream = (workId: string, streamId: string, position?: number) =>
  req<void>(`/works/${workId}/streams/${streamId}`, {
    method: "PUT",
    body: JSON.stringify({ position }),
  });

/** DELETE /works/{workId}/streams/{streamId} */
export const removeFromStream = (workId: string, streamId: string) =>
  req<void>(`/works/${workId}/streams/${streamId}`, { method: "DELETE" });

// ---- Collections ----------------------------------------------------------

export const getCollections = (params?: { author_id?: string; type?: CollectionType }) => {
  const qs = new URLSearchParams();
  if (params?.author_id) qs.set("author_id", params.author_id);
  if (params?.type) qs.set("type", params.type);
  return req<Collection[]>(`/collections${qs.toString() ? "?" + qs : ""}`);
};

export const getCollection = (id: string) => req<CollectionDetail>(`/collections/${id}`);

export const createCollection = (body: {
  name: string;
  description?: string;
  type?: CollectionType;
  author_id?: string;
}) => req<Collection>("/collections", { method: "POST", body: JSON.stringify(body) });

export const updateCollection = (id: string, body: { name?: string; description?: string; type?: CollectionType }) =>
  req<CollectionDetail>(`/collections/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteCollection = (id: string) =>
  req<void>(`/collections/${id}`, { method: "DELETE" });

/** PUT /works/{workId}/collections/{collectionId} — idempotent add */
export const addToCollection = (workId: string, collectionId: string, order?: number) =>
  req<void>(`/works/${workId}/collections/${collectionId}`, {
    method: "PUT",
    body: JSON.stringify({ order }),
  });

/** DELETE /works/{workId}/collections/{collectionId} */
export const removeFromCollection = (workId: string, collectionId: string) =>
  req<void>(`/works/${workId}/collections/${collectionId}`, { method: "DELETE" });

/** PUT /collections/{collectionId}/streams/{streamId} */
export const addCollectionToStream = (collectionId: string, streamId: string, order?: number) =>
  req<void>(`/collections/${collectionId}/streams/${streamId}`, {
    method: "PUT",
    body: JSON.stringify({ order }),
  });

/** DELETE /collections/{collectionId}/streams/{streamId} */
export const removeCollectionFromStream = (collectionId: string, streamId: string) =>
  req<void>(`/collections/${collectionId}/streams/${streamId}`, { method: "DELETE" });

// ---- Authors --------------------------------------------------------------

export const getAuthors = () => req<AuthorSummary[]>("/authors");
export const getAuthor = (id: string) => req<AuthorDetail>(`/authors/${id}`);

// ---- Stats ----------------------------------------------------------------

export const getStats = () => req<Stats>("/stats");
