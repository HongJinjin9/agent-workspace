// 第 07 期 · MotionHarness Pro 入口：3D 评估室世界观 + DOM 合成
import { defineComposition, defineComponent, field, useTime } from '@motionharness/sdk';
import { Stage } from './Stage';
import { THEME } from './data/theme';

const Ep07 = defineComponent({
  id: 'ep07',
  parameters: {
    background: field.color({ label: '背景色', default: THEME.color.bg, animatable: true }),
    h3Opacity: field.number({ label: 'H3 素材不透明度', default: 1, min: 0, max: 1, step: 0.01, animatable: true }),
    grainStrength: field.number({ label: '颗粒强度', default: 1, min: 0, max: 2, step: 0.05 }),
    subtitles: field.boolean({ label: '显示字幕', default: true }),
  },
  component(values) {
    const time = useTime();
    return <Stage time={time} values={values} />;
  },
});

export default defineComposition({
  id: 'ep07',
  component: Ep07,
  width: 1920,
  height: 1080,
  fps: 24,
  duration: 208.9664,
});
