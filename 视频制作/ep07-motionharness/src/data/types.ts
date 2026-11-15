// 分镜数据类型（v2：motion-graphics 主视觉 + H3 强关联插入）
export type SpaceId = 'A' | 'B' | 'C' | 'D' | 'E';
export type ShotKind = 'data' | 'h3' | 'split' | 'end';
export type CamPreset = 'sheet_macro' | 'sheet' | 'desk_wide' | 'three_papers' | 'calc' | 'room_wide' | 'wall_in' | 'curve' | 'bars' | 'tags_low' | 'tags_high' | 'tags_walk' | 'panels' | 'lot' | 'lot_close' | 'dusk_wide' | 'empty';
export type Motion = 'push' | 'pull' | 'lateral' | 'rise' | 'still' | 'dolly' | 'slow' | 'pan';
export type Treatment = 'push_in' | 'push_out' | 'pan_l' | 'pan_r' | 'punch_in' | 'mirror' | 'panel' | 'fill';
export interface Shot {
  id: string; n: number; start: number; end: number; dur: number; seg: string;
  kind: ShotKind;
  block?: string | null;      // data/split/end：图形块名
  clip?: string | null;       // h3/split：H3 素材名
  treat?: Treatment | null;   // h3/split：素材运动处理
  headline: string; sub: string | null;
  space: SpaceId | null;      // 3D backdrop 区域
  cam: CamPreset | null;      // 3D 机位预设
  spaceMotion: Motion | null; // 3D 相机运动
  motion?: Motion | null;    // 兼容 World 的相机运动字段
  in?: number;               // H3 素材起点（可选）
}
export interface Cue { id: string; start: number; end: number; text: string; }
