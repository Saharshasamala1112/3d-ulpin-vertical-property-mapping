import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { SceneUnit } from '../../types/geometry';
import {
  applyOrbitDelta,
  applyZoomDelta,
  computeSceneFocus,
  groundHeight,
  initialSpherical,
  safeDimension,
  type SceneFocus,
  type Spherical,
} from './orbit';
import { floorColor } from './viewer-colors';

/**
 * Theme-aware scene colours. Passed in as plain hex because three.js
 * materials cannot read CSS custom properties from the document.
 */
const SCENE_PALETTE = {
  light: {
    background: '#f1f5f9',
    grid: '#cbd5e1',
    edge: '#0f172a',
    selection: '#1a56db',
    selectionEdge: '#0a0a0a',
  },
  dark: {
    background: '#0a0a0a',
    grid: '#334155',
    edge: '#e2e8f0',
    selection: '#3b82f6',
    selectionEdge: '#ffffff',
  },
} as const;

export type ScenePalette = keyof typeof SCENE_PALETTE;

interface UnitBoxProps {
  unit: SceneUnit;
  color: string;
  selected: boolean;
  dimmed: boolean;
  edgeColor: string;
  selectionEdge: string;
  onSelect: (unitId: string) => void;
}

function UnitBox({ unit, color, selected, dimmed, edgeColor, selectionEdge, onSelect }: UnitBoxProps) {
  const [hovered, setHovered] = useState(false);
  const { centroid, dimensions } = unit.geometry;

  const size = useMemo(
    () => [safeDimension(dimensions.x), safeDimension(dimensions.y), safeDimension(dimensions.z)] as const,
    [dimensions.x, dimensions.y, dimensions.z],
  );

  const boxGeometry = useMemo(() => new THREE.BoxGeometry(size[0], size[1], size[2]), [size]);
  const edgesGeometry = useMemo(() => new THREE.EdgesGeometry(boxGeometry), [boxGeometry]);

  useEffect(() => {
    return () => {
      boxGeometry.dispose();
      edgesGeometry.dispose();
    };
  }, [boxGeometry, edgesGeometry]);

  const opacity = selected ? 0.85 : dimmed ? 0.08 : hovered ? 0.6 : 0.35;

  return (
    <group position={[centroid.x, centroid.y, centroid.z]}>
      <mesh
        geometry={boxGeometry}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(unit.id);
        }}
        onPointerOver={(event) => {
          event.stopPropagation();
          setHovered(true);
        }}
        onPointerOut={() => setHovered(false)}
      >
        <meshStandardMaterial color={color} transparent opacity={opacity} roughness={0.65} metalness={0.05} />
      </mesh>
      <lineSegments geometry={edgesGeometry}>
        <lineBasicMaterial
          color={selected ? selectionEdge : edgeColor}
          transparent
          opacity={selected ? 1 : dimmed ? 0.12 : hovered ? 0.9 : 0.45}
        />
      </lineSegments>
    </group>
  );
}

interface SceneGridProps {
  center: { x: number; y: number };
  radius: number;
  height: number;
  color: string;
}

/** Reference grid on the ground plane, drawn in the Z-up frame. */
function SceneGrid({ center, radius, height, color }: SceneGridProps) {
  const geometry = useMemo(() => {
    const divisions = 10;
    const minX = center.x - radius;
    const maxX = center.x + radius;
    const minY = center.y - radius;
    const maxY = center.y + radius;
    const stepX = ((maxX - minX) / divisions) * 5;
    const stepY = ((maxY - minY) / divisions) * 5;
    const positions: number[] = [];

    for (let x = minX; x <= maxX + 1e-9; x += stepX) {
      positions.push(x, minY, height, x, maxY, height);
    }
    for (let y = minY; y <= maxY + 1e-9; y += stepY) {
      positions.push(minX, y, height, maxX, y, height);
    }

    const buffer = new THREE.BufferGeometry();
    buffer.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    return buffer;
  }, [center.x, center.y, radius, height]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial color={color} transparent opacity={0.55} />
    </lineSegments>
  );
}

interface OrbitRigProps {
  focus: SceneFocus;
}

/**
 * Minimal orbit / pan / zoom camera rig.
 *
 * Hand-rolled rather than pulled from `@react-three/drei` to keep the viewer
 * chunk small and dependency count low, and so the up-axis can be pinned to Z
 * consistently with the data.
 */
function OrbitRig({ focus }: OrbitRigProps) {
  const camera = useThree((state) => state.camera) as THREE.PerspectiveCamera;
  const gl = useThree((state) => state.gl);

  const spherical = useRef<Spherical>(initialSpherical(focus.radius));
  const target = useRef(new THREE.Vector3(focus.center.x, focus.center.y, focus.center.z));
  const mode = useRef<'orbit' | 'pan' | null>(null);
  const previous = useRef({ x: 0, y: 0 });

  useEffect(() => {
    target.current.set(focus.center.x, focus.center.y, focus.center.z);
    spherical.current = initialSpherical(focus.radius);
    camera.up.set(0, 0, 1);
    camera.near = Math.max(focus.radius / 500, 0.01);
    camera.far = focus.radius * 100;
    camera.updateProjectionMatrix();
  }, [focus, camera]);

  useEffect(() => {
    const element = gl.domElement;
    const minDistance = Math.max(focus.radius * 0.05, 0.1);
    const maxDistance = focus.radius * 12;

    const onPointerDown = (event: PointerEvent) => {
      mode.current = event.shiftKey || event.button === 1 || event.button === 2 ? 'pan' : 'orbit';
      previous.current = { x: event.clientX, y: event.clientY };
    };

    const onPointerMove = (event: PointerEvent) => {
      if (!mode.current) return;
      const deltaX = event.clientX - previous.current.x;
      const deltaY = event.clientY - previous.current.y;
      previous.current = { x: event.clientX, y: event.clientY };

      if (mode.current === 'orbit') {
        spherical.current = applyOrbitDelta(spherical.current, deltaX, deltaY);
        return;
      }

      // Pan across the camera's screen plane, scaled so the drag tracks the cursor.
      const scale = (spherical.current.radius * 2 * Math.PI) / element.clientHeight;
      const right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0);
      const up = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
      target.current.addScaledVector(right, -deltaX * scale);
      target.current.addScaledVector(up, deltaY * scale);
    };

    const onPointerUp = () => {
      mode.current = null;
    };

    const onPointerLeave = () => {
      mode.current = null;
    };

    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      spherical.current = applyZoomDelta(spherical.current, event.deltaY, minDistance, maxDistance);
    };

    const onContextMenu = (event: MouseEvent) => event.preventDefault();

    element.addEventListener('pointerdown', onPointerDown);
    element.addEventListener('pointermove', onPointerMove);
    element.addEventListener('pointerup', onPointerUp);
    element.addEventListener('pointerleave', onPointerLeave);
    element.addEventListener('contextmenu', onContextMenu);
    element.addEventListener('wheel', onWheel, { passive: false });

    return () => {
      element.removeEventListener('pointerdown', onPointerDown);
      element.removeEventListener('pointermove', onPointerMove);
      element.removeEventListener('pointerup', onPointerUp);
      element.removeEventListener('pointerleave', onPointerLeave);
      element.removeEventListener('contextmenu', onContextMenu);
      element.removeEventListener('wheel', onWheel);
    };
  }, [gl, camera, focus.radius]);

  useFrame(() => {
    const state = spherical.current;
    const offset = new THREE.Vector3().setFromSpherical(new THREE.Spherical(state.radius, state.phi, state.theta));
    camera.position.copy(target.current).add(offset);
    camera.up.set(0, 0, 1);
    camera.lookAt(target.current);
  });

  return null;
}

interface SceneProps {
  units: SceneUnit[];
  selectedId: string | null;
  palette: ScenePalette;
  onSelect: (unitId: string | null) => void;
}

function Scene({ units, selectedId, palette, onSelect }: SceneProps) {
  const colors = SCENE_PALETTE[palette];
  const focus = useMemo(() => computeSceneFocus(units), [units]);
  const height = useMemo(() => groundHeight(units), [units]);

  const colorForFloor = useCallback(
    (floorId: string) => {
      const index = units.findIndex((unit) => unit.floor.id === floorId);
      return floorColor(index === -1 ? 0 : index);
    },
    [units],
  );

  return (
    <>
      <color attach="background" args={[colors.background]} />
      <OrbitRig focus={focus} />
      <SceneGrid center={focus.center} radius={focus.radius} height={height} color={colors.grid} />
      <ambientLight intensity={0.75} />
      <directionalLight position={[1, 1, 1.5]} intensity={1.1} />
      <directionalLight position={[-1, -1, 0.5]} intensity={0.35} />
      {units.map((unit) => (
        <UnitBox
          key={unit.id}
          unit={unit}
          color={colorForFloor(unit.floor.id)}
          selected={unit.id === selectedId}
          dimmed={selectedId !== null && unit.id !== selectedId}
          edgeColor={colors.edge}
          selectionEdge={colors.selectionEdge}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

export interface GeometryViewerProps {
  units: SceneUnit[];
  selectedId: string | null;
  palette: ScenePalette;
  onSelect: (unitId: string | null) => void;
}

/**
 * Default export so the page can `lazy()` this module into its own chunk and
 * keep three.js out of the initial bundle.
 */
export default function GeometryViewer({ units, selectedId, palette, onSelect }: GeometryViewerProps) {
  return (
    <Canvas
      data-testid="geometry-canvas"
      camera={{ fov: 50, near: 0.1, far: 1000, position: [10, 10, 10] }}
      onPointerMissed={() => onSelect(null)}
      style={{ width: '100%', height: '100%', display: 'block' }}
    >
      <Scene units={units} selectedId={selectedId} palette={palette} onSelect={onSelect} />
    </Canvas>
  );
}
