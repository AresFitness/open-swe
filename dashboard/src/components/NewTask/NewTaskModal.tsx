import { useState, useCallback, useRef, useEffect } from "react";
import { useCreateTask } from "../../api/hooks";

interface NewTaskModalProps {
  onClose: () => void;
}

type Repo = "RedefinedFitness" | "amp-ios" | "both";

const REPO_OPTIONS: { value: Repo; label: string; description: string }[] = [
  {
    value: "RedefinedFitness",
    label: "RedefinedFitness",
    description: "Backend (TypeScript/Node.js)",
  },
  {
    value: "amp-ios",
    label: "amp-ios",
    description: "iOS app (Swift)",
  },
  {
    value: "both",
    label: "Both repos",
    description: "Cross-repo task",
  },
];

export function NewTaskModal({ onClose }: NewTaskModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [repo, setRepo] = useState<Repo>("RedefinedFitness");
  const [useSuperpowers, setUseSuperpowers] = useState(false);
  const createTask = useCreateTask();
  const titleRef = useRef<HTMLInputElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);

  // Focus title on mount
  useEffect(() => {
    titleRef.current?.focus();
  }, []);

  // Close on Escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!title.trim()) return;

      const prompt = description.trim()
        ? `${title.trim()}\n\n${description.trim()}`
        : title.trim();

      const configurable: Record<string, unknown> = {
        repo: {
          owner: "AresFitness",
          name: repo === "both" ? "RedefinedFitness" : repo,
        },
        source: "dashboard",
        superpowers: useSuperpowers,
      };
      if (repo === "both") {
        configurable.additional_repos = [
          { owner: "AresFitness", name: "amp-ios" },
        ];
      }
      const repoConfig = { configurable };

      await createTask.mutateAsync({
        message: prompt,
        config: repoConfig,
      });

      onClose();
    },
    [title, description, repo, createTask, onClose],
  );

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === backdropRef.current) onClose();
    },
    [onClose],
  );

  return (
    <div
      ref={backdropRef}
      onClick={handleBackdropClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/70"
    >
      <div className="w-full max-w-lg mx-4 rounded-xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-800">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
            New Task
          </h2>
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

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Title */}
          <div>
            <label
              htmlFor="task-title"
              className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5"
            >
              Title
            </label>
            <input
              ref={titleRef}
              id="task-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Add user profile endpoint"
              className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:focus:border-blue-400 transition-colors"
              required
            />
          </div>

          {/* Description */}
          <div>
            <label
              htmlFor="task-description"
              className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5"
            >
              Description
            </label>
            <textarea
              id="task-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the task in detail. Include any relevant context, requirements, or constraints..."
              rows={5}
              className="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:focus:border-blue-400 transition-colors resize-none"
            />
          </div>

          {/* Repo selector */}
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">
              Repository
            </label>
            <div className="grid grid-cols-3 gap-2">
              {REPO_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setRepo(option.value)}
                  className={`p-2.5 rounded-lg border text-left transition-all ${
                    repo === option.value
                      ? "border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/20 ring-1 ring-blue-500/20"
                      : "border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600"
                  }`}
                >
                  <p
                    className={`text-xs font-medium ${
                      repo === option.value
                        ? "text-blue-700 dark:text-blue-300"
                        : "text-gray-700 dark:text-gray-300"
                    }`}
                  >
                    {option.label}
                  </p>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                    {option.description}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Superpowers toggle */}
          <div className="flex items-center justify-between p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
            <div className="flex-1 mr-3">
              <p className="text-xs font-medium text-gray-700 dark:text-gray-300">
                Use Superpowers
              </p>
              <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                Interactive brainstorming &amp; structured planning before building
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={useSuperpowers}
              onClick={() => setUseSuperpowers((v) => !v)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 ${
                useSuperpowers
                  ? "bg-blue-600 dark:bg-blue-500"
                  : "bg-gray-300 dark:bg-gray-600"
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transform transition-transform ${
                  useSuperpowers ? "translate-x-4.5" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>

          {/* Error */}
          {createTask.isError && (
            <p className="text-xs text-red-500 dark:text-red-400">
              Failed to create task:{" "}
              {createTask.error?.message ?? "Unknown error"}
            </p>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!title.trim() || createTask.isPending}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 dark:bg-blue-500 text-white hover:bg-blue-700 dark:hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {createTask.isPending && (
                <svg
                  className="w-3.5 h-3.5 animate-spin"
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
              )}
              Create Task
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
