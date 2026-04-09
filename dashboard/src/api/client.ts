import type { Thread, ThreadState, StoreItem } from "./types";

// ── Helpers ────────────────────────────────────────────────────────

async function fetchJSON<T>(
  url: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Threads ────────────────────────────────────────────────────────

export async function searchThreads(): Promise<Thread[]> {
  return fetchJSON<Thread[]>("/threads/search", {
    method: "POST",
    body: JSON.stringify({ limit: 50 }),
  });
}

export async function getThread(threadId: string): Promise<Thread> {
  return fetchJSON<Thread>(`/threads/${threadId}`);
}

export async function getThreadState(
  threadId: string,
): Promise<ThreadState> {
  return fetchJSON<ThreadState>(`/threads/${threadId}/state`);
}

export async function createThread(): Promise<Thread> {
  return fetchJSON<Thread>("/threads", {
    method: "POST",
    body: JSON.stringify({ metadata: {} }),
  });
}

// ── Runs ───────────────────────────────────────────────────────────

export async function createRun(
  threadId: string,
  message: string,
  config?: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return fetchJSON<Record<string, unknown>>(
    `/threads/${threadId}/runs`,
    {
      method: "POST",
      body: JSON.stringify({
        assistant_id: "agent",
        input: {
          messages: [{ role: "user", content: message }],
        },
        config: config ?? {},
      }),
    },
  );
}

// ── Store ──────────────────────────────────────────────────────────

export async function searchStoreItems(): Promise<StoreItem[]> {
  const res = await fetchJSON<{ items: StoreItem[] }>("/store/items/search", {
    method: "POST",
    body: JSON.stringify({
      namespace_prefix: ["dashboard"],
      limit: 100,
    }),
  });
  return res.items ?? [];
}

export async function putStoreItem(
  namespace: string[],
  key: string,
  value: Record<string, unknown>,
): Promise<void> {
  await fetch("/store/items", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ namespace, key, value }),
  });
}

export async function deleteTask(threadId: string): Promise<void> {
  await fetchJSON<{ status: string; thread_id: string }>(
    `/tasks/${threadId}`,
    { method: "DELETE" },
  );
}

export async function queueMessage(
  threadId: string,
  message: string,
): Promise<void> {
  await putStoreItem(["queue", threadId], "pending_messages", {
    messages: [{ role: "user", content: message }],
    queued_at: new Date().toISOString(),
  });
}
