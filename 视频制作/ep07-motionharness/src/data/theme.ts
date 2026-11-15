// 第 07 期视觉主题（3D + DOM 共用；唯一视觉常量源）
export const THEME = {
  color: {
    bg: '#0b0e11',        // 冷灰底
    bgDeep: '#07090b',
    paper: '#e9e4d8',     // 纸白
    paperShade: '#d6cfc0',
    ink: '#1b1a17',       // 墨
    inkSoft: '#4a463d',
    amber: '#d9a441',     // 琥珀价签
    amberSoft: '#e7c887',
    red: '#b3392e',       // 批注红
    redDeep: '#7d231b',
    metal: '#3a424c',     // 金属灰
    metalDark: '#232930',
    metalLight: '#6b7682',
    glass: '#8fa3b8',
    cool: '#8fa3b8',
    line: 'rgba(233,228,216,0.22)',
    lineStrong: 'rgba(233,228,216,0.45)',
  },
  font: {
    serif: '"Noto Serif CJK SC","Noto Serif SC",serif',
    sans: '"Noto Sans CJK SC","Noto Sans SC",sans-serif',
    mono: '"DejaVu Sans Mono","Noto Sans Mono",monospace',
  },
  letterbox: 132,
  size: { h1: 108, h2: 72, quote: 54, body: 34, label: 24, caption: 24, sub: 46, num: 180 },
  // 六段时间（先用场景设计值；TTS 实测后由 Lead/audio-narration 回填）
  segments: [
    { id: 'COLD', label: '冷开场', start: 1, end: 25.866 },
    { id: 'ACT1', label: '第一幕·立判', start: 26.1156, end: 54.919 },
    { id: 'ACT2', label: '第二幕·验证', start: 55.1689, end: 106.166 },
    { id: 'ACT3', label: '第三幕·改判', start: 106.4165, end: 154.541 },
    { id: 'ACT4', label: '第四幕·再判', start: 154.7909, end: 184.585 },
    { id: 'CLOSE', label: '收束', start: 184.8352, end: 197.923 },
  ],
};
