// Faction labels, colors and shapes. Colors are CSS variables (see site.css), validated for
// color-vision deficiency as a set of three; shape repeats the category so color is never alone.
export type Faction = 'moderate' | 'both' | 'progressive' | 'unflagged' | 'mixed-unclear';
export type Shape = 'circle' | 'square' | 'diamond' | 'ring';

export const FACTION: Record<Faction, { label: string; color: string; shape: Shape }> = {
  moderate: { label: 'Moderate', color: 'var(--moderate)', shape: 'circle' },
  both: { label: 'Both flags', color: 'var(--both)', shape: 'diamond' },
  progressive: { label: 'Progressive', color: 'var(--progressive)', shape: 'square' },
  unflagged: { label: 'No flag', color: 'var(--neutral)', shape: 'ring' },
  'mixed-unclear': { label: 'Mixed or unclear', color: 'var(--neutral)', shape: 'ring' },
};

export const HOUSE_ROWS: Faction[] = ['moderate', 'both', 'progressive', 'unflagged'];
