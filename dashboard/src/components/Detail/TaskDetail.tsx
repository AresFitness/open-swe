import { useState, useMemo } from "react";
import { useThreadState, useThread, useMetaMap } from "../../api/hooks";
import type { DashboardMeta, Phase } from "../../api/types";
import { ContextPanel } from "./ContextPanel";
import { PlanPanel } from "./PlanPanel";
import { TestPanel } from "./TestPanel";
import { ScreenshotGallery } from "./ScreenshotGallery";
import { PRPanel } from "./PRPanel";
import { ChatPanel } from "../Chat/ChatPanel";

interface TaskDetailProps {
  threadId: string;
  onClose: () => void;
}

type Tab = "context" | "plan" | "build" | "tests" | "screenshots" | "chat";

const TAB_CONFIG: { id: Tab; label: string }[] = [
  { id: "context", label: "Context" },
  { id: "plan", label: "Plan" },
  { id: "build", label: "Build" },
  { id: "tests", label: "Tests" },
  { id: "screenshots", label: "Screenshots" },
  { id: "chat", label: "Chat" },
];

export function TaskDetail({ threadId, onClose }: TaskDetailProps) {
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const { data: threadState, isLoading: stateLoading } =
    useThreadState(threadId);
  const { data: thread } = useThread(threadId);
  const metaMap = useMetaMap();

  const meta: DashboardMeta | null = metaMap.get(threadId) ?? null;
  const phase: Phase = meta?.phase ?? "research";
  const isBusy = thread?.status === "busy";

  // Count screenshots for badge
  const screenshotCount = meta?.screenshots?.length ?? 0;
  const prCount = meta?.pr_urls?.length ?? 0;

  // Message count for chat badge
  const messageCount = useMemo(() => {
    if (!threadState?.values?.messages) return 0;
    return threadState.values.messages.filter(
      (m) => m.type === "human" || m.type === "ai",
    ).length;
  }, [threadState]);

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-950">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex-shrink-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
              {meta?.title || threadId.slice(0, 12) + "..."}
            </h2>
            {isBusy && (
              <span className="flex items-center gap-1 text-[10px] font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-1.5 py-0.5 rounded-full">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500" />
                </span>
                Running
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">
              Phase: {phase}
            </span>
            <span className="text-[10px] text-gray-300 dark:text-gray-700">
              |
            </span>
            <span className="text-[10px] font-mono text-gray-400 dark:text-gray-500">
              {threadId.slice(0, 8)}
            </span>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-md text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-0.5 px-4 border-b border-gray-200 dark:border-gray-800 flex-shrink-0 overflow-x-auto">
        {TAB_CONFIG.map((tab) => {
          const badge =
            tab.id === "screenshots"
              ? screenshotCount
              : tab.id === "chat"
                ? messageCount
                : tab.id === "build" && meta?.pr_urls?.length
                  ? prCount
                  : 0;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative px-3 py-2.5 text-xs font-medium transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "text-blue-600 dark:text-blue-400"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              <span className="flex items-center gap-1.5">
                {tab.label}
                {badge > 0 && (
                  <span className="text-[9px] px-1 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400">
                    {badge}
                  </span>
                )}
              </span>
              {activeTab === tab.id && (
                <span className="absolute bottom-0 left-3 right-3 h-0.5 bg-blue-600 dark:bg-blue-400 rounded-full" />
              )}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {stateLoading ? (
          <div className="flex items-center justify-center h-32">
            <svg
              className="w-5 h-5 animate-spin text-gray-400"
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
          </div>
        ) : (
          <>
            {activeTab === "context" && <ContextPanel meta={meta} />}
            {activeTab === "plan" && (
              <PlanPanel
                meta={meta}
                threadId={threadId}
                threadState={threadState ?? null}
                phase={phase}
              />
            )}
            {activeTab === "build" && <PRPanel meta={meta} />}
            {activeTab === "tests" && (
              <TestPanel meta={meta} threadState={threadState ?? null} />
            )}
            {activeTab === "screenshots" && (
              <ScreenshotGallery meta={meta} />
            )}
            {activeTab === "chat" && (
              <ChatPanel
                threadId={threadId}
                threadState={threadState ?? null}
                phase={phase}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
