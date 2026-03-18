'use client';

import { useEffect, useState, useCallback } from 'react';
import { BracketView } from '@/components/BracketView';
import { FullBracketView } from '@/components/FullBracketView';
import { ExportButtons } from '@/components/ExportButtons';
import { ScoreBracketSection } from '@/components/ScoreBracketSection';
import { AIChatPanel } from '@/components/AIChatPanel';
import type { BracketTemplate, FilledBracket } from '@/types/bracket';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const BRACKET_ID_KEY = 'march-madness-bracket-id';
const FILL_COOLDOWN_KEY = 'march-madness-fill-at';
const FILL_COOLDOWN_MS = 2 * 60 * 1000; // 2 minutes between fills

const PREFERENCE_MIN = 0.25;
const PREFERENCE_MAX = 3;
const PREFERENCE_STEP = 0.1;

const DEFAULT_PREFERENCES = {
  seed_weight: 1,
  offense_weight: 1,
  defense_weight: 1,
  efficiency_weight: 1,
  tempo_weight: 1,
  upset_tendency: 1,
};

function generateBracketId(): string {
  return `br-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export default function BracketPage() {
  const [bracket, setBracket] = useState<BracketTemplate | null>(null);
  const [filled, setFilled] = useState<FilledBracket | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filling, setFilling] = useState(false);
  const [viewMode, setViewMode] = useState<'list' | 'full'>('full');
  const [bracketId, setBracketId] = useState<string | null>(null);
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
  const [cooldownSecs, setCooldownSecs] = useState<number | null>(null);
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [userPrompt, setUserPrompt] = useState('');
  const [sentimentText, setSentimentText] = useState('');
  const [sentimentResult, setSentimentResult] = useState<{ summary: string; teams: { name: string; sentiment: number }[] } | null>(null);
  const [useSentimentWhenFilling, setUseSentimentWhenFilling] = useState(false);
  const [usePrecomputedSentiment, setUsePrecomputedSentiment] = useState(false);
  const [sentimentLoading, setSentimentLoading] = useState(false);
  const [deterministicFill, setDeterministicFill] = useState(false);

  const loadBracket = useCallback(async () => {
    try {
      const bracketUrl = API ? `${API}/bracket` : '/api/bracket';
      const res = await fetch(bracketUrl);
      if (!res.ok) throw new Error('Bracket not found');
      const data = await res.json();
      setBracket(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load bracket');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBracket();
  }, [loadBracket]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(BRACKET_ID_KEY);
      setBracketId(stored);
    }
  }, [filled]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const check = () => {
      const raw = localStorage.getItem(FILL_COOLDOWN_KEY);
      if (!raw) {
        setCooldownSecs(null);
        return;
      }
      const at = parseInt(raw, 10);
      const elapsed = Date.now() - at;
      if (elapsed >= FILL_COOLDOWN_MS) {
        localStorage.removeItem(FILL_COOLDOWN_KEY);
        setCooldownSecs(null);
        return;
      }
      setCooldownSecs(Math.ceil((FILL_COOLDOWN_MS - elapsed) / 1000));
    };
    check();
    const t = setInterval(check, 1000);
    return () => clearInterval(t);
  }, [filled]);

  const isOnCooldown = cooldownSecs !== null && cooldownSecs > 0;
  const cooldownLabel = isOnCooldown && cooldownSecs != null
    ? `Try again in ${Math.floor(cooldownSecs / 60)}:${String(cooldownSecs % 60).padStart(2, '0')}`
    : null;

  const fillWithAI = async () => {
    if (isOnCooldown) return;
    setFilling(true);
    try {
      const sentiment_teams =
        useSentimentWhenFilling && sentimentResult?.teams?.length
          ? Object.fromEntries(sentimentResult.teams.map((t) => [t.name, t.sentiment]))
          : undefined;
      const res = await fetch(`${API}/api/fill-bracket`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          preferences,
          user_prompt: userPrompt.trim() || undefined,
          sentiment_teams,
          use_precomputed_sentiment: usePrecomputedSentiment || undefined,
          deterministic: deterministicFill || undefined,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = (data && typeof data.detail === 'string') ? data.detail : (data?.detail?.msg ?? 'Fill failed');
        throw new Error(msg);
      }
      setFilled(data as FilledBracket);
      // Clear prompt after a successful fill so the next fill starts fresh
      setUserPrompt('');
      const id = generateBracketId();
      if (typeof window !== 'undefined') {
        localStorage.setItem(BRACKET_ID_KEY, id);
        localStorage.setItem(FILL_COOLDOWN_KEY, String(Date.now()));
      }
      setBracketId(id);
      setCooldownSecs(Math.ceil(FILL_COOLDOWN_MS / 1000));
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to fill bracket';
      setError(msg);
      // Clear so user can dismiss and try again
      setTimeout(() => setError(null), 8000);
    } finally {
      setFilling(false);
    }
  };

  const clearCooldown = () => {
    if (typeof window !== 'undefined') localStorage.removeItem(FILL_COOLDOWN_KEY);
    setCooldownSecs(null);
  };

  const SENTIMENT_FETCH_TIMEOUT_MS = 120_000;
  const analyzeSentiment = async () => {
    const text = sentimentText.trim();
    if (!text) return;
    setSentimentLoading(true);
    setSentimentResult(null);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), SENTIMENT_FETCH_TIMEOUT_MS);
    try {
      const res = await fetch(`${API}/api/llm/sentiment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      const data = await res.json().catch(() => ({}));
      if (res.ok && data && Array.isArray(data.teams)) {
        setSentimentResult({ summary: data.summary || '', teams: data.teams });
      } else {
        const msg = typeof data?.detail === 'string' ? data.detail : 'Sentiment analysis failed.';
        setError(msg);
        setTimeout(() => setError(null), 5000);
      }
    } catch (e) {
      clearTimeout(timeoutId);
      const isTimeout = e instanceof Error && e.name === 'AbortError';
      setError(isTimeout ? 'Sentiment analysis timed out. Try a shorter text or try again.' : 'Could not reach API for sentiment analysis.');
      setTimeout(() => setError(null), 5000);
    } finally {
      setSentimentLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-ncaa-dark/70">Loading bracket…</p>
      </div>
    );
  }

  if (error && !bracket) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4">
        <p className="text-red-600 mb-4">{error}</p>
        <p className="text-sm text-ncaa-dark/70">
          Run the backend and train the model: in <code className="bg-black/10 px-1 rounded">backend</code>, run
          <code className="block mt-2 bg-black/10 px-2 py-1 rounded text-xs">python train_model.py</code>
          then <code className="block mt-1 bg-black/10 px-2 py-1 rounded text-xs">uvicorn main:app --reload</code>
        </p>
      </div>
    );
  }

  return (
    <main className="min-h-screen pb-24 flex">
      <div className="flex-1 min-w-0 flex flex-col">
      <header className="sticky top-0 z-10 bg-ncaa-blue text-white px-4 py-3 shadow flex items-center justify-between">
        <a href="/" className="font-display text-xl md:text-2xl font-bold hover:underline">
          2026 Bracket
        </a>
        <button
          type="button"
          onClick={fillWithAI}
          disabled={filling || !bracket || isOnCooldown}
          title={isOnCooldown ? cooldownLabel ?? 'Wait for cooldown' : undefined}
          className="absolute left-1/2 -translate-x-1/2 bg-ncaa-orange hover:bg-ncaa-orange/90 disabled:opacity-50 disabled:cursor-not-allowed font-display font-semibold px-6 py-2.5 rounded-lg text-base shadow-lg"
        >
          {filling ? 'Filling…' : cooldownLabel ?? 'Fill with AI'}
        </button>
        {isOnCooldown && (
          <button
            type="button"
            onClick={clearCooldown}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-white/90 hover:text-white text-sm underline"
          >
            Reset
          </button>
        )}
        <div className="w-20" />
      </header>

      {error && (
        <div className="bg-red-100 text-red-800 px-4 py-2 text-center text-sm font-medium flex items-center justify-center gap-2">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} className="underline">Dismiss</button>
        </div>
      )}
      {filled?.champion && !error && (
        <div className="bg-ncaa-orange/15 text-ncaa-dark px-4 py-2 text-center font-display font-semibold">
          Champion: {filled.champion}
        </div>
      )}

      {/* Preferences and Scoring above the bracket */}
      <div className="px-4 py-2 space-y-2 border-b border-ncaa-dark/10 bg-white/80">
        <details className="group" open>
          <summary className="font-display font-semibold text-ncaa-blue cursor-pointer list-none flex items-center gap-2">
            <span className="group-open:rotate-90 transition">▶</span>
            Preferences (scale model features; 1 = default)
          </summary>
          <p className="mt-2 pl-5 text-xs text-ncaa-dark/70">
            Higher = weight that feature more. Upsets &gt; 1 = more random outcomes.
          </p>
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4 pl-5">
            {[
              { key: 'seed_weight', label: 'Seed' },
              { key: 'efficiency_weight', label: 'Adj EM' },
              { key: 'offense_weight', label: 'Offense' },
              { key: 'defense_weight', label: 'Defense' },
              { key: 'tempo_weight', label: 'Tempo' },
              { key: 'upset_tendency', label: 'Upsets' },
            ].map(({ key, label }) => (
              <label key={key} className="text-sm">
                <span className="block text-ncaa-dark/70 text-xs mb-0.5">{label}</span>
                <input
                  type="range"
                  min={PREFERENCE_MIN}
                  max={PREFERENCE_MAX}
                  step={PREFERENCE_STEP}
                  value={(preferences as Record<string, number>)[key] ?? 1}
                  onChange={(e) =>
                    setPreferences((p) => ({ ...p, [key]: +e.target.value }))
                  }
                  className="w-full"
                />
                <span className="text-xs text-ncaa-dark/60">
                  {((preferences as Record<string, number>)[key] ?? 1).toFixed(1)}
                </span>
              </label>
            ))}
            <div className="col-span-full mt-2">
              <label className="inline-flex items-center gap-2 cursor-pointer text-xs text-ncaa-dark/80">
                <input
                  type="checkbox"
                  checked={deterministicFill}
                  onChange={(e) => setDeterministicFill(e.target.checked)}
                  className="rounded"
                />
                <span>
                  Disable randomness (always pick higher probability instead of sampling outcomes).
                </span>
              </label>
            </div>
          </div>
        </details>
        <details className="group">
          <summary className="font-display font-semibold text-ncaa-blue cursor-pointer list-none flex items-center gap-2">
            <span className="group-open:rotate-90 transition">▶</span>
            Influence bracket with a prompt
          </summary>
          <p className="mt-2 pl-5 text-xs text-ncaa-dark/70">
            Describe how you want the AI to pick (e.g. &quot;more upsets&quot;, &quot;trust the 1 seeds&quot;). Used when you click Fill with AI. Prompts gently bias the model and sampling, so brackets will not perfectly follow your text.
          </p>
          <div className="mt-2 pl-5">
            <textarea
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              placeholder="e.g. I want more upsets / trust the 1 seeds"
              rows={2}
              className="w-full rounded border border-ncaa-dark/20 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ncaa-blue/50 resize-y"
            />
          </div>
        </details>
        <details className="group">
          <summary className="font-display font-semibold text-ncaa-blue cursor-pointer list-none flex items-center gap-2">
            <span className="group-open:rotate-90 transition">▶</span>
            Sentiment from articles (Reddit, ESPN, etc.)
          </summary>
          <p className="mt-2 pl-5 text-xs text-ncaa-dark/70">
            Paste one or more articles or links for sentiment analysis. Put each article or link on its own line.
          </p>
          <div className="mt-2 pl-5 space-y-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={usePrecomputedSentiment}
                onChange={(e) => setUsePrecomputedSentiment(e.target.checked)}
                className="rounded"
              />
              <span className="text-xs text-ncaa-dark/70">Use precomputed sentiment (if available)</span>
            </label>
            <textarea
              value={sentimentText}
              onChange={(e) => setSentimentText(e.target.value)}
              placeholder="Paste one or more articles or links (one per line)"
              rows={3}
              className="w-full rounded border border-ncaa-dark/20 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ncaa-blue/50 resize-y"
              disabled={sentimentLoading}
            />
            <button
              type="button"
              onClick={analyzeSentiment}
              disabled={sentimentLoading || !sentimentText.trim()}
              className="font-display font-semibold px-4 py-2 rounded bg-ncaa-blue text-white text-sm disabled:opacity-50 hover:bg-ncaa-blue/90"
            >
              {sentimentLoading ? 'Analyzing…' : 'Analyze sentiment'}
            </button>
            {sentimentResult && (
              <div className="rounded border border-ncaa-dark/15 bg-ncaa-dark/[0.03] p-3 text-sm space-y-2">
                {sentimentResult.summary && (
                  <p className="text-ncaa-dark/80">{sentimentResult.summary}</p>
                )}
                {sentimentResult.teams.length > 0 && (
                  <ul className="flex flex-wrap gap-2">
                    {sentimentResult.teams.map((t) => (
                      <li key={t.name} className="bg-white px-2 py-0.5 rounded border border-ncaa-dark/10">
                        <span className="font-medium">{t.name}</span>{' '}
                        <span className={t.sentiment > 0 ? 'text-green-700' : t.sentiment < 0 ? 'text-red-700' : 'text-ncaa-dark/60'}>
                          {t.sentiment > 0 ? 'positive' : t.sentiment < 0 ? 'negative' : 'neutral'}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useSentimentWhenFilling}
                    onChange={(e) => setUseSentimentWhenFilling(e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-xs text-ncaa-dark/70">Use this sentiment when filling bracket</span>
                </label>
              </div>
            )}
          </div>
        </details>
        <details className="group">
          <summary className="font-display font-semibold text-ncaa-blue cursor-pointer list-none flex items-center gap-2">
            <span className="group-open:rotate-90 transition">▶</span>
            How bracket scoring works
          </summary>
          <div className="mt-2 pl-5 text-sm text-ncaa-dark/80 space-y-1">
            <p>Standard NCAA bracket scoring (when you compare to real results):</p>
            <ul className="list-disc pl-5">
              <li>Round of 64: 1 pt</li>
              <li>Round of 32: 2 pts</li>
              <li>Sweet 16: 4 pts</li>
              <li>Elite 8: 8 pts</li>
              <li>Final Four: 16 pts</li>
              <li>Championship: 32 pts</li>
            </ul>
            <p className="text-xs text-ncaa-dark/60">
              Use &quot;Score your bracket&quot; below once you have actual results.
            </p>
          </div>
        </details>
        {filled && (
          <details className="group">
            <summary className="font-display font-semibold text-ncaa-blue cursor-pointer list-none flex items-center gap-2">
              <span className="group-open:rotate-90 transition">▶</span>
              Score your bracket
            </summary>
            <div className="mt-3 pl-5">
              <ScoreBracketSection filled={filled} />
            </div>
          </details>
        )}
      </div>

      <div className="px-2 flex gap-2 items-center flex-wrap pt-2">
        <button
          type="button"
          onClick={() => setViewMode('full')}
          className={`px-3 py-1.5 rounded text-sm font-display font-semibold ${viewMode === 'full' ? 'bg-ncaa-blue text-white' : 'bg-ncaa-dark/10'}`}
        >
          Full bracket
        </button>
        <button
          type="button"
          onClick={() => setViewMode('list')}
          className={`px-3 py-1.5 rounded text-sm font-display font-semibold ${viewMode === 'list' ? 'bg-ncaa-blue text-white' : 'bg-ncaa-dark/10'}`}
        >
          By region
        </button>
      </div>

      {bracket && viewMode === 'full' && (
        <div className="px-2 py-2">
          <FullBracketView bracket={bracket} filled={filled} />
        </div>
      )}
      {bracket && viewMode === 'list' && (
        <BracketView bracket={bracket} filled={filled} />
      )}

      {bracketId && (
        <p className="px-4 text-xs text-ncaa-dark/60">
          Bracket ID: {bracketId} (save to reference this prediction)
        </p>
      )}

      {filled && (
        <div
          className={`fixed bottom-0 left-0 bg-white border-t border-ncaa-dark/10 p-4 safe-area-pb ${aiPanelOpen ? 'sm:right-96 right-0' : 'right-0'}`}
        >
          <ExportButtons filled={filled} bracket={bracket!} />
        </div>
      )}
      </div>

      {/* Right-side collapsible AI panel */}
      <div
        className={`border-l border-ncaa-dark/15 bg-white/95 flex flex-col transition-[width] duration-200 ${
          aiPanelOpen ? 'w-full sm:w-96' : 'w-12'
        }`}
      >
        {aiPanelOpen ? (
          <>
            <div className="flex items-center justify-between px-3 py-2 border-b border-ncaa-dark/10 bg-ncaa-blue text-white">
              <span className="font-display font-semibold text-sm">Ask AI</span>
              <button
                type="button"
                onClick={() => setAiPanelOpen(false)}
                className="p-1 rounded hover:bg-white/20 text-sm"
                aria-label="Close AI panel"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-auto p-3">
              <AIChatPanel filled={filled} sidebar />
            </div>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setAiPanelOpen(true)}
            className="w-full h-full min-h-[4rem] flex items-center justify-center font-display font-semibold text-ncaa-blue text-xs writing-mode-vertical hover:bg-ncaa-blue/10 transition-colors"
            style={{ writingMode: 'vertical-rl' }}
            aria-label="Open AI chat"
          >
            Ask AI
          </button>
        )}
      </div>
    </main>
  );
}
