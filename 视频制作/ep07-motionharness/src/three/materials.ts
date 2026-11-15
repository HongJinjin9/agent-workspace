// 程序化材质：纸 / 车漆 / 金属 / 玻璃 / 墨 / 发光
import * as THREE from 'three';
import { THEME } from '../data/theme';

const C = THEME.color;

export const MAT = {
  paper: new THREE.MeshStandardMaterial({ color: C.paper, roughness: 0.86, metalness: 0.0 }),
  paperDark: new THREE.MeshStandardMaterial({ color: C.paperShade, roughness: 0.9 }),
  ink: new THREE.MeshStandardMaterial({ color: C.ink, roughness: 0.7 }),
  metal: new THREE.MeshStandardMaterial({ color: C.metal, roughness: 0.38, metalness: 0.85 }),
  metalDark: new THREE.MeshStandardMaterial({ color: C.metalDark, roughness: 0.45, metalness: 0.8 }),
  metalLight: new THREE.MeshStandardMaterial({ color: C.metalLight, roughness: 0.3, metalness: 0.9 }),
  rubber: new THREE.MeshStandardMaterial({ color: '#14161a', roughness: 0.95 }),
  glass: new THREE.MeshStandardMaterial({ color: '#a9c2d8', roughness: 0.12, metalness: 0.1, transparent: true, opacity: 0.35 }),
  amber: new THREE.MeshStandardMaterial({ color: C.amber, roughness: 0.42, metalness: 0.25 }),
  red: new THREE.MeshStandardMaterial({ color: C.red, roughness: 0.6 }),
  floor: new THREE.MeshStandardMaterial({ color: '#20252b', roughness: 0.55, metalness: 0.35 }),
  wall: new THREE.MeshStandardMaterial({ color: '#151a20', roughness: 0.9, metalness: 0.05 }),
  carPaint: (color: string) => new THREE.MeshStandardMaterial({ color, roughness: 0.22, metalness: 0.65 }),
  emissive: (color: string, intensity = 1.6) => new THREE.MeshStandardMaterial({ color, emissive: new THREE.Color(color), emissiveIntensity: intensity, roughness: 0.4 }),
  glow: (color: string) => new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9, toneMapped: false }),
};
