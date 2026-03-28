import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { DashboardMeta } from "../../api/types";

interface ContextPanelProps {
  meta: DashboardMeta | null;
}

export function ContextPanel({ meta }: ContextPanelProps) {
  const researchSummary = meta?.phase_summaries?.research;
  const generalSummary = meta?.summary;

  if (!researchSummary && !generalSummary) {
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
            d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Zm3.75 11.625a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z"
          />
        </svg>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No research context yet
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Context will appear once the agent completes the research phase
        </p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* General summary */}
      {generalSummary && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Summary
          </h3>
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
            {generalSummary}
          </p>
        </div>
      )}

      {/* Research details */}
      {researchSummary && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Research Context
          </h3>
          <div className="prose text-sm text-gray-700 dark:text-gray-300 max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {researchSummary}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* Other phase summaries */}
      {meta?.phase_summaries &&
        Object.entries(meta.phase_summaries)
          .filter(([key]) => key !== "research")
          .map(([key, value]) => (
            <div key={key}>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
                {key} Summary
              </h3>
              <div className="prose text-sm text-gray-700 dark:text-gray-300 max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {value}
                </ReactMarkdown>
              </div>
            </div>
          ))}
    </div>
  );
}
