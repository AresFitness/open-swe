import { useState, useCallback } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Header } from "./components/Layout/Header";
import { KanbanBoard } from "./components/Board/KanbanBoard";
import { TaskDetail } from "./components/Detail/TaskDetail";
import { NewTaskModal } from "./components/NewTask/NewTaskModal";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 1000,
      refetchOnWindowFocus: true,
    },
  },
});

function Dashboard() {
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(
    null,
  );
  const [showNewTask, setShowNewTask] = useState(false);

  const handleCloseDetail = useCallback(() => {
    setSelectedThreadId(null);
  }, []);

  const handleOpenNewTask = useCallback(() => {
    setShowNewTask(true);
  }, []);

  const handleCloseNewTask = useCallback(() => {
    setShowNewTask(false);
  }, []);

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 transition-colors">
      <Header
        onNewTask={handleOpenNewTask}
      />

      <div className="flex flex-1 overflow-hidden" style={{ height: "calc(100vh - 56px)" }}>
        {/* Main board area */}
        <div
          className={`flex-1 overflow-x-auto transition-all duration-300 ${
            selectedThreadId ? "w-1/2" : "w-full"
          }`}
        >
          <KanbanBoard
            selectedThreadId={selectedThreadId}
            onSelectThread={setSelectedThreadId}
          />
        </div>

        {/* Detail side panel */}
        {selectedThreadId && (
          <div className="w-1/2 border-l border-gray-200 dark:border-gray-800 overflow-hidden flex-shrink-0">
            <TaskDetail
              threadId={selectedThreadId}
              onClose={handleCloseDetail}
            />
          </div>
        )}
      </div>

      {/* New task modal */}
      {showNewTask && <NewTaskModal onClose={handleCloseNewTask} />}
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Dashboard />
    </QueryClientProvider>
  );
}
