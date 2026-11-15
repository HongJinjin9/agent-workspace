// 分镜数据类型（shots.json 契约）
export type SpaceId = 'A' | 'B' | 'C' | 'D' | 'E';
export type CamPreset = 'sheet_macro' | 'sheet' | 'desk_wide' | 'three_papers' | 'calc' | 'room_wide' | 'wall_in' | 'curve' | 'bars' | 'tags_low' | 'tags_high' | 'tags_walk' | 'panels' | 'lot' | 'lot_close' | 'dusk_wide' | 'empty';
export type Motion = 'push' | 'pull' | 'lateral' | 'rise' | 'still';
export interface Shot {
  id: string; n: number; start: number; end: number; dur: number; seg: string;
  space: SpaceId; cam: CamPreset; motion: Motion;
  h3: string | null; h3mode: 'fill' | 'pip' | 'bg' | 'none';
  in?: number;
  headline: string; sub: string | null;
}
export interface Cue { id: string; start: number; end: number; text: string; }
