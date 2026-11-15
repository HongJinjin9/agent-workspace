// 第 07 期事实/数字常量（唯一数据源，来自 2026-10 中国汽车流通协会保值率报告）
export const FACTS = {
  hook: { newPrice: 20, usedPrice: 9, diff: 11, years: 3, perYear: 3.7 }, // 万元
  overall: { bev: 45.1, phev: 42.2 },          // 三年保值率 %
  categories: { largeSuv: 50.6, mpv: 48.7, smallCar: 48.3 },
  contrast: { fuel: '50%+', japanese: '54%+', porsche: 66.2 }, // 2025-10 对照口径
  luxury: { porsche: 66.2, lexus: '强', volvo: 35.7, jaguar: 32.8, infiniti: 29.1 },
  jointVenture: { strong: '本田 / 丰田 / 马自达 近五成', weak: '标致 / 斯柯达 / 福特 <43%' },
  domestic: { leaders: '传祺 / 坦克 领跑', rising: '领克 / 长安欧尚 / 极氪 上涨' },
  threeBooks: ['技术', '价格', '电池'],
  techParams: ['800V', '5C 超充', '城区智驾'],
  warranty: '多数品牌 8 年或 12 万公里',
  report: { date: '2026.11.10', publisher: '中国汽车流通协会', title: '2026 年 10 月中国汽车保值率报告' },
  sources: [
    '数据：中国汽车流通协会《2026 年 10 月中国汽车保值率报告》（2026-11-10）',
    '对照：中国汽车流通协会《2025 年 10 月中国汽车保值率研究报告》',
    '转引：第一电动网 / ZOL 汽车 / 汽车之家车家号 公开报道',
  ],
  declarations: [
    '本片数据来自公开报告与公开报道',
    '本片为知识与观点内容，不构成购买建议',
    '本片画面与配音含 AI 辅助制作',
  ],
};
export const SEGMENTS = [
  { id: 'COLD', label: '冷开场', start: 1, end: 25.866 },
  { id: 'ACT1', label: '第一幕 · 立判', start: 26.116, end: 54.919 },
  { id: 'ACT2', label: '第二幕 · 验证', start: 55.169, end: 106.166 },
  { id: 'ACT3', label: '第三幕 · 改判', start: 106.416, end: 154.541 },
  { id: 'ACT4', label: '第四幕 · 再判', start: 154.791, end: 184.585 },
  { id: 'CLOSE', label: '收束', start: 184.835, end: 197.923 },
];
