import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { DashboardMeta, ThreadState, Message } from "../../api/types";

interface TestPanelProps {
  meta: DashboardMeta | null;
  threadState: ThreadState | null;
}

/**
 * Extract text content from a message's content field
 */
function getTextContent(msg: Message): string {
  if (typeof msg.content === "string") return msg.content;
  return msg.content
    .filter((b) => b.type === "text")
    .map((b) => {
      if (b.type === "text") return b.text;
      return "";
    })
    .join("\n");
}

/**
 * Check if a tool message is test-related based on name or content
 */
function isTestRelated(msg: Message): boolean {
  const name = msg.name?.toLowerCase() ?? "";
  const content = getTextContent(msg).toLowerCase();
  return (
    name.includes("test") ||
    name.includes("typecheck") ||
    name.includes("lint") ||
    name.includes("build") ||
    content.includes("test") ||
    content.includes("jest") ||
    content.includes("vitest") ||
    content.includes("tsc") ||
    content.includes("eslint") ||
    content.includes("PASS") ||
    content.includes("FAIL")
  );
}

export function TestPanel({ meta, threadState }: TestPanelProps) {
  // Collect test-related tool messages
  const testMessages = useMemo(() => {
    if (!threadState?.values?.messages) return [];
    return threadState.values.messages
      .filter((msg) => msg.type === "tool" && isTestRelated(msg))
      .map((msg) => ({
        name: msg.name ?? "Unknown",
        content: getTextContent(msg),
      }));
  }, [threadState]);

  const hasTestResults = !!meta?.test_results;
  const hasTestMessages = testMessages.length > 0;

  if (!hasTestResults && !hasTestMessages) {
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
            d="M11.42 15.17l-5.21-3.012a.563.563 0 0 1 0-.974l5.21-3.012a.563.563 0 0 1 .563 0l5.21 3.012a.563.563 0 0 1 0 .974l-5.21 3.012a.563.563 0 0 1-.563 0Z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3.75 4.875c0-.621.504-1.125 1.125-1.125h14.25c.621 0 1.125.504 1.125 1.125v14.25c0 .621-.504 1.125-1.125 1.125H4.875a1.125 1.125 0 0 1-1.125-1.125V4.875Z"
          />
        </svg>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No test results yet
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Test results will appear when the agent runs tests
        </p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Dashboard meta test results */}
      {hasTestResults && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Test Results
          </h3>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-4">
            <div className="prose text-sm text-gray-700 dark:text-gray-300 max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {meta!.test_results}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      )}

      {/* Tool messages */}
      {hasTestMessages && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Test Tool Output ({testMessages.length})
          </h3>
          <div className="space-y-2">
            {testMessages.map((msg, i) => {
              // Detect pass/fail
              const content = msg.content.toLowerCase();
              const isPassing =
                content.includes("passed") ||
                content.includes("pass") ||
                (content.includes("0 failed") &&
                  !content.includes("error"));
              const isFailing =
                content.includes("failed") ||
                content.includes("fail") ||
                content.includes("error");

              return (
                <div
                  key={i}
                  className={`rounded-lg border p-3 ${
                    isPassing
                      ? "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20"
                      : isFailing
                        ? "border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20"
                        : "border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    {isPassing && (
                      <svg
                        className="w-3.5 h-3.5 text-green-500"
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
                    )}
                    {isFailing && (
                      <svg
                        className="w-3.5 h-3.5 text-red-500"
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
                    )}
                    <span className="text-[11px] font-mono font-medium text-gray-600 dark:text-gray-400">
                      {msg.name}
                    </span>
                  </div>
                  <pre className="text-xs text-gray-700 dark:text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto max-h-60 overflow-y-auto">
                    {msg.content}
                  </pre>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
