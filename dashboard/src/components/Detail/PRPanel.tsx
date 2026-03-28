import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { DashboardMeta } from "../../api/types";

interface PRPanelProps {
  meta: DashboardMeta | null;
}

export function PRPanel({ meta }: PRPanelProps) {
  const prUrls = meta?.pr_urls ?? [];
  const buildSummary = meta?.phase_summaries?.build;
  const prSummary = meta?.phase_summaries?.pr;
  const reviewSummary = meta?.phase_summaries?.review;

  const hasContent =
    prUrls.length > 0 || buildSummary || prSummary || reviewSummary;

  if (!hasContent) {
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
            d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5"
          />
        </svg>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No build or PR info yet
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Build progress and PRs will appear as the agent works
        </p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* PR Links */}
      {prUrls.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Pull Requests ({prUrls.length})
          </h3>
          <div className="space-y-1.5">
            {prUrls.map((url, i) => {
              // Extract repo and PR number from GitHub URL
              const match = url.match(
                /github\.com\/([^/]+\/[^/]+)\/pull\/(\d+)/,
              );
              const label = match
                ? `${match[1]}#${match[2]}`
                : url;

              return (
                <a
                  key={i}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors group"
                >
                  <svg
                    className="w-4 h-4 text-green-600 dark:text-green-400 flex-shrink-0"
                    viewBox="0 0 16 16"
                    fill="currentColor"
                  >
                    <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z" />
                  </svg>
                  <span className="text-sm text-blue-600 dark:text-blue-400 group-hover:underline font-mono truncate">
                    {label}
                  </span>
                  <svg
                    className="w-3 h-3 text-gray-400 dark:text-gray-500 flex-shrink-0 ml-auto"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
                    />
                  </svg>
                </a>
              );
            })}
          </div>
        </div>
      )}

      {/* Build summary */}
      {buildSummary && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Build Summary
          </h3>
          <div className="prose text-sm text-gray-700 dark:text-gray-300 max-w-none rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {buildSummary}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* PR summary */}
      {prSummary && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            PR Summary
          </h3>
          <div className="prose text-sm text-gray-700 dark:text-gray-300 max-w-none rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {prSummary}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* Review summary */}
      {reviewSummary && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Review Summary
          </h3>
          <div className="prose text-sm text-gray-700 dark:text-gray-300 max-w-none rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {reviewSummary}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
