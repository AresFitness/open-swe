import { useState } from "react";
import type { DashboardMeta } from "../../api/types";

interface ScreenshotGalleryProps {
  meta: DashboardMeta | null;
}

export function ScreenshotGallery({ meta }: ScreenshotGalleryProps) {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  const screenshots = meta?.screenshots ?? [];

  if (screenshots.length === 0) {
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
            d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z"
          />
        </svg>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No screenshots yet
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Screenshots will appear when the agent captures them
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">
          Screenshots ({screenshots.length})
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {screenshots.map((path, i) => {
            const filename = path.split("/").pop() ?? path;
            return (
              <button
                key={i}
                onClick={() => setSelectedImage(path)}
                className="group relative rounded-lg overflow-hidden border border-gray-200 dark:border-gray-800 bg-gray-100 dark:bg-gray-900 hover:border-blue-400 dark:hover:border-blue-500 transition-colors aspect-video"
              >
                <img
                  src={`/files/${path}`}
                  alt={filename}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement;
                    target.style.display = "none";
                    const parent = target.parentElement;
                    if (parent && !parent.querySelector(".error-fallback")) {
                      const fallback = document.createElement("div");
                      fallback.className =
                        "error-fallback flex items-center justify-center h-full text-xs text-gray-400 dark:text-gray-500";
                      fallback.textContent = "Failed to load";
                      parent.appendChild(fallback);
                    }
                  }}
                />
                <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/60 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <p className="text-[10px] text-white truncate">
                    {filename}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Lightbox */}
      {selectedImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
          onClick={() => setSelectedImage(null)}
        >
          <div
            className="relative max-w-[90vw] max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setSelectedImage(null)}
              className="absolute -top-10 right-0 text-white/70 hover:text-white p-2"
            >
              <svg
                className="w-5 h-5"
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
            <img
              src={`/files/${selectedImage}`}
              alt="Screenshot"
              className="max-w-full max-h-[85vh] rounded-lg object-contain"
            />
            <p className="text-xs text-white/60 mt-2 text-center">
              {selectedImage.split("/").pop()}
            </p>
          </div>
        </div>
      )}
    </>
  );
}
