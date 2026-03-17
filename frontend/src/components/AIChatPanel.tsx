'use client';

import { useEffect, useState, useRef } from 'react';
import type { FilledBracket } from '@/types/bracket';

const API = process.env.NEXT_PUBLIC_API_URL || '';

/** LLM can take 30–60+ seconds; use a long timeout to avoid spurious 500s. */
const CHAT_FETCH_TIMEOUT_MS = 120_000;

const SYSTEM_PROMPT = `You are a helpful assistant for a March Madness NCAA bracket app. Answer briefly about college basketball, bracket strategy, seeds, upsets, and predictions. Keep responses concise (1-3 short paragraphs). If the user mentions their bracket or champion, you can comment on it.`;

type Message = { role: 'user' | 'assistant'; content: string };

type LLMStatus = {
  enabled: boolean;
  reachable?: boolean;
  base_url?: string;
  model?: string;
  message?: string;
};

export function AIChatPanel({ filled, sidebar = false }: { filled: FilledBracket | null; sidebar?: boolean }) {
  const [status, setStatus] = useState<LLMStatus | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/llm/status`)
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) setStatus({ enabled: false, message: 'Could not reach API' });
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || !status?.enabled || status?.reachable === false || sending) return;
    const userMessage: Message = { role: 'user', content: text };
    setMessages((m) => [...m, userMessage]);
    setInput('');
    setSending(true);
    try {
      const context = filled?.champion
        ? ` [User's current bracket champion: ${filled.champion}.]`
        : '';
      const chatMessages: { role: string; content: string }[] = [
        { role: 'system', content: SYSTEM_PROMPT + context },
        ...messages.map((m) => ({ role: m.role, content: m.content })),
        { role: 'user', content: text },
      ];
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), CHAT_FETCH_TIMEOUT_MS);
      const res = await fetch(`${API}/api/llm/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: chatMessages }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok && data.reply) {
        setMessages((m) => [...m, { role: 'assistant', content: data.reply }]);
      } else {
        const errMsg =
          data.error ||
          (typeof data.detail === 'string' ? data.detail : null) ||
          (res.status === 504 || res.status === 503
            ? 'Request timed out or server busy. Ollama can take 1–2 minutes; try again or use a smaller model (e.g. llama3.2:1b).'
            : 'Sorry, the AI could not respond.');
        setMessages((m) => [...m, { role: 'assistant', content: errMsg }]);
      }
    } catch (e) {
      const isTimeout = e instanceof Error && e.name === 'AbortError';
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: isTimeout
            ? 'Request took too long. Ollama can need 1–2 minutes; try again or use a smaller model.'
            : 'Network error. Is the backend running?',
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const pad = sidebar ? '' : 'mt-2 pl-5';
  if (status === null) {
    return (
      <div className={`text-sm text-ncaa-dark/60 ${pad}`}>
        Checking AI…
      </div>
    );
  }

  if (!status.enabled || status.reachable === false) {
    return (
      <div className={`text-sm text-ncaa-dark/70 space-y-1 ${pad}`}>
        <p>AI chat uses a local LLM (Ollama). To enable:</p>
        <ol className="list-decimal pl-5 text-xs">
          <li>Install <a href="https://ollama.com" target="_blank" rel="noopener noreferrer" className="text-ncaa-blue underline">Ollama</a></li>
          <li>Run <code className="bg-ncaa-dark/10 px-1 rounded">ollama pull llama3.2</code></li>
          <li>Start backend with Ollama running</li>
        </ol>
        {status.message && <p className="text-xs text-ncaa-dark/60">{status.message}</p>}
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${sidebar ? 'flex flex-col min-h-[280px]' : 'mt-3 pl-5'}`}>
      <div className={`rounded-lg border border-ncaa-dark/15 bg-ncaa-dark/[0.03] overflow-y-auto ${sidebar ? 'flex-1 min-h-[200px]' : 'max-h-64'}`}>
        {messages.length === 0 && (
          <p className="p-3 text-sm text-ncaa-dark/60">
            Ask about bracket strategy, seeds, upsets, or your picks. Keep it short.
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`p-3 text-sm ${msg.role === 'user' ? 'bg-ncaa-blue/10 border-l-2 border-ncaa-blue' : 'bg-white/80'}`}
          >
            <span className="font-display font-semibold text-ncaa-dark/70 text-xs uppercase">
              {msg.role === 'user' ? 'You' : 'AI'}
            </span>
            <p className="mt-0.5 text-ncaa-dark whitespace-pre-wrap">{msg.content}</p>
          </div>
        ))}
        {sending && (
          <div className="p-3 text-sm text-ncaa-dark/60">Thinking…</div>
        )}
        <div ref={bottomRef} />
      </div>
      <form
        onSubmit={(e) => { e.preventDefault(); send(); }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about brackets or picks…"
          className="flex-1 min-w-0 rounded border border-ncaa-dark/20 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ncaa-blue/50"
          disabled={sending}
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="font-display font-semibold px-4 py-2 rounded bg-ncaa-blue text-white disabled:opacity-50 hover:bg-ncaa-blue/90 text-sm"
        >
          Send
        </button>
      </form>
    </div>
  );
}
