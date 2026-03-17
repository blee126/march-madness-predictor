import { NextResponse } from 'next/server';

const BACKEND = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const LLM_TIMEOUT_MS = 120_000;

export async function GET() {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), LLM_TIMEOUT_MS);
  try {
    const res = await fetch(`${BACKEND}/llm/status`, { signal: controller.signal });
    clearTimeout(timeoutId);
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    clearTimeout(timeoutId);
    return NextResponse.json(
      { enabled: false, message: 'Could not reach backend. Is it running on ' + BACKEND + '?' },
      { status: 503 }
    );
  }
}
