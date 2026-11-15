// 3D 相机/场景布局常量：五区空间锚点与机位预设（单位≈米，Y 向上）
export const AREAS = {
  A: { label: '评估工位', deskY: 0.92, room: { w: 7.2, d: 7.6, h: 3.4 } },
  B: { label: '数据墙', wallX: 9.4, wallZ: 0, width: 6.4, height: 4.2, floorY: 0 },
  C: { label: '价签森林', x0: 12.0, x1: 20.5, floorY: 0, ceilingY: 4.6 },
  D: { label: '二手车场', x0: -22, x1: -7.0, floorY: 0, depth: 26 },
  E: { label: '收束空间', room: { w: 7.2, d: 7.6, h: 3.4 } },
};

// 机位预设：pos 相机位置；look 注视点；fov 垂直视场角（等效 24/35/50mm）
export const CAM_PRESETS = {
  sheet_macro: { pos: [0.0, 1.66, 1.42], look: [0.0, 0.96, 0.05], fov: 34 },
  sheet: { pos: [0.0, 1.82, 1.95], look: [0.0, 0.99, 0.02], fov: 36 },
  desk_wide: { pos: [0.0, 2.02, 3.25], look: [0.0, 1.06, 0.0], fov: 40 },
  three_papers: { pos: [0.0, 1.70, 2.05], look: [0.0, 0.97, 0.06], fov: 36 },
  calc: { pos: [0.78, 1.44, 1.52], look: [0.34, 0.97, 0.30], fov: 34 },
  room_wide: { pos: [0.0, 2.30, 4.55], look: [0.0, 1.10, 0.0], fov: 42 },
  wall_in: { pos: [3.9, 1.82, 2.7], look: [8.0, 1.70, 0.0], fov: 46 },
  curve: { pos: [5.6, 2.00, 2.7], look: [8.4, 2.10, 0.0], fov: 40 },
  bars: { pos: [5.2, 1.70, 2.5], look: [8.4, 1.75, -0.35], fov: 42 },
  tags_low: { pos: [10.8, 1.50, 3.1], look: [16.0, 1.88, 0.3], fov: 48 },
  tags_high: { pos: [12.4, 1.10, 2.5], look: [17.0, 2.55, 0.0], fov: 50 },
  tags_walk: { pos: [11.8, 1.70, 1.7], look: [18.0, 1.85, 0.0], fov: 46 },
  panels: { pos: [14.8, 1.90, 3.4], look: [19.0, 2.00, 0.0], fov: 42 },
  lot: { pos: [-7.0, 1.72, 8.6], look: [-15.0, 1.20, -1.0], fov: 38 },
  lot_close: { pos: [-10.6, 1.30, 5.6], look: [-16.0, 1.05, 0.0], fov: 35 },
  dusk_wide: { pos: [-5.6, 2.80, 11.0], look: [-16.0, 1.00, -2.0], fov: 44 },
  empty: { pos: [0.0, 2.80, 6.0], look: [0.0, 1.00, 0.0], fov: 44 },
};
