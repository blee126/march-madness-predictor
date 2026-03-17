'use client';

import { useState } from 'react';
import type { BracketTemplate, FilledBracket } from '@/types/bracket';

const REGION_NAMES = ['East', 'Midwest', 'South', 'West'];

function getWinnerForGame(
  filled: FilledBracket | null,
  regionIndex: number,
  roundOf: number,
  team1Id: string,
  team2Id: string
): string | null {
  if (!filled) return null;
  const p = filled.predictions.find(
    (x) =>
      x.region_index === regionIndex &&
      x.round_of === roundOf &&
      ((x.team1_id === team1Id && x.team2_id === team2Id) ||
        (x.team1_id === team2Id && x.team2_id === team1Id))
  );
  return p?.winner ?? null;
}

export function BracketView({
  bracket,
  filled,
}: {
  bracket: BracketTemplate;
  filled: FilledBracket | null;
}) {
  const [regionTab, setRegionTab] = useState(0);
  // Local manual winner overrides for Round of 64 (by region + game index).
  const [manualWinners, setManualWinners] = useState<Record<string, string>>({});
  const regions = bracket.regions ?? [];

  return (
    <div className="px-2 py-4 max-w-4xl mx-auto">
      {/* Tabs: mobile-friendly region switcher */}
      <div className="flex gap-1 mb-4 overflow-x-auto pb-2">
        {REGION_NAMES.map((name, i) => (
          <button
            key={name}
            type="button"
            onClick={() => setRegionTab(i)}
            className={`flex-shrink-0 px-4 py-2 rounded-lg font-display font-semibold text-sm ${
              regionTab === i
                ? 'bg-ncaa-blue text-white'
                : 'bg-ncaa-dark/10 text-ncaa-dark'
            }`}
          >
            {name}
          </button>
        ))}
      </div>

      {regions[regionTab] && (
        <div className="space-y-3">
          <h2 className="font-display font-semibold text-ncaa-blue text-lg">
            Round of 64
          </h2>
          {regions[regionTab].map((game, gameIdx) => {
            const [t1, t2] = game;
            const autoWinner = getWinnerForGame(
              filled,
              regionTab,
              64,
              t1.id,
              t2.id
            );
            const key = `${regionTab}-${gameIdx}`;
            const winner = manualWinners[key] ?? autoWinner;
            return (
              <div
                key={`${regionTab}-${gameIdx}`}
                className="border border-ncaa-dark/15 rounded-lg overflow-hidden bg-white shadow-sm"
              >
                <div className="bracket-cell flex flex-col">
                  <div
                    className={`flex items-center justify-between px-3 py-2 cursor-pointer ${
                      winner === t1.team ? 'bg-ncaa-blue/15 font-semibold' : ''
                    }`}
                    onClick={() =>
                      setManualWinners((prev) => ({ ...prev, [key]: t1.team }))
                    }
                  >
                    <span>
                      <span className="text-ncaa-dark/60 text-xs mr-2">{t1.seed}</span>
                      {t1.team}
                    </span>
                  </div>
                  <div
                    className={`flex items-center justify-between px-3 py-2 border-t border-ncaa-dark/10 cursor-pointer ${
                      winner === t2.team ? 'bg-ncaa-blue/15 font-semibold' : ''
                    }`}
                    onClick={() =>
                      setManualWinners((prev) => ({ ...prev, [key]: t2.team }))
                    }
                  >
                    <span>
                      <span className="text-ncaa-dark/60 text-xs mr-2">{t2.seed}</span>
                      {t2.team}
                    </span>
                  </div>
                </div>
                {filled && (
                  <div className="px-3 py-1 bg-ncaa-cream text-xs text-ncaa-dark/70">
                    Winner: {winner ?? '—'}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Summary: all region winners + champion on larger screens */}
      {filled && filled.region_winners?.length > 0 && (
        <section className="mt-8 pt-6 border-t border-ncaa-dark/10">
          <h3 className="font-display font-semibold text-ncaa-blue mb-2">
            Region winners
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {filled.region_winners.map((slot, i) => (
              <div
                key={i}
                className="bg-white border border-ncaa-dark/15 rounded px-3 py-2 text-sm"
              >
                <span className="text-ncaa-dark/60 text-xs">{REGION_NAMES[i]}</span>
                <p className="font-medium">{slot.team}</p>
              </div>
            ))}
          </div>
          {filled.champion && (
            <p className="mt-3 text-center font-display font-bold text-lg text-ncaa-orange">
              National champion: {filled.champion}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
