import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import { supabase } from "./lib/supabase";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  Check,
  Copy,
  ExternalLink,
  Loader2,
  MessageCircle,
  Plus,
  Search,
  Send,
  Sparkles,
  Square,
  XCircle,
  Brain,
  Calculator,
  FileSearch,
  PenLine,
} from "lucide-react";

import {
  streamChat,
  type ChatMessage,
  type AgentStep,
} from "./api";

// ============================================================
// TYPES
// ============================================================

type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
};

// ============================================================
// STORAGE
// ============================================================

const STORAGE_KEY = "orbit-conversations";
const ACTIVE_CHAT_KEY = "orbit-active-chat";

// ============================================================
// CREATE CONVERSATION
// ============================================================

function createConversation(): Conversation {
  return {
    id: crypto.randomUUID(),
    title: "New chat",
    messages: [],
    updatedAt: Date.now(),
  };
}

// ============================================================
// AGENT ICON
// ============================================================

function getAgentIcon(step: string) {
  switch (step) {
    case "request_received":
      return <MessageCircle size={15} />;

    case "planning":
      return <Brain size={15} />;

    case "web_search":
      return <Search size={15} />;

    case "analysis":
      return <FileSearch size={15} />;

    case "calculator":
      return <Calculator size={15} />;

    case "writing":
    case "answer":
      return <PenLine size={15} />;

    case "completed":
      return <Check size={15} />;

    case "stopped":
      return <Square size={13} />;

    default:
      return <Sparkles size={15} />;
  }
}

// ============================================================
// AGENT TIMELINE
// ============================================================

function AgentTimeline({
  steps,
  active,
}: {
  steps: AgentStep[];
  active: boolean;
}) {
  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="mb-5 rounded-2xl border border-[#293136] bg-[#111518]/80 p-4">

      {/* HEADER */}

      <div className="mb-4 flex items-center gap-2">

        <div className="grid size-7 place-items-center rounded-lg bg-[#c6f36b] text-[#111610]">
          <Sparkles size={14} />
        </div>

        <div>
          <p className="text-sm font-semibold text-[#dce3e6]">
            Orbit Agent
          </p>

          <p className="text-[11px] text-[#667177]">
            Autonomous task execution
          </p>
        </div>

        {active && (
          <Loader2
            size={14}
            className="ml-auto animate-spin text-[#c6f36b]"
          />
        )}
      </div>

      {/* STEPS */}

      <div className="ml-1">

        {steps.map((item, index) => {

          const isLast =
            index === steps.length - 1;

          const isStarted =
            item.status === "started";

          const isCompleted =
            item.status === "completed";

          const isFailed =
            item.status === "failed";

          const isStopped =
            item.status === "stopped";

          return (
            <div
              key={`${item.step}-${index}`}
              className="relative flex gap-3"
            >

              {/* CONNECTING LINE */}

              {!isLast && (
                <div className="absolute left-[11px] top-6 h-[calc(100%-2px)] w-px bg-[#30383d]" />
              )}

              {/* ICON */}

              <div
                className={`
                  relative z-10 grid size-6 shrink-0
                  place-items-center rounded-full border

                  ${
                    isCompleted
                      ? "border-[#53683d] bg-[#1c291b] text-[#c6f36b]"
                      : isFailed
                        ? "border-[#713e3e] bg-[#29191a] text-[#ff8f86]"
                        : isStopped
                          ? "border-[#555d61] bg-[#202528] text-[#9ba5a9]"
                          : isStarted
                            ? "border-[#53683d] bg-[#1c291b] text-[#c6f36b]"
                            : "border-[#30383d] bg-[#171b1e] text-[#748087]"
                  }
                `}
              >

                {isFailed ? (

                  <XCircle size={14} />

                ) : isStopped ? (

                  <Square
                    size={11}
                    fill="currentColor"
                  />

                ) : isStarted ? (

                  <Loader2
                    size={13}
                    className="animate-spin"
                  />

                ) : (

                  getAgentIcon(item.step)

                )}

              </div>

              {/* CONTENT */}

              <div className="min-w-0 flex-1 pb-4">

                <div className="flex items-center gap-2">

                  <p
                    className={`
                      text-sm

                      ${
                        isStarted
                          ? "font-medium text-[#c6f36b]"
                          : isFailed
                            ? "text-[#ff9b93]"
                            : isStopped
                              ? "font-medium text-[#9ba5a9]"
                              : "text-[#b9c3c7]"
                      }
                    `}
                  >
                    {item.label}
                  </p>

                  {isStarted && (
                    <span className="text-[10px] uppercase tracking-wider text-[#748087]">
                      running
                    </span>
                  )}

                  {isCompleted && (
                    <span className="text-[10px] uppercase tracking-wider text-[#667177]">
                      completed
                    </span>
                  )}

                  {isStopped && (
                    <span className="text-[10px] uppercase tracking-wider text-[#9ba5a9]">
                      stopped
                    </span>
                  )}

                  {isFailed && (
                    <span className="text-[10px] uppercase tracking-wider text-[#ff9b93]">
                      failed
                    </span>
                  )}

                </div>

                {item.reason && (
                  <p className="mt-1 text-xs leading-5 text-[#667177]">
                    {item.reason}
                  </p>
                )}

                {item.action && (
                  <p className="mt-1 text-[11px] text-[#59646a]">
                    Decision: {item.action}
                  </p>
                )}

                {typeof item.count === "number" && (
                  <p className="mt-1 text-[11px] text-[#59646a]">
                    {item.count} source
                    {item.count === 1 ? "" : "s"} found
                  </p>
                )}

              </div>

            </div>
          );
        })}

      </div>
    </div>
  );
}

// ============================================================
// APP
// ============================================================

export default function App() {

  const [
    conversations,
    setConversations,
  ] = useState<Conversation[]>([]);

  const [
    session,
    setSession,
  ] = useState<any>(null);

  const [
    authLoading,
    setAuthLoading,
  ] = useState(true);

  const [
    activeId,
    setActiveId,
  ] = useState("");

  const [
    draft,
    setDraft,
  ] = useState("");

  const [
    status,
    setStatus,
  ] = useState<string | null>(null);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const [
    isStreaming,
    setIsStreaming,
  ] = useState(false);

  const abortRef =
    useRef<AbortController | null>(null);

  // ==========================================================
  // ACTIVE CONVERSATION
  // ==========================================================

  const active =
    conversations.find(
      (conversation) =>
        conversation.id === activeId,
    );

  // ==========================================================
  // AUTH
  // ==========================================================

  useEffect(() => {

    let mounted = true;

    supabase.auth
      .getSession()
      .then(({ data }) => {

        if (!mounted) {
          return;
        }

        setSession(data.session);
        setAuthLoading(false);
      });

    const {
      data: {
        subscription,
      },
    } =
      supabase.auth.onAuthStateChange(
        (_event, nextSession) => {

          if (!mounted) {
            return;
          }

          setSession(nextSession);
          setAuthLoading(false);
        },
      );

    return () => {

      mounted = false;

      subscription.unsubscribe();
    };

  }, []);

  // ==========================================================
  // GOOGLE LOGIN
  // ==========================================================

  async function signInWithGoogle() {

    const {
      error: loginError,
    } =
      await supabase.auth.signInWithOAuth({
        provider: "google",

        options: {
          redirectTo:
            window.location.origin,

          queryParams: {
            prompt: "select_account",
          },
        },
      });

    if (loginError) {

      console.error(
        "Google login error:",
        loginError,
      );

      alert(
        loginError.message,
      );
    }
  }

  // ==========================================================
  // LOGOUT
  // ==========================================================

  async function signOut() {

    abortRef.current?.abort();

    setIsStreaming(false);
    setStatus(null);
    setError(null);

    await supabase.auth.signOut();
  }

  // ==========================================================
  // LOAD CHATS
  // ==========================================================

  useEffect(() => {

    if (
      authLoading ||
      !session?.user?.id
    ) {
      return;
    }

    const userStorageKey =
      `${STORAGE_KEY}-${session.user.id}`;

    const userActiveChatKey =
      `${ACTIVE_CHAT_KEY}-${session.user.id}`;

    try {

      const saved =
        localStorage.getItem(
          userStorageKey,
        );

      const savedActiveId =
        localStorage.getItem(
          userActiveChatKey,
        );

      if (saved) {

        const parsed =
          JSON.parse(
            saved,
          ) as Conversation[];

        if (
          Array.isArray(parsed) &&
          parsed.length > 0
        ) {

          setConversations(parsed);

          const activeExists =
            parsed.some(
              (conversation) =>
                conversation.id ===
                savedActiveId,
            );

          setActiveId(
            activeExists &&
            savedActiveId
              ? savedActiveId
              : parsed[0].id,
          );

          return;
        }
      }

    } catch (loadError) {

      console.error(
        "Could not restore Orbit chats:",
        loadError,
      );
    }

    const conversation =
      createConversation();

    setConversations([
      conversation,
    ]);

    setActiveId(
      conversation.id,
    );

  }, [
    authLoading,
    session?.user?.id,
  ]);

  // ==========================================================
  // SAVE CHATS
  // ==========================================================

  useEffect(() => {

    if (
      authLoading ||
      !session?.user?.id ||
      conversations.length === 0
    ) {
      return;
    }

    const userStorageKey =
      `${STORAGE_KEY}-${session.user.id}`;

    try {

      localStorage.setItem(
        userStorageKey,
        JSON.stringify(
          conversations,
        ),
      );

    } catch (saveError) {

      console.error(
        "Could not save Orbit chats:",
        saveError,
      );
    }

  }, [
    conversations,
    authLoading,
    session?.user?.id,
  ]);

  // ==========================================================
  // SAVE ACTIVE CHAT
  // ==========================================================

  useEffect(() => {

    if (
      authLoading ||
      !session?.user?.id ||
      !activeId
    ) {
      return;
    }

    const userActiveChatKey =
      `${ACTIVE_CHAT_KEY}-${session.user.id}`;

    localStorage.setItem(
      userActiveChatKey,
      activeId,
    );

  }, [
    activeId,
    authLoading,
    session?.user?.id,
  ]);

  // ==========================================================
  // NEW CHAT
  // ==========================================================

  function startNewChat() {

    abortRef.current?.abort();

    setIsStreaming(false);
    setStatus(null);
    setError(null);

    const conversation =
      createConversation();

    setConversations(
      (current) => [
        ...current,
        conversation,
      ],
    );

    setActiveId(
      conversation.id,
    );

    setDraft("");
  }

  // ==========================================================
  // MARK CURRENT AGENT STOPPED
  // ==========================================================

  function markCurrentAgentStopped() {

    setConversations(
      (current) =>
        current.map(
          (conversation) => {

            if (
              conversation.id !==
              activeId
            ) {
              return conversation;
            }

            const messages =
              [...conversation.messages];

            const index =
              messages.length - 1;

            const last =
              messages[index];

            if (
              !last ||
              last.role !==
                "assistant"
            ) {
              return conversation;
            }

            const steps =
              [
                ...(last.agentSteps ?? []),
              ];

            if (steps.length === 0) {
              return conversation;
            }

            const runningIndex =
              steps.findIndex(
                (step) =>
                  step.status ===
                  "started",
              );

            const targetIndex =
              runningIndex >= 0
                ? runningIndex
                : steps.length - 1;

            const target =
              steps[targetIndex];

            steps[targetIndex] = {
              ...target,
              status: "stopped",
              reason:
                target.reason ??
                "Task stopped by user.",
            };

            messages[index] = {
              ...last,
              agentSteps: steps,
            };

            return {
              ...conversation,
              messages,
              updatedAt:
                Date.now(),
            };
          },
        ),
    );

    setStatus(
      "Task stopped.",
    );
  }

  // ==========================================================
  // UPDATE CURRENT ASSISTANT MESSAGE
  // ==========================================================

  function updateAssistantMessage(
    updater: (
      message: ChatMessage,
    ) => ChatMessage,
  ) {

    setConversations(
      (current) =>
        current.map(
          (conversation) => {

            if (
              conversation.id !==
              activeId
            ) {
              return conversation;
            }

            const messages =
              [...conversation.messages];

            const index =
              messages.length - 1;

            const last =
              messages[index];

            if (
              !last ||
              last.role !==
                "assistant"
            ) {
              return conversation;
            }

            messages[index] =
              updater(last);

            return {
              ...conversation,
              messages,
              updatedAt:
                Date.now(),
            };
          },
        ),
    );
  }

  // ==========================================================
  // SEND MESSAGE
  // ==========================================================

  async function sendMessage(
    event?: FormEvent,
  ) {

    event?.preventDefault();

    const message =
      draft.trim();

    if (
      !message ||
      isStreaming ||
      !active
    ) {
      return;
    }

    const history =
      active.messages;

    const title =
      active.title === "New chat"
        ? makeTitle(message)
        : active.title;

    const nextMessages:
      ChatMessage[] = [
        ...history,

        {
          role: "user",
          content: message,
        },

        {
          role: "assistant",
          content: "",
          sources: [],
          agentSteps: [],
        },
      ];

    setConversations(
      (current) =>
        current.map(
          (conversation) =>
            conversation.id ===
            active.id
              ? {
                  ...conversation,
                  title,
                  messages:
                    nextMessages,
                  updatedAt:
                    Date.now(),
                }
              : conversation,
        ),
    );

    setDraft("");
    setStatus(null);
    setError(null);

    const controller =
      new AbortController();

    abortRef.current =
      controller;

    setIsStreaming(true);

    try {

     await streamChat(
  session.user.id,
  active.id,
  message,
  history,
        {

          // ==================================================
          // TOKEN
          // ==================================================

          onToken: (
            token,
          ) => {

            updateAssistantMessage(
              (assistant) => ({
                ...assistant,
                content:
                  assistant.content +
                  token,
              }),
            );
          },

          // ==================================================
          // AGENT STEP
          // ==================================================

          onAgent: (
            step,
          ) => {

            updateAssistantMessage(
              (assistant) => {

                const steps =
                  [
                    ...(assistant.agentSteps ??
                      []),
                  ];

                const existingIndex =
                  steps.findIndex(
                    (item) =>
                      item.step ===
                      step.step,
                  );

                if (
                  existingIndex >= 0
                ) {

                  steps[
                    existingIndex
                  ] = step;

                } else {

                  steps.push(step);
                }

                return {
                  ...assistant,
                  agentSteps:
                    steps,
                };
              },
            );
          },

          // ==================================================
          // STATUS
          // ==================================================

          onStatus:
            setStatus,

          // ==================================================
          // SOURCE
          // ==================================================

          onSource: (
            source,
          ) => {

            updateAssistantMessage(
              (assistant) => {

                const sources =
                  [
                    ...(assistant.sources ??
                      []),
                  ];

                const exists =
                  sources.some(
                    (item) =>
                      item.url ===
                      source.url,
                  );

                if (!exists) {

                  sources.push(
                    source,
                  );
                }

                return {
                  ...assistant,
                  sources,
                };
              },
            );
          },

          // ==================================================
          // ERROR
          // ==================================================

          onError: (
            message,
          ) => {

            setError(
              message,
            );
          },
        },

        controller.signal,
      );

    } catch (caught) {

      if (
        caught instanceof Error &&
        caught.name !== "AbortError"
      ) {

        setError(
          caught.message,
        );
      }

    } finally {

      abortRef.current =
        null;

      setIsStreaming(false);
      setStatus(null);
    }
  }

  // ==========================================================
  // KEYBOARD
  // ==========================================================

  function handleKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {

    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {

      event.preventDefault();

      void sendMessage();
    }
  }

  // ==========================================================
  // AUTH LOADING
  // ==========================================================

  if (authLoading) {

    return (
      <main className="min-h-screen bg-[#0b0e10] text-[#e8edf2]">

        <div className="grid min-h-screen place-items-center">

          <div className="text-center">

            <div className="mx-auto mb-4 grid size-14 place-items-center rounded-2xl bg-[#c6f36b] text-[#101214]">
              <Sparkles size={25} />
            </div>

            <h1 className="font-[Space_Grotesk] text-2xl font-bold">
              Orbit Agent
            </h1>

            <p className="mt-2 text-sm text-[#859097]">
              Loading your account...
            </p>

          </div>

        </div>

      </main>
    );
  }

  // ==========================================================
  // LOGIN
  // ==========================================================

  if (!session) {

    return (
      <main className="min-h-screen bg-[#0b0e10] text-[#e8edf2]">

        <div className="relative grid min-h-screen place-items-center overflow-hidden px-5">

          <div className="pointer-events-none absolute left-1/2 top-1/2 size-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#c6f36b]/5 blur-3xl" />

          <div className="relative w-full max-w-md rounded-3xl border border-[#293136] bg-[#111518]/90 p-8 text-center shadow-2xl shadow-black/40 backdrop-blur">

            <div className="mx-auto mb-5 grid size-16 place-items-center rounded-2xl bg-[#c6f36b] text-[#101214] shadow-lg shadow-[#c6f36b]/10">
              <Sparkles size={28} />
            </div>

            <h1 className="font-[Space_Grotesk] text-3xl font-bold">
              Orbit Agent
            </h1>

            <p className="mt-3 text-sm leading-6 text-[#859097]">
              Your personal AI assistant,
              running on your own machine.
            </p>

            <button
              type="button"
              onClick={
                signInWithGoogle
              }
              className="mt-8 flex w-full items-center justify-center gap-3 rounded-xl bg-white px-5 py-3 font-medium text-[#111610] transition hover:bg-[#e9eceb]"
            >

              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >

                <path
                  fill="#4285F4"
                  d="M21.35 12.27c0-.79-.07-1.55-.22-2.27H12v4.3h5.22a4.46 4.46 0 0 1-1.94 2.92v2.42h3.14c1.84-1.69 2.93-4.18 2.93-7.37Z"
                />

                <path
                  fill="#34A853"
                  d="M12 21.75c2.63 0 4.84-.87 6.45-2.36l-3.14-2.42c-.87.58-1.98.92-3.31.92-2.54 0-4.69-1.72-5.46-4.03H3.29v2.5A9.74 9.74 0 0 0 12 21.75Z"
                />

                <path
                  fill="#FBBC05"
                  d="M6.54 13.86A5.86 5.86 0 0 1 6.23 12c0-.65.11-1.28.31-1.86v-2.5H3.29A9.75 9.75 0 0 0 2.25 12c0 1.57.38 3.05 1.04 4.36l3.25-2.5Z"
                />

                <path
                  fill="#EA4335"
                  d="M12 6.11c1.43 0 2.71.49 3.72 1.45l2.79-2.79C16.84 3.22 14.63 2.25 12 2.25a9.74 9.74 0 0 0-8.71 5.39l3.25 2.5C7.31 7.83 9.46 6.11 12 6.11Z"
                />

              </svg>

              Continue with Google

            </button>

            <p className="mt-5 text-xs text-[#667177]">
              Sign in to keep your Orbit
              chats separate from other
              accounts.
            </p>

          </div>

        </div>

      </main>
    );
  }

  // ==========================================================
  // PROFILE
  // ==========================================================

  const avatarUrl =
    session.user.user_metadata?.avatar_url ??
    session.user.user_metadata?.picture ??
    session.user.user_metadata?.photo_url ??
    null;

  const displayName =
    session.user.user_metadata?.full_name ??
    session.user.user_metadata?.name ??
    session.user.email ??
    "User";

  // ==========================================================
  // MAIN APPLICATION
  // ==========================================================

  return (
    <main className="min-h-screen text-[#e8edf2]">

      {/* HEADER */}

      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8">

        <div className="flex items-center gap-3">

          <div className="grid size-9 place-items-center rounded-xl bg-[#c6f36b] text-[#101214]">
            <Sparkles size={18} />
          </div>

          <div>

            <h1 className="font-[Space_Grotesk] text-lg font-bold">
              Orbit Agent
            </h1>

            <p className="text-xs text-[#859097]">
              Autonomous local intelligence
            </p>

          </div>

        </div>

        <div className="flex items-center gap-2">

          <button
            type="button"
            onClick={
              startNewChat
            }
            className="flex items-center gap-2 rounded-lg border border-[#30383d] px-3 py-2 text-sm hover:border-[#c6f36b] hover:text-[#c6f36b]"
          >

            <Plus size={16} />

            New chat

          </button>

          <div className="flex items-center gap-2 rounded-xl border border-[#30383d] bg-[#171b1e] px-2 py-1.5">

            {avatarUrl ? (

              <img
                src={avatarUrl}
                alt="Profile"
                className="size-7 rounded-full object-cover"
                onError={(event) => {
                  event.currentTarget.style.display =
                    "none";
                }}
              />

            ) : (

              <div className="grid size-7 place-items-center rounded-full bg-[#c6f36b] text-xs font-bold text-[#111610]">

                {String(
                  displayName,
                )
                  .charAt(0)
                  .toUpperCase()}

              </div>

            )}

            <span className="hidden max-w-32 truncate text-sm text-[#a7b1b5] sm:block">

              {displayName}

            </span>

            <button
              type="button"
              onClick={
                signOut
              }
              className="rounded-lg px-2 py-1 text-xs text-[#859097] hover:bg-[#222a2e] hover:text-white"
            >
              Logout
            </button>

          </div>

        </div>

      </header>

      {/* BODY */}

      <div className="mx-auto flex min-h-[calc(100vh-88px)] max-w-6xl gap-8 px-5 pb-5 sm:px-8">

        {/* SIDEBAR */}

        <aside className="hidden w-56 shrink-0 border-r border-[#252d31] pr-5 md:block">

          <div className="mb-4 flex items-center gap-2 px-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#748087]">

            <MessageCircle size={14} />

            Your chats

          </div>

          <div className="space-y-1">

            {conversations
              .filter(
                (conversation) =>
                  conversation.messages
                    .length > 0,
              )
              .sort(
                (a, b) =>
                  b.updatedAt -
                  a.updatedAt,
              )
              .map(
                (conversation) => (

                  <button
                    type="button"
                    key={
                      conversation.id
                    }
                    onClick={() => {

                      if (
                        !isStreaming
                      ) {

                        setActiveId(
                          conversation.id,
                        );

                        setError(null);
                      }
                    }}
                    className={`
                      flex w-full
                      items-start gap-2
                      rounded-lg px-2 py-2
                      text-left text-sm
                      leading-5
                      hover:bg-[#1b2320]
                      hover:text-[#c6f36b]

                      ${
                        conversation.id ===
                        activeId
                          ? "bg-[#1b2320] text-[#c6f36b]"
                          : "text-[#a7b1b5]"
                      }
                    `}
                  >

                    <MessageCircle
                      className="mt-0.5 shrink-0"
                      size={14}
                    />

                    <span className="line-clamp-2">
                      {
                        conversation.title
                      }
                    </span>

                  </button>

                ),
              )}

          </div>

        </aside>

        {/* CHAT */}

        <section className="mx-auto flex min-w-0 max-w-3xl flex-1 flex-col">

          <div className="flex flex-1 flex-col justify-end gap-6 pb-6 pt-8">

            {!active ||
            active.messages.length === 0 ? (

              <div className="m-auto max-w-md text-center">

                <div className="mx-auto mb-5 grid size-14 place-items-center rounded-2xl border border-[#38453a] bg-[#172019] text-[#c6f36b]">

                  <Sparkles size={25} />

                </div>

                <h2 className="font-[Space_Grotesk] text-3xl font-semibold">
                  What can I help you explore?
                </h2>

                <p className="mt-3 text-sm leading-6 text-[#859097]">
                  Orbit can reason about your
                  request, choose tools, retrieve
                  information and synthesize an
                  answer.
                </p>

              </div>

            ) : (

              <>

                {active.messages.map(
                  (
                    message,
                    index,
                  ) => {

                    const isAssistant =
                      message.role ===
                      "assistant";

                    const hasWebTimeline =
                      isAssistant &&
                      (
                        message.agentSteps ??
                        []
                      ).some(
                        (step) =>
                          step.step ===
                            "web_search" ||
                          step.action ===
                            "web_search",
                      );

                    const isCurrentMessage =
                      index ===
                      active.messages.length -
                        1;

                    return (
                      <div
                        key={`${index}-${message.role}`}
                      >

                        {hasWebTimeline && (

                          <AgentTimeline
                            steps={
                              message.agentSteps ??
                              []
                            }
                            active={
                              isStreaming &&
                              isCurrentMessage &&
                              (
                                message.agentSteps ??
                                []
                              ).some(
                                (step) =>
                                  step.status ===
                                  "started",
                              )
                            }
                          />

                        )}

                        <article
                          className={`
                            flex

                            ${
                              message.role ===
                              "user"
                                ? "justify-end"
                                : "justify-start"
                            }
                          `}
                        >

                          <div
                            className={`
                              max-w-[90%]
                              rounded-2xl
                              px-4 py-3
                              text-[15px]
                              leading-7

                              ${
                                message.role ===
                                "user"
                                  ? "rounded-br-sm bg-[#c6f36b] text-[#111610]"
                                  : "rounded-bl-sm border border-[#293136] bg-[#171b1e] text-[#dce3e6]"
                              }
                            `}
                          >

                            <Markdown
                              content={
                                message.content
                              }
                              streaming={
                                isAssistant &&
                                !message.content &&
                                isStreaming &&
                                isCurrentMessage
                              }
                            />

                            {isAssistant &&
                              message.sources &&
                              message.sources
                                .length > 0 && (

                                <div className="mt-4 space-y-2">

                                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#748087]">
                                    Sources
                                  </p>

                                  {message.sources.map(
                                    (
                                      source,
                                    ) => (

                                      <a
                                        key={
                                          source.url
                                        }
                                        href={
                                          source.url
                                        }
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center justify-between rounded-xl border border-[#30383d] bg-[#171b1e] px-3 py-2 text-sm hover:border-[#c6f36b]"
                                      >

                                        <span className="min-w-0">

                                          <span className="block truncate text-[#dce3e6]">
                                            {
                                              source.title
                                            }
                                          </span>

                                          <span className="text-xs text-[#77838a]">
                                            {
                                              getHostname(
                                                source.url,
                                              )
                                            }
                                          </span>

                                        </span>

                                        <ExternalLink
                                          size={14}
                                          className="ml-3 shrink-0 text-[#859097]"
                                        />

                                      </a>

                                    ),
                                  )}

                                </div>

                              )}

                          </div>

                        </article>

                      </div>
                    );
                  },
                )}

              </>

            )}

            {status && (
              <p className="text-xs text-[#9ca8a8]">
                {status}
              </p>
            )}

            {error && (
              <div className="rounded-xl border border-[#713e3e] bg-[#29191a] px-4 py-3 text-sm text-[#ffb7b0]">
                {error}
              </div>
            )}

          </div>

          {/* INPUT */}

          <form
            onSubmit={
              sendMessage
            }
            className="rounded-2xl border border-[#30383d] bg-[#171b1e] p-2 shadow-2xl shadow-black/20"
          >

            <textarea
              value={draft}
              onChange={(
                event,
              ) =>
                setDraft(
                  event.target.value,
                )
              }
              onKeyDown={
                handleKeyDown
              }
              rows={1}
              placeholder="Message Orbit Agent..."
              className="max-h-40 min-h-12 w-full resize-none bg-transparent px-3 py-3 outline-none placeholder:text-[#667177]"
            />

            <div className="flex justify-end px-2 pb-1">

              {isStreaming ? (

                <button
                  type="button"
                  onClick={() => {

                    markCurrentAgentStopped();

                    abortRef.current?.abort();

                    setIsStreaming(false);
                  }}
                  aria-label="Stop generation"
                  className="grid size-9 place-items-center rounded-xl bg-[#30383d]"
                >

                  <Square
                    size={15}
                    fill="currentColor"
                  />

                </button>

              ) : (

                <button
                  type="submit"
                  disabled={
                    !draft.trim()
                  }
                  aria-label="Send message"
                  className="grid size-9 place-items-center rounded-xl bg-[#c6f36b] text-[#111610] disabled:opacity-40"
                >

                  <Send size={16} />

                </button>

              )}

            </div>

          </form>

        </section>

      </div>

    </main>
  );
}

// ============================================================
// MARKDOWN
// ============================================================

function Markdown({
  content,
  streaming,
}: {
  content: string;
  streaming: boolean;
}) {

  if (
    streaming &&
    !content
  ) {

    return (
      <span className="inline-flex gap-1">

        <i className="size-1.5 animate-bounce rounded-full bg-[#c6f36b]" />

        <i className="size-1.5 animate-bounce rounded-full bg-[#c6f36b] [animation-delay:120ms]" />

        <i className="size-1.5 animate-bounce rounded-full bg-[#c6f36b] [animation-delay:240ms]" />

      </span>
    );
  }

  return (
    <div className="prose prose-invert max-w-none [&_a]:text-[#c6f36b] [&_a]:underline [&_code]:rounded [&_code]:bg-[#0e1113] [&_code]:px-1 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-[#0e1113]">

      <ReactMarkdown
        remarkPlugins={[
          remarkGfm,
        ]}
        components={{

          code({
            children,
            className,
          }) {

            const text =
              String(children)
                .replace(
                  /\n$/,
                  "",
                );

            return className ? (

              <div className="group relative">

                <button
                  type="button"
                  onClick={() =>
                    void navigator.clipboard.writeText(
                      text,
                    )
                  }
                  className="absolute right-2 top-2 text-[#859097] hover:text-white"
                  aria-label="Copy code"
                >

                  <Copy size={14} />

                </button>

                <pre
                  className={
                    className
                  }
                >
                  <code>
                    {children}
                  </code>
                </pre>

              </div>

            ) : (

              <code
                className={
                  className
                }
              >
                {children}
              </code>

            );
          },
        }}
      >
        {content}
      </ReactMarkdown>

    </div>
  );
}

// ============================================================
// CHAT TITLE
// ============================================================

function makeTitle(
  message: string,
): string {

  const text =
    message
      .trim()
      .replace(
        /\s+/g,
        " ",
      );

  const lower =
    text.toLowerCase();

  if (
    lower.includes("cricket") &&
    lower.includes("image")
  ) {
    return "Cricket image request";
  }

  if (
    lower.includes("cricket")
  ) {
    return "Cricket discussion";
  }

  if (
    lower.includes("encapsulation") &&
    lower.includes("java")
  ) {
    return "Java encapsulation";
  }

  if (
    lower.includes("latest") &&
    lower.includes("ai")
  ) {
    return "Latest AI news";
  }

  if (
    lower.includes("react") &&
    (
      lower.includes("error") ||
      lower.includes("issue") ||
      lower.includes("problem")
    )
  ) {
    return "React troubleshooting";
  }

  if (
    lower.includes("tcp") ||
    lower.includes("ip model")
  ) {
    return "TCP/IP model";
  }

  if (
    lower.includes("linked list")
  ) {
    return "Linked list explanation";
  }

  const stopWords =
    new Set([
      "a",
      "an",
      "and",
      "are",
      "can",
      "could",
      "do",
      "does",
      "for",
      "give",
      "get",
      "how",
      "i",
      "in",
      "is",
      "it",
      "me",
      "my",
      "of",
      "please",
      "tell",
      "the",
      "to",
      "what",
      "with",
      "you",
    ]);

  const words =
    text
      .replace(
        /[?!.,:;()[\]{}]/g,
        "",
      )
      .split(/\s+/)
      .filter(
        (word) =>
          word.length > 1 &&
          !stopWords.has(
            word.toLowerCase(),
          ),
      );

  let title =
    words
      .slice(0, 5)
      .join(" ");

  if (!title) {
    title = "New chat";
  }

  title =
    title.charAt(0).toUpperCase() +
    title.slice(1);

  return title;
}

// ============================================================
// HOSTNAME
// ============================================================

function getHostname(
  url: string,
): string {

  try {

    return new URL(
      url,
    ).hostname;

  } catch {

    return url;
  }
}