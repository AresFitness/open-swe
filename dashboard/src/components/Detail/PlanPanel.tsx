import { useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { DashboardMeta, Phase, ThreadState } from "../../api/types";
import { useSendMessage } from "../../api/hooks";

interface PlanPanelProps {
  meta: DashboardMeta | null;
  threadId: string;
  threadState: ThreadState | null;
  phase: Phase;
}

export function PlanPanel({
  meta,
  threadId,
  threadState,
  phase,
}: PlanPanelProps) {
  const sendMessage = useSendMessage(threadId);
  const isPlanPhase = phase === "plan";

  const todos = threadState?.values?.todos ?? [];

  const handleApprove = useCallback(() => {
    sendMessage.mutate({
      message:
        "The plan looks good. Please proceed with the implementation.",
    });
  }, [sendMessage]);

  const handleRequestChanges = useCallback(() => {
    const feedback = window.prompt(
      "What changes would you like to the plan?",
    );
    if (feedback) {
      sendMessage.mutate({
        message: `Please revise the plan with the following feedback:\n\n${feedback}`,
      });
    }
  }, [sendMessage]);

  if (!meta?.plan && todos.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16 px-4">
        <svg
          className="w-10 h-10 text-gray-300 dark:text-gray-700 mb-3"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25Z"
          />
        </svg>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No plan available yet
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          The agent will create a plan after the research phase
        </p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Approval buttons (only in plan phase) */}
      {isPlanPhase && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
          <svg
            className="w-4 h-4 text-amber-500 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
            />
          </svg>
          <p className="text-xs text-amber-700 dark:text-amber-300 flex-1">
            The agent is waiting for plan approval before proceeding.
          </p>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <button
              onClick={handleRequestChanges}
              disabled={sendMessage.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded-md border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
            >
              Request Changes
            </button>
            <button
              onClick={handleApprove}
              disabled={sendMessage.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-green-600 dark:bg-green-500 text-white hover:bg-green-700 dark:hover:bg-green-600 transition-colors disabled:opacity-50"
            >
              {sendMessage.isPending ? "Sending..." : "Approve Plan"}
            </button>
          </div>
        </div>
      )}

      {/* Plan markdown */}
      {meta?.plan && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Implementation Plan
          </h3>
          <div className="prose text-sm text-gray-700 dark:text-gray-300 max-w-none rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {meta.plan}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* Todos */}
      {todos.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Tasks ({todos.filter((t) => t.status === "completed").length}/
            {todos.length} completed)
          </h3>
          <div className="space-y-1">
            {todos.map((todo) => (
              <div
                key={todo.id}
                className="flex items-start gap-2 px-3 py-2 rounded-md bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800"
              >
                <span className="mt-0.5 flex-shrink-0">
                  {todo.status === "completed" ? (
                    <svg
                      className="w-4 h-4 text-green-500"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2}
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
                      />
                    </svg>
                  ) : todo.status === "in_progress" ? (
                    <svg
                      className="w-4 h-4 text-blue-500 animate-spin"
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
                  ) : (
                    <svg
                      className="w-4 h-4 text-gray-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2}
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
                      />
                    </svg>
                  )}
                </span>
                <span
                  className={`text-sm leading-snug ${
                    todo.status === "completed"
                      ? "text-gray-400 dark:text-gray-500 line-through"
                      : "text-gray-700 dark:text-gray-300"
                  }`}
                >
                  {todo.task}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
