'use client';

import { useState } from 'react';
import type { FilledBracket } from '@/types/bracket';

const API = process.env.NEXT_PUBLIC_API_URL || '';
const ROUND_LABELS: Record<number, string> = {
  64: 'Round of 64',
  32: 'Round of 32',
  16: 'Sweet 16',
  8: 'Elite 8',
  4: 'Final Four',
  2: 'Championship',
};

const EXAMPLE_ACTUAL = [
  { round_of: 64, team1: 'Duke', team2: 'North Dakota St', winner: 'Duke' },
  { round_of: 64, team1: 'VCU', team2: 'UCF', winner: 'UCF' },
];

export function ScoreBracketSection({ filled }: { filled: FilledBracket }) {
  const [jsonInput, setJsonInput] = useState('');
  const [result, setResult] = useState<{
    total_score: number;
    max_possible: number;
    by_round: Record<
      number,
      { correct: number; total: number; points_earned: number }
    >;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const scoreBracket = async () => {
    setError(null);
    setResult(null);
    let actual: { round_of: number; team1: string; team2: string; winner: string }[];
    try {
      const parsed = JSON.parse(jsonInput);
      actual = Array.isArray(parsed) ? parsed : parsed.actual_results ?? [];
    } catch {
      setError('Invalid JSON. Paste an array of { round_of, team1, team2, winner }.');
      return;
    }
    if (!actual.length) {
      setError('No actual results in the JSON.');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/score-bracket`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          predictions: filled.predictions.map((p) => ({
            round_of: p.round_of,
            team1: p.team1,
            team2: p.team2,
            winner: p.winner,
          })),
          actual_results: actual,
        }),
      });
      if (!res.ok) throw new Error('Scoring failed');
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const loadFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const text = String(reader.result);
        setJsonInput(text);
        setError(null);
      } catch {
        setError('Could not read file.');
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  return (
    <div className="space-y-2">
      <p className="text-sm text-ncaa-dark/80">
        Paste actual game results as JSON (array of{' '}
        <code className="bg-black/10 px-1 rounded text-xs">
          &#123; &quot;round_of&quot;: 64, &quot;team1&quot;: &quot;...&quot;, &quot;team2&quot;: &quot;...&quot;, &quot;winner&quot;: &quot;...&quot; &#125;
        </code>
        ) or load a .json file. Team names must match your bracket.
      </p>
      <label className="inline-block text-sm text-ncaa-blue font-semibold cursor-pointer underline">
        Load from file
        <input type="file" accept=".json,application/json" onChange={loadFile} className="hidden" />
      </label>
      <textarea
        className="w-full h-24 p-2 text-sm font-mono border border-ncaa-dark/20 rounded bg-white"
        placeholder={JSON.stringify(EXAMPLE_ACTUAL, null, 2)}
        value={jsonInput}
        onChange={(e) => setJsonInput(e.target.value)}
      />
      <button
        type="button"
        onClick={scoreBracket}
        disabled={loading || !jsonInput.trim()}
        className="bg-ncaa-blue text-white font-display font-semibold px-4 py-2 rounded-lg text-sm disabled:opacity-50"
      >
        {loading ? 'Scoring…' : 'Score my bracket'}
      </button>
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
      {result && (
        <div className="border border-ncaa-dark/15 rounded-lg p-3 bg-white space-y-2">
          <p className="font-display font-bold text-ncaa-blue">
            Total: {result.total_score} / {result.max_possible} pts
          </p>
          <ul className="text-sm space-y-1">
            {[64, 32, 16, 8, 4, 2].map((r) => {
              const d = result.by_round[r];
              if (!d) return null;
              return (
                <li key={r}>
                  {ROUND_LABELS[r]}: {d.correct}/{d.total} correct → {d.points_earned} pts
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
