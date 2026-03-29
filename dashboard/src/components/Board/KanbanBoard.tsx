import { useMemo } from "react";
import { useThreads, useMetaMap, getPhaseFromMeta } from "../../api/hooks";
import { PHASES } from "../../api/types";
import type { Phase, Thread, DashboardMeta } from "../../api/types";
import { PhaseColumn } from "./PhaseColumn";

interface KanbanBoardProps {
  selectedThreadId: string | null;
  onSelectThread: (threadId: string) => void;
}

export interface ThreadCardData {
  thread: Thread;
  meta: DashboardMeta | null;
}

export function KanbanBoard({
  selectedThreadId,
  onSelectThread,
}: KanbanBoardProps) {
  const { data: threads, isLoading, error } = useThreads();
  const metaMap = useMetaMap();

  // Group threads by phase
  const columnData = useMemo(() => {
    const columns: Record<Phase, ThreadCardData[]> = {
      research: [],
      brainstorm: [],
      plan: [],
      build: [],
      test: [],
      iterate: [],
      pr: [],
      review: [],
    };

    if (!threads) return columns;

    for (const thread of threads) {
      const meta = metaMap.get(thread.thread_id) ?? null;
      const phase = getPhaseFromMeta(meta);
      columns[phase].push({ thread, meta });
    }

    // Sort each column: busy threads first, then by updated_at desc
    for (const phase of PHASES) {
      columns[phase].sort((a, b) => {
        if (a.thread.status === "busy" && b.thread.status !== "busy")
          return -1;
        if (a.thread.status !== "busy" && b.thread.status === "busy")
          return 1;
        return (
          new Date(b.thread.updated_at).getTime() -
          new Date(a.thread.updated_at).getTime()
        );
      });
    }

    return columns;
  }, [threads, metaMap]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-3 text-gray-500 dark:text-gray-400">
          <svg
            className="w-5 h-5 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <span className="text-sm">Loading threads...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center px-4">
          <p className="text-sm text-red-500 dark:text-red-400 mb-1">
            Failed to load threads
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 p-4 h-full min-w-max">
      {PHASES.map((phase) => (
        <PhaseColumn
          key={phase}
          phase={phase}
          cards={columnData[phase]}
          selectedThreadId={selectedThreadId}
          onSelectThread={onSelectThread}
        />
      ))}
    </div>
  );
}
