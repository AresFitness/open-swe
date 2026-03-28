import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import {
  searchThreads,
  getThreadState,
  searchStoreItems,
  createRun,
  createThread,
  queueMessage,
  getThread,
} from "./client";
import type {
  Thread,
  ThreadState,
  StoreItem,
  DashboardMeta,
  Phase,
} from "./types";

// ── Threads (polls every 3s) ───────────────────────────────────────

export function useThreads() {
  return useQuery<Thread[]>({
    queryKey: ["threads"],
    queryFn: searchThreads,
    refetchInterval: 3000,
  });
}

// ── Single thread state (polls every 2s) ───────────────────────────

export function useThreadState(threadId: string | null) {
  return useQuery<ThreadState>({
    queryKey: ["threadState", threadId],
    queryFn: () => getThreadState(threadId!),
    enabled: !!threadId,
    refetchInterval: 2000,
  });
}

// ── Single thread metadata ─────────────────────────────────────────

export function useThread(threadId: string | null) {
  return useQuery<Thread>({
    queryKey: ["thread", threadId],
    queryFn: () => getThread(threadId!),
    enabled: !!threadId,
    refetchInterval: 3000,
  });
}

// ── Dashboard meta from store (polls every 3s) ────────────────────

export function useDashboardMeta() {
  return useQuery<StoreItem[]>({
    queryKey: ["dashboardMeta"],
    queryFn: searchStoreItems,
    refetchInterval: 3000,
  });
}

/**
 * Build a lookup map: threadId -> DashboardMeta
 */
export function useMetaMap(): Map<string, DashboardMeta> {
  const { data } = useDashboardMeta();
  const map = new Map<string, DashboardMeta>();
  if (data) {
    for (const item of data) {
      // namespace is ["dashboard", threadId]
      const threadId = item.namespace[1];
      if (threadId && item.key === "task") {
        map.set(threadId, item.value);
      }
    }
  }
  return map;
}

/**
 * Get a thread's phase from dashboard meta, defaulting to "research"
 */
export function getPhaseFromMeta(
  meta: DashboardMeta | null | undefined,
): Phase {
  return meta?.phase ?? "research";
}

// ── Send message (queue if busy, new run if idle) ──────────────────

export function useSendMessage(threadId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      message,
      config,
    }: {
      message: string;
      config?: Record<string, unknown>;
    }) => {
      if (!threadId) throw new Error("No thread selected");

      // Check thread status
      const thread = await getThread(threadId);

      if (thread.status === "busy") {
        // Queue the message for when the thread becomes idle
        await queueMessage(threadId, message);
        return { queued: true };
      }

      // Thread is idle — create a new run
      await createRun(threadId, message, config);
      return { queued: false };
    },
    onSuccess: () => {
      // Invalidate relevant queries so UI refreshes
      void queryClient.invalidateQueries({ queryKey: ["threads"] });
      void queryClient.invalidateQueries({
        queryKey: ["threadState", threadId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["thread", threadId],
      });
    },
  });
}

// ── Create new task (thread + run) ─────────────────────────────────

export function useCreateTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      message,
      config,
    }: {
      message: string;
      config?: Record<string, unknown>;
    }) => {
      const thread = await createThread();
      await createRun(thread.thread_id, message, config);
      return thread;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["threads"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboardMeta"] });
    },
  });
}
