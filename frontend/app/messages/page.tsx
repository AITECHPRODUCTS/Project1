"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Identity = { user?: { email?: string; account_type?: string } };
type ApplicationOption = {
  application_id: string;
  offer_name: string;
  application_status: string;
  counterparty_name: string;
};
type Conversation = {
  id: string;
  application_id: string;
  subject: string;
  offer_name: string;
  counterparty_name: string;
  status: string;
  last_message_at: string | null;
  last_message_preview: string;
  unread_count: number;
};
type PartnerMessage = {
  id: string;
  sender_workspace_id: string;
  sender_email: string;
  body: string;
  created_at: string | null;
  read_at: string | null;
  is_mine: boolean;
  is_read: boolean;
};
type ApplicationResponse = { count: number; data: ApplicationOption[] };
type ConversationResponse = {
  count: number;
  total_count: number;
  can_send: boolean;
  data: Conversation[];
};
type MessageResponse = {
  conversation_id: string;
  application_id: string;
  can_send: boolean;
  data: PartnerMessage[];
};
type PartnerActivity = {
  id: string;
  actor: string;
  action: string;
  outcome: string;
  created_at: string | null;
};
type ActivityResponse = { count: number; data: PartnerActivity[] };

function activityLabel(action: string): string {
  if (action === "partner.message.sent") return "Message sent";
  if (action === "partner.messages.marked_read") return "Messages marked as read";
  return "Conversation activity recorded";
}

function dateTime(value: string | null): string {
  if (!value) return "No messages yet";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : date.toLocaleString();
}

export default function PartnerMessagesPage() {
  const [email, setEmail] = useState("");
  const [applications, setApplications] = useState<ApplicationOption[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedApplicationId, setSelectedApplicationId] = useState("");
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const [messages, setMessages] = useState<PartnerMessage[]>([]);
  const [activityEvents, setActivityEvents] = useState<PartnerActivity[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [activityError, setActivityError] = useState("");
  const [draft, setDraft] = useState("");
  const [canSend, setCanSend] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadInbox = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const identity = await apiFetch<Identity>("/api/auth/me");
      const role = identity.user?.account_type;
      if (role !== "affiliate_publisher" && role !== "merchant_product_owner") {
        window.location.replace(identity.user ? "/dashboard" : "/login");
        return;
      }
      setEmail(identity.user?.email || "");
      const [applicationResponse, conversationResponse] = await Promise.all([
        apiFetch<ApplicationResponse>("/api/partner/messageable-applications"),
        apiFetch<ConversationResponse>("/api/partner/conversations"),
      ]);
      const applicationRows = Array.isArray(applicationResponse.data) ? applicationResponse.data : [];
      const conversationRows = Array.isArray(conversationResponse.data) ? conversationResponse.data : [];
      setApplications(applicationRows);
      setConversations(conversationRows);
      setCanSend(conversationResponse.can_send !== false);

      const requestedApplication = new URLSearchParams(window.location.search).get("applicationId") || "";
      const nextApplication = requestedApplication && applicationRows.some(item => item.application_id === requestedApplication)
        ? requestedApplication
        : conversationRows[0]?.application_id || applicationRows[0]?.application_id || "";
      setSelectedApplicationId(nextApplication);
      const matchingConversation = conversationRows.find(item => item.application_id === nextApplication);
      setSelectedConversationId(matchingConversation?.id || "");
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Partner messages could not be loaded.";
      if (message.startsWith("401:")) window.location.replace("/login");
      else setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMessages = useCallback(async (conversationId: string) => {
    setLoadingMessages(true);
    setError("");
    try {
      const result = await apiFetch<MessageResponse>(
        "/api/partner/conversations/" + encodeURIComponent(conversationId) + "/messages"
      );
      setMessages(Array.isArray(result.data) ? result.data : []);
      setCanSend(result.can_send !== false);
      setConversations(previous => previous.map(item =>
        item.id === conversationId ? { ...item, unread_count: 0 } : item
      ));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Conversation messages could not be loaded.");
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  const loadActivity = useCallback(async (conversationId: string) => {
    setLoadingActivity(true);
    setActivityError("");
    try {
      const result = await apiFetch<ActivityResponse>(
        "/api/partner/conversations/" + encodeURIComponent(conversationId) + "/activity"
      );
      setActivityEvents(Array.isArray(result.data) ? result.data : []);
    } catch (cause) {
      setActivityEvents([]);
      setActivityError(cause instanceof Error ? cause.message : "Conversation activity could not be loaded.");
    } finally {
      setLoadingActivity(false);
    }
  }, []);

  useEffect(() => { void loadInbox(); }, [loadInbox]);
  useEffect(() => {
    if (!selectedConversationId) {
      setMessages([]);
      setActivityEvents([]);
      setActivityError("");
      return;
    }
    // Load messages first because opening the thread may persist recipient read receipts.
    void loadMessages(selectedConversationId).then(() => loadActivity(selectedConversationId));
  }, [selectedConversationId, loadMessages, loadActivity]);

  const selectApplication = (applicationId: string) => {
    setSelectedApplicationId(applicationId);
    const existing = conversations.find(item => item.application_id === applicationId);
    setSelectedConversationId(existing?.id || "");
    setNotice("");
    setError("");
  };

  const selectConversation = (conversation: Conversation) => {
    setSelectedApplicationId(conversation.application_id);
    setSelectedConversationId(conversation.id);
    setNotice("");
    setError("");
  };

  const sendMessage = async () => {
    const body = draft.trim();
    if (!body || sending || !canSend) return;
    if (!selectedApplicationId) {
      setError("Select a program application before starting a conversation.");
      return;
    }
    setSending(true);
    setError("");
    setNotice("");
    let activityConversationId = selectedConversationId;
    try {
      if (selectedConversationId) {
        const result = await apiFetch<{ message: PartnerMessage }>(
          "/api/partner/conversations/" + encodeURIComponent(selectedConversationId) + "/messages",
          { method: "POST", body: JSON.stringify({ body }) }
        );
        setMessages(previous => [...previous, result.message]);
      } else {
        const result = await apiFetch<{ conversation_id: string; message: PartnerMessage }>(
          "/api/partner/conversations",
          {
            method: "POST",
            body: JSON.stringify({ application_id: selectedApplicationId, body }),
          }
        );
        activityConversationId = result.conversation_id;
        setSelectedConversationId(result.conversation_id);
        setMessages([result.message]);
      }
      setDraft("");
      setNotice("Message sent and saved to this program conversation.");
      const response = await apiFetch<ConversationResponse>("/api/partner/conversations");
      setConversations(Array.isArray(response.data) ? response.data : []);
      // Activity is supplemental; do not keep the message composer locked while it refreshes.
      if (activityConversationId) void loadActivity(activityConversationId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Message could not be sent.");
    } finally {
      setSending(false);
    }
  };

  const selectedConversation = conversations.find(item => item.id === selectedConversationId) || null;
  const selectedApplication = applications.find(item => item.application_id === selectedApplicationId) || null;

  return (
    <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-6">
          <div>
            <a href="/dashboard" className="text-sm font-bold text-indigo-700">← Workspace overview</a>
            <p className="mt-5 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Partner operations</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Partner messages</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Private, program-specific conversations between approved marketplace participants. Messages are persisted and access is restricted to the merchant and publisher workspaces on the application.</p>
            {email && <p className="mt-2 text-xs text-slate-400">Signed in as {email}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => void loadInbox()} disabled={loading} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">{loading ? "Refreshing…" : "Refresh inbox"}</button>
            <a href="/programs" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold">My programs</a>
          </div>
        </header>

        {error && <p role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
        {notice && <p role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</p>}

        <section className="mt-6 grid min-h-[620px] gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
          <aside className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-black">Inbox</h2>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold">{conversations.reduce((total, item) => total + item.unread_count, 0)} unread</span>
            </div>
            <div className="mt-4 space-y-2">
              {conversations.map(item => (
                <button key={item.id} type="button" onClick={() => selectConversation(item)}
                  aria-pressed={selectedConversationId === item.id}
                  className={"block w-full rounded-xl border p-3 text-left transition " + (selectedConversationId === item.id ? "border-indigo-300 bg-indigo-50" : "border-slate-100 bg-white hover:bg-slate-50")}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm font-bold text-slate-800">{item.offer_name}</span>
                    {item.unread_count > 0 && <span className="shrink-0 rounded-full bg-indigo-600 px-2 py-0.5 text-[10px] font-black text-white">{item.unread_count}</span>}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{item.counterparty_name}</p>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{item.last_message_preview || item.subject}</p>
                  <p className="mt-2 text-[10px] text-slate-400">{dateTime(item.last_message_at)}</p>
                </button>
              ))}
              {!loading && conversations.length === 0 && <p className="rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">No conversations yet. Choose a program to contact its merchant or publisher.</p>}
            </div>
          </aside>

          <section className="flex min-h-[620px] flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
            <div className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-100 pb-4">
              <div className="min-w-[220px] flex-1">
                <label htmlFor="partner-message-program" className="text-xs font-bold uppercase tracking-wider text-slate-500">Program</label>
                <select id="partner-message-program" aria-label="Program" value={selectedApplicationId} onChange={event => selectApplication(event.target.value)}
                  className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm">
                  <option value="">Select a program application</option>
                  {applications.map(item => <option key={item.application_id} value={item.application_id}>{item.offer_name} · {item.application_status.replaceAll("_", " ")}</option>)}
                </select>
                <p className="mt-2 text-xs text-slate-500">{selectedConversation ? selectedConversation.counterparty_name : selectedApplication?.counterparty_name || "Select a program to start a discussion."}</p>
              </div>
              {selectedConversation && <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-800">{selectedConversation.status}</span>}
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto py-5" aria-live="polite">
              {loadingMessages && <p role="status" className="text-sm text-slate-500">Loading conversation…</p>}
              {messages.map(item => (
                <article key={item.id} className={"max-w-[90%] rounded-2xl p-4 sm:max-w-[78%] " + (item.is_mine ? "ml-auto bg-indigo-600 text-white" : "mr-auto bg-slate-100 text-slate-800")}>
                  <div className="flex flex-wrap items-center justify-between gap-3 text-[11px] opacity-75">
                    <span>{item.is_mine ? "You" : item.sender_email}</span>
                    <time>{dateTime(item.created_at)}</time>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6">{item.body}</p>
                  {item.is_mine && <p className="mt-2 text-right text-[10px] opacity-75">{item.is_read ? "Read" : "Sent"}</p>}
                </article>
              ))}
              {!loadingMessages && messages.length === 0 && <div className="mx-auto mt-12 max-w-md text-center"><h2 className="font-black text-slate-700">{selectedApplication ? "Start a program conversation" : "Choose a program"}</h2><p className="mt-2 text-sm leading-6 text-slate-500">Discuss program requirements, permitted promotion channels, tracking questions and partner support. Do not send passwords, payment credentials or sensitive customer data.</p></div>}
              {selectedConversationId && (
                <section aria-label="Conversation activity" className="mt-6 border-t border-slate-100 pt-4">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-xs font-black uppercase tracking-wider text-slate-500">Conversation activity</h3>
                    <span className="text-[11px] text-slate-400">{loadingActivity ? "Loading…" : activityEvents.length + " events"}</span>
                  </div>
                  {activityError && <p role="status" className="mt-2 text-xs text-amber-700">{activityError}</p>}
                  {!loadingActivity && !activityError && activityEvents.length === 0 && <p className="mt-2 text-xs text-slate-400">No activity has been recorded yet.</p>}
                  <ol className="mt-3 space-y-2">
                    {activityEvents.slice(-10).map(item => (
                      <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2">
                        <span className="text-xs font-semibold text-slate-700">{activityLabel(item.action)}</span>
                        <span className="text-[10px] text-slate-500">{item.actor} · {dateTime(item.created_at)}</span>
                      </li>
                    ))}
                  </ol>
                </section>
              )}
            </div>

            <div className="border-t border-slate-100 pt-4">
              <label htmlFor="partner-message-body" className="text-xs font-bold uppercase tracking-wider text-slate-500">Message</label>
              <textarea id="partner-message-body" aria-label="Message" value={draft} onChange={event => setDraft(event.target.value)} rows={3} maxLength={5000}
                placeholder="Write a message about this affiliate program…" disabled={!selectedApplicationId || !canSend || selectedConversation?.status === "closed"}
                className="mt-2 w-full resize-y rounded-xl border border-slate-200 px-3 py-3 text-sm leading-6 disabled:bg-slate-50"/>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-slate-400">{draft.length}/5000 characters · Messages are visible to both program participants.</p>
                <button type="button" onClick={() => void sendMessage()} disabled={!draft.trim() || !selectedApplicationId || !canSend || sending || selectedConversation?.status === "closed"}
                  className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">{sending ? "Sending…" : "Send message"}</button>
              </div>
              {!canSend && <p className="mt-2 text-xs text-amber-700">Your workspace role can read this conversation but cannot send messages.</p>}
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}
