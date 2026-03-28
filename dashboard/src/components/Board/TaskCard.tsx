import { useMemo } from "react";
import type { ThreadCardData } from "./KanbanBoard";

interface TaskCardProps {
  data: ThreadCardData;
  isSelected: boolean;
  onClick: () => void;
}

function formatElapsed(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;

  if (diffMs < 0) return "just now";

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;

  const days = Math.floor(hours / 24);
  return `${days}d`;
}

function getSourceIcon(
  metadata: Record<string, unknown>,
): { label: string; icon: React.ReactNode } | null {
  const source = metadata?.source as string | undefined;
  if (!source) return null;

  switch (source) {
    case "slack":
      return {
        label: "Slack",
        icon: (
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
            <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zm10.122 2.521a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.268 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zm-2.523 10.122a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.268a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
          </svg>
        ),
      };
    case "linear":
      return {
        label: "Linear",
        icon: (
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2.513 12.833l8.654 8.654a9.953 9.953 0 0 1-3.37-1.236l-6.52-6.52a10.03 10.03 0 0 1 1.236-3.37v2.472zm-.96 2.03A10.106 10.106 0 0 1 1.5 12c0-5.523 4.477-10 10-10 .96 0 1.893.135 2.773.389L2.523 14.14c-.347.347-.686.486-.97.724zM4.37 19.63l-.262-.262L19.368 4.108A9.953 9.953 0 0 1 22.5 12c0 5.523-4.477 10-10 10a9.953 9.953 0 0 1-8.13-2.37z" />
          </svg>
        ),
      };
    case "github":
      return {
        label: "GitHub",
        icon: (
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
          </svg>
        ),
      };
    default:
      return null;
  }
}

export function TaskCard({ data, isSelected, onClick }: TaskCardProps) {
  const { thread, meta } = data;
  const isBusy = thread.status === "busy";

  const title = meta?.title || thread.thread_id.slice(0, 8) + "...";
  const summary = meta?.summary || "";
  const elapsed = useMemo(
    () => formatElapsed(thread.updated_at),
    [thread.updated_at],
  );
  const sourceInfo = useMemo(
    () => getSourceIcon(thread.metadata),
    [thread.metadata],
  );
  const iterationCount = meta?.iteration_count ?? 0;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-lg border p-3 transition-all duration-150 cursor-pointer group
        ${
          isSelected
            ? "border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-blue-950/30 ring-1 ring-blue-500/20"
            : "border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 hover:border-gray-300 dark:hover:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800/70"
        }
        ${isBusy ? "animate-pulse-subtle" : ""}
      `}
    >
      {/* Title row */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 leading-snug line-clamp-2">
          {title}
        </h3>
        {isBusy && (
          <span className="flex-shrink-0 mt-0.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
            </span>
          </span>
        )}
      </div>

      {/* Summary */}
      {summary && (
        <p className="text-[11px] text-gray-500 dark:text-gray-400 leading-relaxed line-clamp-2 mb-2">
          {summary}
        </p>
      )}

      {/* Footer: source + elapsed */}
      <div className="flex items-center justify-between text-[10px] text-gray-400 dark:text-gray-500">
        <div className="flex items-center gap-1.5">
          {sourceInfo && (
            <span
              className="flex items-center gap-1"
              title={sourceInfo.label}
            >
              {sourceInfo.icon}
            </span>
          )}
          {iterationCount > 0 && (
            <span className="px-1 py-0.5 rounded bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 font-medium">
              iter {iterationCount}
            </span>
          )}
        </div>
        <span>{elapsed}</span>
      </div>
    </button>
  );
}
