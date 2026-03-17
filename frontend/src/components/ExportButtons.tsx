'use client';

import type { BracketTemplate, FilledBracket } from '@/types/bracket';

export function ExportButtons({
  filled,
  bracket,
}: {
  filled: FilledBracket;
  bracket: BracketTemplate;
}) {
  const exportJson = () => {
    const payload = {
      exportedAt: new Date().toISOString(),
      bracketTemplate: { regions: bracket.regions },
      predictions: filled.predictions,
      regionWinners: filled.region_winners,
      champion: filled.champion,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `march-madness-bracket-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const printBracket = () => {
    const regionNames = ['East', 'Midwest', 'South', 'West'];
    const byRound = filled.predictions.reduce((acc, p) => {
      const r = p.round_of;
      if (!acc[r]) acc[r] = [];
      acc[r].push(p);
      return acc;
    }, {} as Record<number, typeof filled.predictions>);
    const roundLabels: Record<number, string> = { 64: 'Round of 64', 32: 'Round of 32', 16: 'Sweet 16', 8: 'Elite 8', 4: 'Final Four', 2: 'Championship' };
    let html = '';
    [64, 32, 16, 8, 4, 2].forEach((r) => {
      const list = byRound[r] || [];
      if (list.length === 0) return;
      html += `<div class="region"><h3>${roundLabels[r]}</h3><ul>`;
      list.forEach((p) => {
        html += `<li class="game">${p.team1} vs ${p.team2} → <span class="winner">${p.winner}</span> (${(p.team1_win_prob * 100).toFixed(0)}%)</li>`;
      });
      html += '</ul></div>';
    });
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write(`
      <!DOCTYPE html>
      <html>
        <head><title>March Madness Bracket</title>
        <style>
          body { font-family: system-ui,sans-serif; padding: 16px; color: #1a1a2e; }
          h1 { color: #0033A0; }
          .region { margin-bottom: 24px; }
          .game { margin: 8px 0; padding: 8px; border: 1px solid #ccc; border-radius: 8px; }
          .winner { font-weight: bold; }
        </style>
        </head>
        <body>
          <h1>March Madness Bracket</h1>
          <p>Exported ${new Date().toLocaleDateString()}</p>
          ${html}
          ${filled.champion ? `<p style="font-size:1.2em;margin-top:1em;"><strong>Champion: ${filled.champion}</strong></p>` : ''}
        </body>
      </html>
    `);
    win.document.close();
    win.print();
    win.close();
  };

  return (
    <div className="flex flex-wrap gap-3 justify-center">
      <button
        type="button"
        onClick={exportJson}
        className="bg-ncaa-blue hover:bg-ncaa-blue/90 text-white font-display font-semibold px-4 py-2 rounded-lg text-sm"
      >
        Export JSON
      </button>
      <button
        type="button"
        onClick={printBracket}
        className="bg-ncaa-dark/10 hover:bg-ncaa-dark/20 text-ncaa-dark font-display font-semibold px-4 py-2 rounded-lg text-sm"
      >
        Print / Save as PDF
      </button>
    </div>
  );
}
