import { act, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChatStateAdapterProvider, useChatStateAdapter } from "@/features/chat/ChatStateAdapter";

const mocks = vi.hoisted(() => ({
  getSession: vi.fn(), getTrace: vi.fn(), getOrganization: vi.fn(),
}));

vi.mock("@/lib/session-api", async (original) => ({
  ...(await original<typeof import("@/lib/session-api")>()),
  getSession: mocks.getSession, getMessageTrace: mocks.getTrace,
  getSessionOrganization: mocks.getOrganization,
}));
vi.mock("@/features/chat/transport/UnifiedTurnClient", () => ({
  UnifiedTurnClient: class {
    connected = true;
    connect() {} disconnect() {} setResumeState() {} send() {}
  },
}));

let chat: ReturnType<typeof useChatStateAdapter>;
function Probe() { chat = useChatStateAdapter(); return null; }
const detail = () => ({
  id: "session-a", session_id: "session-a", title: "Cached session", status: "completed",
  updated_at: 10, created_at: 1, preferences: {}, active_turns: [],
  messages: [{ id: 2, role: "assistant", content: "Saved answer", parent_message_id: null,
    events: [{ type: "done", seq: 3, turn_id: "turn-a", content: "", timestamp: 3 }],
    trace: { turn_id: "turn-a", total: 3, last_seq: 3, truncated: true } }],
});

beforeEach(() => {
  localStorage.clear();
  mocks.getSession.mockReset().mockImplementation(async () => detail());
  mocks.getOrganization.mockReset().mockResolvedValue({
    ...detail(), messages: undefined,
  });
  mocks.getTrace.mockReset().mockResolvedValue({
    turn_id: "turn-a", total: 3, last_seq: 3, complete: true,
    events: [
      { type: "progress", seq: 1, turn_id: "turn-a", content: "Current reasoning", timestamp: 1 },
      { type: "content", seq: 2, turn_id: "turn-a", content: "Saved answer", timestamp: 2 },
      { type: "done", seq: 3, turn_id: "turn-a", content: "", timestamp: 3 },
    ],
  });
});

describe("warm navigation memory", () => {
  it("does not warm older traces after the newest two are already resident", async () => {
    mocks.getSession.mockResolvedValue({ ...detail(), messages: [2, 4, 6].map(id => ({
      ...detail().messages[0], id,
      trace: { turn_id: `turn-${id}`, total: 3, last_seq: 3, truncated: true },
    })) });
    mocks.getTrace.mockImplementation(async (_sessionId, id) => ({
      turn_id: `turn-${id}`, total: 3, last_seq: 3, complete: true,
      events: [1, 2, 3].map(seq => ({ type: seq === 3 ? "done" : "progress",
        seq, turn_id: `turn-${id}`, content: "Trace", timestamp: seq })),
    }));
    render(<ChatStateAdapterProvider><Probe /></ChatStateAdapterProvider>);
    await act(async () => { await chat.loadSession("session-a"); });
    await waitFor(() => expect(chat.state.messages.filter(message =>
      message.trace?.truncated === false)).toHaveLength(2));
    expect(mocks.getTrace.mock.calls.map(call => call[1])).toEqual([4, 6]);
    act(() => { chat.newSession(); });
    act(() => { chat.showCachedSession("session-a"); });
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 30)); });
    expect(mocks.getTrace.mock.calls.map(call => call[1])).toEqual([4, 6]);
    expect(chat.state.messages[0].trace?.truncated).toBe(true);
  });

  it("keeps an opened trace when collapsed, selected away and reopened", async () => {
    render(<ChatStateAdapterProvider><Probe /></ChatStateAdapterProvider>);
    await act(async () => { await chat.loadSession("session-a"); });
    await act(async () => { await chat.loadMessageTrace("session-a", 2); });
    const events = chat.state.messages[0].events;
    expect(events).toHaveLength(3);
    act(() => { chat.releaseMessageTrace("session-a", 2); });
    act(() => { chat.newSession(); });
    act(() => { expect(chat.showCachedSession("session-a")).toBe(true); });
    await act(async () => { await chat.loadMessageTrace("session-a", 2); });
    expect(chat.state.messages[0].events).toBe(events);
    expect(mocks.getTrace).toHaveBeenCalledTimes(1);
  });

  it("checks a small revision in the background without refetching an unchanged transcript", async () => {
    render(<ChatStateAdapterProvider><Probe /></ChatStateAdapterProvider>);
    await act(async () => { await chat.loadSession("session-a"); });
    await act(async () => { await chat.loadMessageTrace("session-a", 2); });
    const message = chat.state.messages[0];
    await act(async () => { await chat.loadSession("session-a", { revalidate: true }); });
    expect(mocks.getSession).toHaveBeenCalledTimes(1);
    expect(chat.state.messages[0]).toBe(message);
    expect(chat.state.messages[0].trace?.truncated).toBe(false);
  });

  it("refreshes a changed server revision without keeping an old trace", async () => {
    render(<ChatStateAdapterProvider><Probe /></ChatStateAdapterProvider>);
    await act(async () => { await chat.loadSession("session-a"); });
    await act(async () => { await chat.loadMessageTrace("session-a", 2); });
    mocks.getOrganization.mockResolvedValue({ ...detail(), updated_at: 11 });
    mocks.getSession.mockResolvedValue({ ...detail(), updated_at: 11,
      messages: [{ ...detail().messages[0], content: "Edited answer",
        trace: { turn_id: "turn-new", total: 1, last_seq: 1, truncated: false }, events: [] }] });
    await act(async () => { await chat.loadSession("session-a", { revalidate: true }); });
    expect(chat.state.messages[0].content).toBe("Edited answer");
    expect(chat.state.messages[0].trace?.turn_id).toBe("turn-new");
  });
});
