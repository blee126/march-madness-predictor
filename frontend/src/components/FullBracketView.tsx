'use client';

import { useMemo } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import type { BracketTemplate, FilledBracket, Prediction } from '@/types/bracket';

const REGION_COLORS: Record<string, string> = {
  South: 'bg-amber-400/90',
  East: 'bg-slate-400/90',
  West: 'bg-orange-500/90',
  Midwest: 'bg-teal-400/90',
};

const SLOT_WIDTH = 132;
const TEAM_HEIGHT = 22;

function GameSlot({
  team1,
  team2,
  seed1,
  seed2,
  winner,
  winProb,
  compact,
}: {
  team1: string;
  team2: string;
  seed1?: number;
  seed2?: number;
  winner?: string | null;
  winProb?: number;
  compact?: boolean;
}) {
  const h = compact ? TEAM_HEIGHT : TEAM_HEIGHT + 2;
  return (
    <div
      className="rounded-sm border border-ncaa-dark/25 bg-white overflow-hidden flex flex-col shadow"
      style={{ width: SLOT_WIDTH, minHeight: 2 * h }}
    >
      <div
        className={`px-1.5 py-0.5 text-[10px] flex items-center gap-1 ${
          winner === team1 ? 'bg-ncaa-blue/20 font-semibold' : 'bg-ncaa-cream'
        }`}
        style={{ minHeight: h }}
      >
        <span className="flex-shrink-0 w-5 h-4 rounded bg-amber-500 text-ncaa-dark font-bold flex items-center justify-center text-[9px]">
          {seed1 ?? '–'}
        </span>
        <span className="truncate">{team1}</span>
      </div>
      <div
        className={`px-1.5 py-0.5 text-[10px] flex items-center gap-1 border-t border-ncaa-dark/15 ${
          winner === team2 ? 'bg-ncaa-blue/20 font-semibold' : 'bg-white'
        }`}
        style={{ minHeight: h }}
      >
        <span className="flex-shrink-0 w-5 h-4 rounded bg-amber-500 text-ncaa-dark font-bold flex items-center justify-center text-[9px]">
          {seed2 ?? '–'}
        </span>
        <span className="truncate">{team2}</span>
      </div>
      {winner != null && (
        <div className="px-1.5 py-0.5 bg-ncaa-cream/80 text-[9px] text-ncaa-dark/80 border-t border-ncaa-dark/10">
          {winner}
          {winProb != null && ` (${(winProb * 100).toFixed(0)}%)`}
        </div>
      )}
    </div>
  );
}

function buildRoundsFromPredictions(filled: FilledBracket) {
  const byRound: Record<number, typeof filled.predictions> = {};
  for (const p of filled.predictions) {
    if (!byRound[p.round_of]) byRound[p.round_of] = [];
    byRound[p.round_of].push(p);
  }
  return byRound;
}

function buildR64FromBracket(bracket: BracketTemplate) {
  const byRegion: Record<number, { team1: string; team2: string; seed1: number; seed2: number }[]> = {};
  (bracket.regions ?? []).forEach((region, ri) => {
    byRegion[ri] = region.map((game) => {
      const [a, b] = game;
      return { team1: a.team, team2: b.team, seed1: a.seed, seed2: b.seed };
    });
  });
  return byRegion;
}

const PER_REGION: Record<number, number> = { 64: 8, 32: 4, 16: 2, 8: 1 };

/** One region's tree: R64 (8) → R32 (4) → R16 (2) → R8 (1). If reverse, columns order is R8→R16→R32→R64 so R64 is on the right. */
function RegionTree({
  regionName,
  regionIdx,
  r64Games,
  rounds,
  hasFilled,
  colorClass,
  reverse = false,
}: {
  regionName: string;
  regionIdx: number;
  r64Games: { team1: string; team2: string; seed1: number; seed2: number }[];
  rounds: Record<number, Prediction[]> | null;
  hasFilled: boolean;
  colorClass: string;
  reverse?: boolean;
}) {
  const roundKeys = (reverse ? [8, 16, 32, 64] : [64, 32, 16, 8]) as const;
  return (
    <div className="flex flex-col h-full">
      <div className={`font-display font-bold text-xs text-white px-2 py-1 rounded-t ${colorClass}`}>
        {regionName.toUpperCase()}
      </div>
      <div className="flex gap-1 flex-1 items-stretch p-1 bg-ncaa-dark/5 rounded-b">
        {roundKeys.map((r) => {
          const size = PER_REGION[r];
          const fullList = (hasFilled && rounds ? rounds[r] : []) ?? [];
          const list = fullList.slice(regionIdx * size, regionIdx * size + size);
          const regionR64 = r64Games;
          return (
            <div
              key={r}
              className="flex flex-col justify-around gap-0.5"
              style={{ minHeight: size * (2 * TEAM_HEIGHT + 6) }}
            >
              {r === 64
                ? regionR64.map((g, i) => {
                    const pred = list[i];
                    const winProb =
                      pred && pred.team1_win_prob != null
                        ? pred.winner === pred.team1
                          ? pred.team1_win_prob
                          : 1 - pred.team1_win_prob
                        : undefined;
                    return (
                      <GameSlot
                        key={i}
                        team1={g.team1}
                        team2={g.team2}
                        seed1={g.seed1}
                        seed2={g.seed2}
                        winner={pred?.winner}
                        winProb={winProb}
                        compact
                      />
                    );
                  })
                : list.map((p, i) => {
                    const winProb =
                      p.team1_win_prob != null
                        ? p.winner === p.team1
                          ? p.team1_win_prob
                          : 1 - p.team1_win_prob
                        : undefined;
                    return (
                      <GameSlot
                        key={i}
                        team1={p.team1}
                        team2={p.team2}
                        seed1={p.team1_seed}
                        seed2={p.team2_seed}
                        winner={p.winner}
                        winProb={winProb}
                        compact
                      />
                    );
                  })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function FullBracketView({
  bracket,
  filled,
}: {
  bracket: BracketTemplate;
  filled: FilledBracket | null;
}) {
  const hasFilled = filled != null && filled.predictions.length > 0;

  const { roundsByRound, r64ByRegion } = useMemo(() => {
    const r64ByRegion = buildR64FromBracket(bracket);
    if (!hasFilled || !filled) {
      return { roundsByRound: null, r64ByRegion };
    }
    const byRound = buildRoundsFromPredictions(filled);
    return { roundsByRound: byRound, r64ByRegion };
  }, [bracket, filled, hasFilled]);

  const centerPredictions = useMemo(() => {
    if (!hasFilled || !filled || !roundsByRound) return null;
    return {
      semi: roundsByRound[4] ?? [],
      final: roundsByRound[2] ?? [],
    };
  }, [hasFilled, filled, roundsByRound]);

  return (
    <div className="w-full h-[72vh] min-h-[420px] border-2 border-ncaa-blue/30 rounded-xl overflow-hidden bg-gradient-to-b from-ncaa-blue/5 to-ncaa-cream/50">
      <TransformWrapper
        initialScale={hasFilled ? 0.4 : 0.55}
        minScale={0.2}
        maxScale={1.8}
        centerOnInit
        limitToBounds={false}
      >
        <TransformComponent
          wrapperStyle={{ width: '100%', height: '100%' }}
          contentStyle={{ width: '100%', height: '100%', minHeight: '100%' }}
        >
          <div className="p-3 inline-block min-w-full">
            <div className="flex items-stretch gap-2 justify-center">
              {/* Left: South (top) + West (bottom) */}
              <div className="flex flex-col gap-2 w-[min-content]">
                <RegionTree
                  regionName="South"
                  regionIdx={2}
                  r64Games={r64ByRegion[2] ?? []}
                  rounds={roundsByRound}
                  hasFilled={hasFilled}
                  colorClass={REGION_COLORS.South}
                />
                <RegionTree
                  regionName="West"
                  regionIdx={3}
                  r64Games={r64ByRegion[3] ?? []}
                  rounds={roundsByRound}
                  hasFilled={hasFilled}
                  colorClass={REGION_COLORS.West}
                />
              </div>

              {/* Center: Final Four + Championship + Champion */}
              <div className="flex flex-col justify-center gap-3 px-2 min-w-[140px] bg-ncaa-blue/10 rounded-lg border border-ncaa-blue/20">
                <div className="font-display font-bold text-ncaa-blue text-xs text-center">FINAL FOUR</div>
                {centerPredictions?.semi?.map((p, i) => {
                  const winProb =
                    p.team1_win_prob != null
                      ? p.winner === p.team1
                        ? p.team1_win_prob
                        : 1 - p.team1_win_prob
                      : undefined;
                  return (
                    <GameSlot
                      key={i}
                      team1={p.team1}
                      team2={p.team2}
                      seed1={p.team1_seed}
                      seed2={p.team2_seed}
                      winner={p.winner}
                      winProb={winProb}
                    />
                  );
                })}
                {centerPredictions?.final?.length ? (
                  <>
                    <div className="font-display font-bold text-ncaa-blue text-xs text-center mt-1">
                      CHAMPIONSHIP
                    </div>
                    {centerPredictions.final.slice(0, 1).map((p, i) => {
                      const winProb =
                        p.team1_win_prob != null
                          ? p.winner === p.team1
                            ? p.team1_win_prob
                            : 1 - p.team1_win_prob
                          : undefined;
                      return (
                        <GameSlot
                          key={`final-${i}`}
                          team1={p.team1}
                          team2={p.team2}
                          seed1={p.team1_seed}
                          seed2={p.team2_seed}
                          winner={p.winner}
                          winProb={winProb}
                        />
                      );
                    })}
                    <div className="font-display font-bold text-ncaa-orange text-xs text-center">
                      NATIONAL CHAMPION
                    </div>
                    <div className="bg-ncaa-orange/20 border-2 border-ncaa-orange rounded-lg px-2 py-2 text-center font-display font-bold text-sm">
                      {filled?.champion ?? '—'}
                    </div>
                  </>
                ) : null}
              </div>

              {/* Right: East (top) + Midwest (bottom) — reversed so R64 is on the right */}
              <div className="flex flex-col gap-2 w-[min-content]">
                <RegionTree
                  regionName="East"
                  regionIdx={0}
                  r64Games={r64ByRegion[0] ?? []}
                  rounds={roundsByRound}
                  hasFilled={hasFilled}
                  colorClass={REGION_COLORS.East}
                  reverse
                />
                <RegionTree
                  regionName="Midwest"
                  regionIdx={1}
                  r64Games={r64ByRegion[1] ?? []}
                  rounds={roundsByRound}
                  hasFilled={hasFilled}
                  colorClass={REGION_COLORS.Midwest}
                  reverse
                />
              </div>
            </div>
          </div>
        </TransformComponent>
      </TransformWrapper>
      <p className="text-xs text-ncaa-dark/60 px-2 py-1 border-t border-ncaa-dark/10 bg-white/80">
        Scroll/pinch to zoom • Drag to pan • Fill with AI to see all rounds
      </p>
    </div>
  );
}
