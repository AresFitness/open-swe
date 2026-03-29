import { PHASE_LABELS, PHASE_DESCRIPTIONS } from "../../api/types";
import type { Phase } from "../../api/types";
import type { ThreadCardData } from "./KanbanBoard";
import { TaskCard } from "./TaskCard";

interface PhaseColumnProps {
  phase: Phase;
  cards: ThreadCardData[];
  selectedThreadId: string | null;
  onSelectThread: (threadId: string) => void;
}

const PHASE_COLORS: Record<Phase, string> = {
  research: "bg-purple-500",
  brainstorm: "bg-pink-500",
  plan: "bg-amber-500",
  build: "bg-blue-500",
  test: "bg-green-500",
  iterate: "bg-orange-500",
  pr: "bg-teal-500",
  review: "bg-indigo-500",
};

export function PhaseColumn({
  phase,
  cards,
  selectedThreadId,
  onSelectThread,
}: PhaseColumnProps) {
  const hasActiveTasks = cards.some((c) => c.thread.status === "busy");

  return (
    <div className="w-[220px] flex-shrink-0 flex flex-col h-full">
      {/* Column header */}
      <div
        className={`mb-3 px-2 ${
          hasActiveTasks
            ? "border-l-2 border-blue-500 dark:border-blue-400"
            : ""
        }`}
      >
        <div className="flex items-center gap-2 mb-0.5">
          <div className={`w-2 h-2 rounded-full ${PHASE_COLORS[phase]}`} />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-300">
            {PHASE_LABELS[phase]}
          </h2>
          {cards.length > 0 && (
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400">
              {cards.length}
            </span>
          )}
        </div>
        <p className="text-[10px] text-gray-400 dark:text-gray-500">
          {PHASE_DESCRIPTIONS[phase]}
        </p>
      </div>

      {/* Card list */}
      <div className="flex-1 overflow-y-auto space-y-2 min-h-0">
        {cards.map((card) => (
          <TaskCard
            key={card.thread.thread_id}
            data={card}
            isSelected={selectedThreadId === card.thread.thread_id}
            onClick={() => onSelectThread(card.thread.thread_id)}
          />
        ))}

        {cards.length === 0 && (
          <div className="px-2 py-8 text-center">
            <p className="text-[11px] text-gray-400 dark:text-gray-600">
              No tasks
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
