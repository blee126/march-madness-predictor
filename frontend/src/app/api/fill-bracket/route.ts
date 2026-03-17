import { NextRequest, NextResponse } from 'next/server';

const BACKEND = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
/** Fill-bracket can call Ollama (user prompt, sentiment); use long timeout to avoid proxy socket hang up. */
const FILL_BRACKET_TIMEOUT_MS = 180_000;

export async function POST(req: NextRequest) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FILL_BRACKET_TIMEOUT_MS);
  try {
    const body = await req.json();
    const res = await fetch(`${BACKEND}/fill-bracket`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.ok ? 200 : res.status });
  } catch (e) {
    clearTimeout(timeoutId);
    const isTimeout = e instanceof Error && e.name === 'AbortError';
    return NextResponse.json(
      {
        detail: isTimeout
          ? 'Fill request timed out. If you used a prompt or sentiment, the LLM can take 1–2 minutes; try again.'
          : 'Could not reach backend. Is it running on ' + BACKEND + '?',
      },
      { status: 503 }
    );
  }
}
