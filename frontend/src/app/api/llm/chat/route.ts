import { NextRequest, NextResponse } from 'next/server';

const BACKEND = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
/** Ollama often takes 30–60+ seconds; proxy must wait long enough to avoid 500. */
const LLM_TIMEOUT_MS = 120_000;

export async function POST(req: NextRequest) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), LLM_TIMEOUT_MS);
  try {
    const body = await req.json();
    const res = await fetch(`${BACKEND}/llm/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    const data = await res.json().catch(() => ({}));
    // Forward backend status and body; if backend returned 503, pass it through
    return NextResponse.json(data, { status: res.ok ? 200 : res.status });
  } catch (e) {
    clearTimeout(timeoutId);
    const isTimeout = e instanceof Error && e.name === 'AbortError';
    return NextResponse.json(
      {
        ok: false,
        error: isTimeout
          ? 'Request timed out. Ollama can take 1–2 minutes; try again or use a smaller model (e.g. llama3.2:1b).'
          : 'Could not reach backend. Is it running on ' + BACKEND + '?',
      },
      { status: 503 }
    );
  }
}
