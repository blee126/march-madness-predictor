export interface TeamSlot {
  id: string;
  team: string;
  seed: number;
}

export interface BracketGame {
  0: TeamSlot;
  1: TeamSlot;
}

export interface BracketRegion {
  [gameIndex: number]: [TeamSlot, TeamSlot];
}

export interface BracketTemplate {
  regions: [TeamSlot, TeamSlot][][]; // regions[regionIdx] = array of 8 games
  finalfour?: unknown[];
}

export interface Prediction {
  region_index: number | null;
  round_of: number;
  team1: string;
  team2: string;
  team1_seed?: number;
  team2_seed?: number;
  team1_id?: string;
  team2_id?: string;
  winner: string;
  winner_id?: string;
  team1_win_prob: number;
}

export interface FilledBracket {
  predictions: Prediction[];
  region_winners: TeamSlot[];
  champion: string | null;
}
