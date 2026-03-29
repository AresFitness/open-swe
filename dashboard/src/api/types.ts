// ── Phase definitions ──────────────────────────────────────────────
export const PHASES = [
  "research",
  "brainstorm",
  "plan",
  "build",
  "test",
  "iterate",
  "pr",
  "review",
] as const;

export type Phase = (typeof PHASES)[number];

export const PHASE_LABELS: Record<Phase, string> = {
  research: "Research",
  brainstorm: "Brainstorm",
  plan: "Plan",
  build: "Build",
  test: "Test",
  iterate: "Iterate",
  pr: "PR",
  review: "Review",
};

export const PHASE_DESCRIPTIONS: Record<Phase, string> = {
  research: "Context gathering",
  brainstorm: "Design exploration",
  plan: "Implementation plan",
  build: "Code implementation",
  test: "Tests, typecheck, builds",
  iterate: "Fix failures",
  pr: "Create pull requests",
  review: "Address PR comments",
};

// ── Dashboard metadata (stored in LangGraph Store) ─────────────────
export interface DashboardMeta {
  phase: Phase;
  title: string;
  summary: string;
  plan: string;
  test_results: string;
  screenshots: string[];
  pr_urls: string[];
  phase_summaries: Record<string, string>;
  iteration_count: number;
}

// ── Store item shape returned by LangGraph Store API ───────────────
export interface StoreItem {
  namespace: string[];
  key: string;
  value: DashboardMeta;
  created_at: string;
  updated_at: string;
}

// ── Thread from LangGraph ──────────────────────────────────────────
export interface Thread {
  thread_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  status: "idle" | "busy" | "interrupted" | "error";
  values: Record<string, unknown>;
}

// ── Messages (LangChain format) ────────────────────────────────────
export interface ContentBlockText {
  type: "text";
  text: string;
}

export interface ContentBlockToolUse {
  type: "tool_use";
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export type ContentBlock = ContentBlockText | ContentBlockToolUse;

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface Message {
  id?: string;
  type: "human" | "ai" | "tool";
  content: string | ContentBlock[];
  tool_calls?: ToolCall[];
  name?: string;
  tool_call_id?: string;
}

// ── Todos from thread state ────────────────────────────────────────
export interface Todo {
  id: string;
  task: string;
  status: "pending" | "in_progress" | "completed";
}

// ── Thread state (full) ────────────────────────────────────────────
export interface ThreadState {
  values: {
    messages: Message[];
    todos?: Todo[];
    [key: string]: unknown;
  };
  next: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  tasks: Record<string, unknown>;
}

// ── Combined thread + meta for board display ───────────────────────
export interface ThreadWithMeta {
  thread: Thread;
  meta: DashboardMeta | null;
}
