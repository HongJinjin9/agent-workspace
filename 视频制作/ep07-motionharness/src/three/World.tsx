// ep07 3D 世界：一个连续空间五个区（A 评估工位 / B 数据墙 / C 价签森林 / D 二手车场 / E 收束空间）
// 全部程序化几何 + 灯光；所有动画只依赖 time（秒），确定性、可回退。
import * as THREE from 'three';
import { useMemo, useRef } from 'react';
import { useThree } from '@react-three/fiber';
import { THEME } from '../data/theme';
import { FACTS } from '../data/facts';
import { MAT } from './materials';
import { sheetTexture, skyTexture, tagTexture, panelTexture, plateTexture, textTexture } from './text-texture';
import { AREAS, CAM_PRESETS } from './pose';
import { poseForShot } from './camera-rig';
import { clamp, easeInOutCubic, easeOutCubic, easeOutQuint, lerp, progress, mulberry32 } from './math';
import type { Shot } from '../data/types';

const C = THEME.color;

// ---------------------------------------------------------------- camera
function CameraRig({ shot, localT }: { shot: Shot; localT: number }) {
  const { camera } = useThree();
  const pose = poseForShot(shot, localT, shot.n * 0.37);
  const cam = camera as THREE.PerspectiveCamera;
  cam.position.set(pose.pos[0], pose.pos[1], pose.pos[2]);
  cam.fov = pose.fov;
  cam.near = 0.04;
  cam.far = 260;
  cam.updateProjectionMatrix();
  cam.lookAt(pose.look[0], pose.look[1], pose.look[2]);
  return null;
}

// ---------------------------------------------------------------- room A / E
function Room({ time, shot, dim }: { time: number; shot: Shot; dim: number }) {
  const room = AREAS.A.room;
  return (
    <group>
      {/* 地面 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[room.w, room.d]} />
        <primitive object={MAT.floor} attach="material" />
      </mesh>
      {/* 后墙 / 左右墙 / 顶 */}
      <mesh position={[0, room.h / 2, -room.d / 2]}>
        <planeGeometry args={[room.w, room.h]} />
        <primitive object={MAT.wall} attach="material" />
      </mesh>
      <mesh position={[-room.w / 2, room.h / 2, 0]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[room.d, room.h]} />
        <primitive object={MAT.wall} attach="material" />
      </mesh>
      <mesh position={[room.w / 2, room.h / 2, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <planeGeometry args={[room.d, room.h]} />
        <primitive object={MAT.wall} attach="material" />
      </mesh>
      <mesh position={[0, room.h, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[room.w, room.d]} />
        <primitive object={MAT.metalDark} attach="material" />
      </mesh>
      {/* 顶光槽（自发光条） */}
      <mesh position={[0, room.h - 0.06, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.9, room.d * 0.72]} />
        <meshBasicMaterial color="#c9d6e4" transparent opacity={0.85 - dim * 0.7} toneMapped={false} />
      </mesh>
      {/* 评估台 */}
      <Desk time={time} shot={shot} />
      {/* 举升机 + 低多边形车（A 区右侧） */}
      <Lift time={time} shot={shot} />
    </group>
  );
}

function Desk({ time, shot }: { time: number; shot: Shot }) {
  const deskY = AREAS.A.deskY;
  const inPaperShot = shot.space === 'A';
  const sheetLift = shot.space === 'A' ? 0.002 + Math.sin(Math.min(time, 197) * 0.7) * 0.0008 : 0.002;
  return (
    <group position={[0, 0, 0]}>
      {/* 台面 */}
      <mesh position={[0, deskY, 0]}>
        <boxGeometry args={[2.35, 0.07, 1.25]} />
        <primitive object={MAT.metal} attach="material" />
      </mesh>
      {/* 桌脚 */}
      {[-1, 1].flatMap((sx) => [-1, 1].map((sz) => (
        <mesh key={`leg${sx}${sz}`} position={[sx * 1.02, deskY / 2 - 0.03, sz * 0.48]}>
          <boxGeometry args={[0.07, deskY, 0.07]} />
          <primitive object={MAT.metalDark} attach="material" />
        </mesh>
      )))}
      {/* 台灯（左后） */}
      <group position={[-0.92, deskY + 0.035, -0.42]}>
        <mesh position={[0, 0.03, 0]}><cylinderGeometry args={[0.11, 0.13, 0.06, 20]} /><primitive object={MAT.metalDark} attach="material" /></mesh>
        <mesh position={[0, 0.32, 0]}><cylinderGeometry args={[0.018, 0.022, 0.6, 12]} /><primitive object={MAT.metalLight} attach="material" /></mesh>
        <mesh position={[0, 0.66, 0.1]} rotation={[0.35, 0, 0]}>
          <cylinderGeometry args={[0.16, 0.055, 0.2, 24, 1, true]} />
          <meshStandardMaterial color={C.amber} emissive={new THREE.Color(C.amber)} emissiveIntensity={0.9} side={THREE.DoubleSide} roughness={0.4} />
        </mesh>
      </group>
      {/* 评估单 */}
      <group position={[0, deskY + 0.04 + sheetLift, 0.02]} rotation={[-Math.PI / 2, 0, 0]}>
        <mesh>
          <planeGeometry args={[0.62, 0.875, 1, 1]} />
          <meshStandardMaterial map={sheetTexture()} roughness={0.9} transparent={false} />
        </mesh>
      </group>
      {/* 印章（评估单右下） */}
      <Stamp time={time} />
      {/* 计算器（台面右前） */}
      <Calculator time={time} />
      {/* 三张纸 / 三本账（左右摊开的额外纸页） */}
      {inPaperShot && <Papers time={time} shot={shot} />}
    </group>
  );
}

function Papers({ time, shot }: { time: number; shot: Shot }) {
  const deskY = AREAS.A.deskY;
  const spread = easeOutCubic(progress(time, shot.start, shot.start + 0.8));
  const pages = [
    { pos: [-0.52, deskY + 0.042, 0.16], rot: -0.24, label: '账① 技术' },
    { pos: [0.52, deskY + 0.042, 0.2], rot: 0.22, label: '账② 价格' },
    { pos: [0.02, deskY + 0.044, 0.52], rot: 0.04, label: '账③ 电池' },
  ];
  return (
    <group>
      {pages.map((p, i) => (
        <group key={p.label} position={[p.pos[0] * spread, p.pos[1], p.pos[2]]} rotation={[-Math.PI / 2, p.rot, 0]}>
          <mesh>
            <planeGeometry args={[0.42, 0.6]} />
            <meshStandardMaterial color={i === 0 ? C.paper : C.paperShade} roughness={0.9} />
          </mesh>
          <mesh position={[0, -0.001, 0]}>
            <planeGeometry args={[0.34, 0.5]} />
            <meshBasicMaterial map={plateTexture(p.label, { w: 512, h: 720, fontSize: 54, font: THEME.font.serif, color: C.ink })} transparent />
          </mesh>
        </group>
      ))}
    </group>
  );
}

const STAMP_WINDOWS = [
  { start: 16.8, text: '重估' },
  { start: 40.5, text: '有异议' },
  { start: 131.3, text: '重新评估' },
  { start: 181.5, text: '落章' },
];

function Stamp({ time }: { time: number }) {
  const win = STAMP_WINDOWS.find((w) => time >= w.start - 0.9 && time < w.start + 1.9);
  if (!win) return null;
  const t = time - (win.start - 0.9);
  const drop = easeInOutCubic(clamp((t - 0.55) / 0.32));
  const y = lerp(1.42, AREAS.A.deskY + 0.13, drop);
  const flash = clamp(1 - Math.abs(t - 0.9) / 0.5);
  return (
    <group position={[0.3, y, 0.42]} rotation={[0, 0.35, 0]}>
      <mesh position={[0, 0.1, 0]}><cylinderGeometry args={[0.075, 0.085, 0.2, 20]} /><primitive object={MAT.metalDark} attach="material" /></mesh>
      <mesh position={[0, 0.25, 0]}><sphereGeometry args={[0.075, 16, 12]} /><primitive object={MAT.metalLight} attach="material" /></mesh>
      <mesh position={[0, 0, 0]} rotation={[0, 0.7, 0]}>
        <boxGeometry args={[0.19, 0.05, 0.19]} /><primitive object={MAT.metal} attach="material" />
      </mesh>
      {/* 印面 */}
      <mesh position={[0, -0.028, 0]} rotation={[-Math.PI / 2, 0, 0.3]}>
        <planeGeometry args={[0.16, 0.16]} />
        <meshBasicMaterial map={plateTexture(win.text, { w: 256, h: 256, fontSize: 84, font: THEME.font.serif, color: C.red })} transparent />
      </mesh>
      {flash > 0.05 && (
        <mesh position={[0, -0.03, 0]} rotation={[-Math.PI / 2, 0, 0.3]}>
          <planeGeometry args={[0.34 + (1 - flash) * 0.3, 0.34 + (1 - flash) * 0.3]} />
          <meshBasicMaterial color={C.red} transparent opacity={flash * 0.22} depthWrite={false} />
        </mesh>
      )}
    </group>
  );
}

function Calculator({ time }: { time: number }) {
  const deskY = AREAS.A.deskY;
  const screen = time < 36.6 ? '' : time < 38.5 ? '11 ÷ 3' : time < 145 ? '3.7' : time < 152 ? '20 − 9' : '11';
  const tex = useMemo(() => plateTexture(screen || ' ', { w: 256, h: 128, fontSize: 72, font: THEME.font.mono, color: '#7fd6a0', align: 'left' }), [screen]);
  return (
    <group position={[0.62, deskY + 0.035, 0.42]} rotation={[0, -0.28, 0]}>
      <mesh><boxGeometry args={[0.3, 0.05, 0.36]} /><primitive object={MAT.metalDark} attach="material" /></mesh>
      <mesh position={[0, 0.028, -0.1]}>
        <planeGeometry args={[0.22, 0.1]} /><meshBasicMaterial map={tex} transparent />
      </mesh>
      {/* 按键 */}
      {Array.from({ length: 12 }).map((_, i) => (
        <mesh key={i} position={[-0.09 + (i % 4) * 0.06, 0.03, 0.04 + Math.floor(i / 4) * 0.06]}>
          <boxGeometry args={[0.042, 0.018, 0.042]} />
          <meshStandardMaterial color={i % 5 === 0 ? C.amber : '#2c333b'} roughness={0.5} metalness={0.4} />
        </mesh>
      ))}
    </group>
  );
}

// ---------------------------------------------------------------- car asset
export function Car({ color = '#2b3644', position = [0, 0, 0] as [number, number, number], rotation = 0, scale = 1, wheels = false }) {
  return (
    <group position={position} rotation={[0, rotation, 0]} scale={scale}>
      {/* 车身 */}
      <mesh position={[0, 0.36, 0]} castShadow>
        <boxGeometry args={[1.9, 0.34, 0.78]} />
        <primitive object={MAT.carPaint(color)} attach="material" />
      </mesh>
      {/* 座舱 */}
      <mesh position={[0.05, 0.6, 0]}>
        <boxGeometry args={[1.05, 0.3, 0.7]} />
        <primitive object={MAT.carPaint(color)} attach="material" />
      </mesh>
      {/* 玻璃 */}
      <mesh position={[0.05, 0.61, 0.36]}>
        <planeGeometry args={[0.96, 0.24]} /><primitive object={MAT.glass} attach="material" />
      </mesh>
      <mesh position={[0.05, 0.61, -0.36]} rotation={[0, Math.PI, 0]}>
        <planeGeometry args={[0.96, 0.24]} /><primitive object={MAT.glass} attach="material" />
      </mesh>
      {/* 车轮 */}
      {[[-0.62, 0.31], [0.62, 0.31]].flatMap(([x]) => [0.4, -0.4].map((z) => (
        <mesh key={`w${x}${z}`} position={[x, 0.3, z]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.3, 0.3, 0.2, 18]} />
          <primitive object={MAT.rubber} attach="material" />
        </mesh>
      )))}
      {/* 电池包（底盘平板） */}
      <mesh position={[0, 0.14, 0]}>
        <boxGeometry args={[1.5, 0.08, 0.6]} />
        <meshStandardMaterial color={C.metalLight} roughness={0.3} metalness={0.9} />
      </mesh>
      {wheels && (
        <mesh position={[0, 0.3, 0.78]}>
          <planeGeometry args={[0.7, 0.18]} />
          <primitive object={MAT.amber} attach="material" />
        </mesh>
      )}
    </group>
  );
}

function Lift({ time, shot }: { time: number; shot: Shot }) {
  const nearLift = shot.space === 'A' && time > 79;
  const liftH = nearLift ? easeInOutCubic(progress(time, 83.4, 89)) * 1.05 : 0.6;
  return (
    <group position={[2.25, 0, 0.42]} rotation={[0, -0.35, 0]}>
      {/* 立柱 */}
      {[-1.05, 1.05].map((z) => (
        <mesh key={z} position={[0, 1.0, z]}>
          <boxGeometry args={[0.14, 2.0, 0.14]} /><primitive object={MAT.metalDark} attach="material" />
        </mesh>
      ))}
      {/* 平台 */}
      <group position={[0, liftH, 0]}>
        <mesh position={[0, 0.02, 0]}>
          <boxGeometry args={[2.25, 0.08, 2.0]} /><primitive object={MAT.metal} attach="material" />
        </mesh>
        <Car color="#38424f" position={[0, 0.06, 0]} scale={1} />
      </group>
    </group>
  );
}

// ---------------------------------------------------------------- B data wall
function DataWall({ time, shot }: { time: number; shot: Shot }) {
  const active = shot.space === 'B';
  const p = active ? progress(time, shot.start, shot.start + Math.min(2.2, shot.dur)) : 1;
  const grow = easeOutCubic(p);
  // 折旧曲线：从 50.6% 掉到 42.2% 再探底的三段管
  const curve = useMemo(() => {
    const pts = [
      new THREE.Vector3(8.5, 2.9, -1.7), new THREE.Vector3(8.5, 2.55, -1.0),
      new THREE.Vector3(8.5, 2.15, -0.2), new THREE.Vector3(8.5, 1.75, 0.6), new THREE.Vector3(8.5, 1.15, 1.55),
    ];
    const c = new THREE.CatmullRomCurve3(pts);
    return { geo: new THREE.TubeGeometry(c, 64, 0.028, 10, false), end: pts[pts.length - 1] };
  }, []);
  const bars = [
    { z: -1.9, h: FACTS.categories.largeSuv / 100 * 2.6, label: '50.6%', name: '中大型 SUV' },
    { z: -1.0, h: FACTS.categories.mpv / 100 * 2.6, label: '48.7%', name: 'MPV' },
    { z: -0.1, h: FACTS.categories.smallCar / 100 * 2.6, label: '48.3%', name: '小型车' },
  ];
  return (
    <group>
      {/* 地面延伸 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[9.4, -0.005, 0]}>
        <planeGeometry args={[7, 8]} /><primitive object={MAT.floor} attach="material" />
      </mesh>
      {/* 墙 */}
      <mesh position={[9.45, 2.1, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <planeGeometry args={[7.2, 4.4]} /><primitive object={MAT.wall} attach="material" />
      </mesh>
      {/* 墙面网格线 */}
      {Array.from({ length: 9 }).map((_, i) => (
        <mesh key={`gl${i}`} position={[9.42, 0.35 + i * 0.5, 0]} rotation={[0, -Math.PI / 2, 0]}>
          <planeGeometry args={[6.6, 0.006]} /><meshBasicMaterial color={C.metalLight} transparent opacity={0.28} />
        </mesh>
      ))}
      {/* 折旧曲线 */}
      <group>
        <mesh position={[0, 0, 0]}>
          <primitive object={curve.geo} attach="geometry" />
          <meshStandardMaterial color={C.amber} emissive={new THREE.Color(C.amber)} emissiveIntensity={0.55} roughness={0.4} />
        </mesh>
        <mesh position={[curve.end.x, curve.end.y, curve.end.z]}>
          <sphereGeometry args={[0.06, 16, 12]} /><primitive object={MAT.amber} attach="material" />
        </mesh>
        {/* 45.1 / 42.2 数字牌 */}
        <mesh position={[8.45, 3.15, -1.75]} rotation={[0, -Math.PI / 2, 0]}>
          <planeGeometry args={[1.5, 0.45]} />
          <meshBasicMaterial map={plateTexture('纯电 45.1%', { w: 640, h: 192, fontSize: 64, font: THEME.font.sans, color: C.paper })} transparent />
        </mesh>
        <mesh position={[8.45, 1.0, 1.62]} rotation={[0, -Math.PI / 2, 0]}>
          <planeGeometry args={[1.4, 0.42]} />
          <meshBasicMaterial map={plateTexture('插混 42.2%', { w: 600, h: 180, fontSize: 60, font: THEME.font.sans, color: C.amber })} transparent />
        </mesh>
      </group>
      {/* 三根品类柱 */}
      {bars.map((b, i) => {
        const h = Math.max(0.02, b.h * (active ? grow : 1));
        return (
          <group key={b.name} position={[8.92, 0, b.z]}>
            <mesh position={[0, h / 2, 0]}>
              <boxGeometry args={[0.42, h, 0.42]} />
              <meshStandardMaterial color={i === 0 ? C.amber : C.metalLight} metalness={0.6} roughness={0.35} emissive={i === 0 ? new THREE.Color(C.amber) : undefined} emissiveIntensity={i === 0 ? 0.28 : 0} />
            </mesh>
            <mesh position={[-0.12, h + 0.2, 0]} rotation={[0, -Math.PI / 2, 0]}>
              <planeGeometry args={[1.0, 0.3]} />
              <meshBasicMaterial map={plateTexture(b.label, { w: 512, h: 160, fontSize: 76, font: THEME.font.mono, color: i === 0 ? C.amber : C.paper })} transparent />
            </mesh>
            <mesh position={[-0.12, h - 0.12, 0.34]} rotation={[0, -Math.PI / 2, 0]}>
              <planeGeometry args={[1.0, 0.16]} />
              <meshBasicMaterial map={plateTexture(b.name, { w: 512, h: 96, fontSize: 42, font: THEME.font.sans, color: C.paper, alpha: 0.7 })} transparent />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

// ---------------------------------------------------------------- C tag forest
interface TagSpec { x: number; y: number; z: number; label: string; value: string; tone: 'paper' | 'amber' | 'red'; layer: number; sway: number; }
const TAG_SPECS: TagSpec[] = (() => {
  const rnd = mulberry32(7007);
  const out: TagSpec[] = [];
  const brands = [
    ['保时捷', '66.2%', 'amber'], ['雷克萨斯', '强', 'paper'], ['沃尔沃', '35.7%', 'red'], ['捷豹', '32.8%', 'red'], ['英菲尼迪', '29.1%', 'red'],
    ['本田', '49.8%', 'paper'], ['丰田', '49.4%', 'paper'], ['马自达', '49.1%', 'paper'], ['标致', '42.6%', 'red'], ['斯柯达', '42.1%', 'red'], ['福特', '42.4%', 'red'],
    ['传祺', '52.1%', 'amber'], ['坦克', '51.4%', 'amber'], ['领克', '47.9%', 'paper'], ['长安欧尚', '46.8%', 'paper'], ['极氪', '46.2%', 'paper'],
  ] as const;
  const layers = [1.35, 2.05, 2.75];
  brands.forEach((b, i) => {
    const layer = i % 3;
    const x = 12.4 + (i / brands.length) * 7.2 + rnd() * 0.5;
    const z = (layer - 1) * 1.15 + (rnd() - 0.5) * 0.5;
    out.push({ x, y: layers[layer] + rnd() * 0.12, z, label: b[0], value: b[1], tone: b[2], layer, sway: rnd() * Math.PI * 2 });
  });
  return out;
})();

function Tag({ spec, time, active }: { spec: TagSpec; time: number; active: number }) {
  const tex = useMemo(() => tagTexture(spec.label, spec.value, spec.tone), [spec]);
  const sway = Math.sin(time * 0.7 + spec.sway) * 0.05;
  const y = spec.y + sway * 0.15 + active * (spec.layer === 2 ? 0.35 : spec.layer === 1 ? 0.15 : 0);
  const rotY = Math.PI / 2 + Math.sin(time * 0.6 + spec.sway) * 0.18;
  return (
    <group position={[spec.x, y, spec.z]} rotation={[0, rotY, 0]}>
      {/* 吊线：从天花板 4.4m 垂到价签顶部 */}
      {(() => { const h = Math.max(0.05, 4.4 - y); return (
        <mesh position={[0, h / 2, 0]}>
          <cylinderGeometry args={[0.004, 0.004, h, 6]} />
          <meshBasicMaterial color="#8b8f96" transparent opacity={0.5} />
        </mesh>
      ); })()}
      <mesh>
        <planeGeometry args={[0.36, 0.54]} />
        <meshStandardMaterial map={tex} roughness={0.85} side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[0, 0, -0.002]}><planeGeometry args={[0.36, 0.54]} /><meshBasicMaterial map={tex} transparent opacity={0.01} /></mesh>
    </group>
  );
}

function TagForest({ time, shot }: { time: number; shot: Shot }) {
  const active = shot.space === 'C' ? Math.min(1, progress(time, shot.start, shot.start + 1.6)) : 0.6;
  const rise = shot.space === 'C' && shot.motion === 'rise';
  const panels = useMemo(() => ({
    one: panelTexture('2025-10 一年期榜单', ['1  小米 SU7', '2  问界 M9', '3  理想 L6', '4  比亚迪 汉', '5  特斯拉 Model Y', '6  小鹏 G6', '7  零跑 C11', '8  蔚来 ES6'], 0),
    three: panelTexture('2025-10 三年期榜单', ['1  保时捷 Cayenne', '2  雷克萨斯 ES', '3  丰田 汉兰达', '4  本田 CR-V', '5  马自达 CX-5', '6  大众 途昂', '7  别克 GL8', '8  理想 ONE'], 0),
  }), []);
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[16, 0, 0]}>
        <planeGeometry args={[10, 9]} /><primitive object={MAT.floor} attach="material" />
      </mesh>
      {/* 顶棚横梁 */}
      {Array.from({ length: 6 }).map((_, i) => (
        <mesh key={i} position={[12.5 + i * 1.55, 4.3, 0]}>
          <boxGeometry args={[0.08, 0.08, 8]} /><primitive object={MAT.metalDark} attach="material" />
        </mesh>
      ))}
      {/* 森林尽头深色背板 + 冷光条（保证纵深与轮廓） */}
      <mesh position={[21.6, 2.6, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <planeGeometry args={[11, 5.6]} /><meshBasicMaterial color="#0d1116" />
      </mesh>
      {[1.2, 2.4, 3.6].map((y) => (
        <mesh key={`strip${y}`} position={[21.55, y, 0]} rotation={[0, -Math.PI / 2, 0]}>
          <planeGeometry args={[10.4, 0.02]} /><meshBasicMaterial color="#9fb0c4" transparent opacity={0.22} toneMapped={false} />
        </mesh>
      ))}
      {TAG_SPECS.map((s, i) => <Tag key={i} spec={s} time={time} active={rise ? active : 0} />)}
      {/* 两座高台价签（S32） */}
      {[['中大型 SUV', '50.6%'], ['MPV', '48.7%']].map(([label, value], i) => (
        <group key={label} position={[14.2 + i * 2.4, 0, 1.5]} rotation={[0, Math.PI / 2, 0]}>
          <mesh position={[0, 0.9, 0]}><boxGeometry args={[0.5, 1.8, 0.5]} /><primitive object={MAT.metal} attach="material" /></mesh>
          <mesh position={[0, 2.0, 0]} rotation={[0, 0, 0]}>
            <planeGeometry args={[0.78, 1.0]} />
            <meshStandardMaterial map={tagTexture(label, value, 'amber', '保值率')} roughness={0.8} side={THREE.DoubleSide} />
          </mesh>
        </group>
      ))}
      {/* 榜单面板 */}
      <group position={[19.4, 2.0, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <mesh><planeGeometry args={[2.6, 1.7]} /><meshBasicMaterial map={panels.one} transparent /></mesh>
        <mesh position={[0, 0, -0.03]}><planeGeometry args={[2.75, 1.85]} /><primitive object={MAT.metalDark} attach="material" /></mesh>
      </group>
      <group position={[19.42, 2.0, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <mesh position={[0, 0, 0.01]}><planeGeometry args={[2.6, 1.7]} /><meshBasicMaterial map={panels.three} transparent opacity={0.0} /></mesh>
      </group>
    </group>
  );
}

// ---------------------------------------------------------------- D car lot
function CarLot({ time, shot }: { time: number; shot: Shot }) {
  const active = shot.space === 'D';
  const p = active ? progress(time, shot.start, shot.start + 2.2) : 1;
  const sky = useMemo(() => skyTexture(), []);
  const cars = [
    { x: -9.4, z: 1.1, color: '#2b3644', rot: 0.06 },
    { x: -11.2, z: 0.9, color: '#4a3b34', rot: -0.04 },
    { x: -13.0, z: 0.7, color: '#39434d', rot: 0.02 },
    { x: -14.8, z: 0.5, color: '#3d3226', rot: 0.08 },
    { x: -16.6, z: 0.3, color: '#2e3a3a', rot: -0.05 },
    { x: -10.3, z: -2.6, color: '#333d46', rot: 0.1 },
    { x: -12.2, z: -2.9, color: '#41352f', rot: -0.02 },
  ];
  return (
    <group>
      {/* 场地 */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-14, 0, 0]}>
        <planeGeometry args={[30, 34]} /><meshStandardMaterial color="#2a2622" roughness={0.9} metalness={0.1} />
      </mesh>
      {/* 黄昏天空背景板 */}
      <mesh position={[-30, 6.4, 0]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[52, 14]} /><meshBasicMaterial map={sky} toneMapped={false} />
      </mesh>
      {/* 车阵 */}
      {cars.map((car, i) => (
        <Car key={i} color={car.color} position={[car.x, 0, car.z]} rotation={car.rot} scale={1.02} />
      ))}
      {/* 路灯 */}
      {[-10, -14, -18].map((x, i) => (
        <group key={i} position={[x, 0, 2.6]}>
          <mesh position={[0, 2.2, 0]}><cylinderGeometry args={[0.04, 0.05, 4.4, 10]} /><primitive object={MAT.metalDark} attach="material" /></mesh>
          <mesh position={[0, 4.45, 0]}><sphereGeometry args={[0.12, 12, 10]} /><meshBasicMaterial color="#ffcf8a" toneMapped={false} /></mesh>
          <pointLight position={[0, 4.4, 0]} color="#ffb968" intensity={3.2} distance={9} decay={2} />
        </group>
      ))}
      {/* 黄昏主光 */}
      <directionalLight position={[-26, 4.5, 8]} color="#ffb877" intensity={2.2 * (active ? p : 0.8)} />
      {/* 地面价签（两张，S35/S48） */}
      {active && (
        <group position={[-12.6, 1.1, 2.9]} rotation={[0, 0.5, 0]}>
          <mesh><planeGeometry args={[0.5, 0.74]} /><meshStandardMaterial map={tagTexture('三年残值', '45.1%', 'amber', '市场定价')} side={THREE.DoubleSide} roughness={0.85} /></mesh>
          <mesh position={[0.62, -0.12, 0]}><planeGeometry args={[0.42, 0.62]} /><meshStandardMaterial map={tagTexture('落地价', '20 万', 'paper', '厂商定价')} side={THREE.DoubleSide} roughness={0.9} /></mesh>
        </group>
      )}
    </group>
  );
}

// ---------------------------------------------------------------- E beam / dust
function Beam({ time, shot }: { time: number; shot: Shot }) {
  const p = shot.space === 'E' ? progress(time, shot.start, shot.start + 1.4) : 0;
  if (p <= 0.01) return null;
  return (
    <group position={[0, 2.2, 0]}>
      <mesh rotation={[0, 0, 0]} position={[0, 1.0, 0]}>
        <cylinderGeometry args={[0.12, 0.95, 2.6, 28, 1, true]} />
        <meshBasicMaterial color="#dfe8f2" transparent opacity={0.06 * p} side={THREE.DoubleSide} depthWrite={false} toneMapped={false} />
      </mesh>
      <spotLight position={[0, 1.9, 0]} target-position={[0, -1.2, 0]} angle={0.42} penumbra={0.8} intensity={14 * p} color="#e8eef7" distance={9} decay={2} />
    </group>
  );
}

function Dust({ time }: { time: number }) {
  const geom = useMemo(() => {
    const rnd = mulberry32(4242);
    const count = 700;
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (rnd() - 0.5) * 7;
      pos[i * 3 + 1] = rnd() * 3.4;
      pos[i * 3 + 2] = (rnd() - 0.5) * 7;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return g;
  }, []);
  return (
    <points geometry={geom}>
      <pointsMaterial color="#cfd8e2" size={0.012} transparent opacity={0.35} depthWrite={false} sizeAttenuation />
    </points>
  );
}

// ---------------------------------------------------------------- world
export function World({ time, shot }: { time: number; shot: Shot }) {
  const localT = time - shot.start;
  const space = shot.space;
  const dim = space === 'E' ? clamp(progress(time, shot.start, shot.start + 3)) : 0;
  const inRoom = space === 'A' || space === 'E';
  return (
    <>
      <CameraRig shot={shot} localT={localT} />
      <fog attach="fog" args={[space === 'D' ? '#5a4530' : '#080a0d', space === 'D' ? 16 : 7, space === 'D' ? 48 : 20]} />
      {/* 灯光：冷白顶光 + 琥珀台灯 + 黄昏（车场） */}
      <ambientLight intensity={space === 'D' ? 0.18 : 0.22} color={space === 'D' ? '#c9a07a' : '#9fb0c4'} />
      <directionalLight position={[2.5, 4.6, 2.2]} intensity={space === 'D' ? 0.4 : 1.05 - dim * 0.5} color="#cfd8e6" />
      <pointLight position={[-0.92, 1.62, -0.32]} intensity={inRoom ? 1.0 - dim * 0.55 : 0.3} color="#ffb968" distance={4.2} decay={2} />
      {inRoom && <Room time={time} shot={shot} dim={dim} />}
      {space === 'B' && <DataWall time={time} shot={shot} />}
      {space === 'C' && <TagForest time={time} shot={shot} />}
      {space === 'D' && <CarLot time={time} shot={shot} />}
      {space === 'B' && <ItemHint label="数据墙" />}
      {(space === 'A' || space === 'E') && <Dust time={time} />}
      <Beam time={time} shot={shot} />
    </>
  );
}

function ItemHint({ label }: { label: string }) {
  return null;
}
