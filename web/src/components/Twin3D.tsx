import { useEffect, useRef, useState } from "react";
import type { BufferGeometry, PerspectiveCamera } from "three";
import type { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { heatRgb, MAP } from "../lib/palette";
import { ZONE_BUILDING, ZONE_GROUND } from "../lib/physics";
import type { Twin } from "../lib/twin";

interface Props {
  twin: Twin;
  cdsm: Float32Array;
  utci: Float32Array;
}

type Three = typeof import("three");
type Controls = typeof import("three/examples/jsm/controls/OrbitControls.js");
type Rgb = [number, number, number];

/** A colour token of the page as 0-255 sRGB, so the scene takes the page's own palette. */
function token(THREE: Three, el: Element, name: string): Rgb {
  const c = new THREE.Color(getComputedStyle(el).getPropertyValue(name).trim());
  const { r, g, b } = c.getRGB({ r: 0, g: 0, b: 0 }, THREE.SRGBColorSpace);
  return [r * 255, g * 255, b * 255];
}

/**
 * Look from the south-south-east, 45 degrees up, so walls show and the yard reads as a plan;
 * back off along that line until the whole grid fits, whatever the box's shape.
 */
function frame(
  THREE: Three,
  camera: PerspectiveCamera,
  controls: OrbitControls,
  width: number,
  depth: number,
) {
  const dir = new THREE.Vector3(0.3, 0.71, 0.64).normalize();
  const corners = [-1, 1].flatMap((sx) =>
    [-1, 1].map((sz) => new THREE.Vector3((sx * width) / 2, 0, (sz * depth) / 2)),
  );
  let dist = Math.max(width, depth);
  for (let k = 0; k < 5; k++) {
    camera.position.copy(dir).multiplyScalar(dist);
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld();
    const reach = Math.max(
      ...corners.map((c) => {
        const p = c.clone().project(camera);
        return Math.max(Math.abs(p.x), Math.abs(p.y));
      }),
    );
    dist *= reach / 0.94;
  }
  controls.target.set(0, 0, 0);
  controls.minDistance = dist * 0.3;
  controls.maxDistance = dist * 1.6;
  controls.update();
}

/**
 * The school as a heightfield: ground coloured by feels-like heat, roofs in grey, crowns in
 * green. three.js is loaded on first use, so the planner page stays light until someone asks.
 */
export default function Twin3D({ twin, cdsm, utci }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  const [ready, setReady] = useState(false);
  const state = useRef<{
    three: Three;
    geometry: BufferGeometry;
    paper: Rgb;
    crown: Rgb;
    redraw: () => void;
    dispose: () => void;
  } | null>(null);

  // Build the scene once per twin; paint reads the latest design through a ref.
  // biome-ignore lint/correctness/useExhaustiveDependencies: the scene is built once per twin
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      import("three") as Promise<Three>,
      import("three/examples/jsm/controls/OrbitControls.js") as Promise<Controls>,
    ])
      .then(([THREE, { OrbitControls }]) => {
        const el = host.current;
        if (cancelled || !el) return;
        const { rows, cols, pixel_size: px } = twin.summary.grid;
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        // the page's own night behind the model, as under the flat map
        renderer.setClearColor(getComputedStyle(el).getPropertyValue("--paper").trim());
        el.appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(40, 1, 1, 5000);
        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.maxPolarAngle = Math.PI * 0.47;

        // A plane with one vertex per cell; heights and colours are filled in by `paint`.
        const geometry = new THREE.PlaneGeometry(cols * px, rows * px, cols - 1, rows - 1);
        geometry.rotateX(-Math.PI / 2);
        geometry.setAttribute(
          "color",
          new THREE.BufferAttribute(new Float32Array(rows * cols * 3), 3),
        );
        const material = new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.frustumCulled = false; // heights change after the bounds are first measured
        scene.add(mesh);
        // light from the whole sky keeps flat ground at its palette colour; a high sun gives
        // the walls their form
        scene.add(new THREE.HemisphereLight(0xffffff, 0xbbbbbb, 2));
        const sun = new THREE.DirectionalLight(0xffffff, 1.2);
        sun.position.set(-1, 2, 0.5);
        scene.add(sun);

        let dirty = true;
        const resize = () => {
          const w = el.clientWidth;
          const h = el.clientHeight;
          if (!w || !h) return;
          renderer.setSize(w, h, false);
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
          dirty = true;
        };
        resize();
        frame(THREE, camera, controls, cols * px, rows * px);
        const ro = new ResizeObserver(resize);
        ro.observe(el);

        // draw only when the camera moves or the design changes, so an idle view costs nothing
        let raf = 0;
        const loop = () => {
          if (controls.update() || dirty) {
            renderer.render(scene, camera);
            dirty = false;
          }
          raf = requestAnimationFrame(loop);
        };
        state.current = {
          three: THREE,
          geometry,
          paper: token(THREE, el, "--paper"),
          crown: token(THREE, el, "--leaf"),
          redraw: () => {
            dirty = true;
          },
          dispose: () => {
            cancelAnimationFrame(raf);
            ro.disconnect();
            controls.dispose();
            renderer.dispose();
            geometry.dispose();
            material.dispose();
            el.removeChild(renderer.domElement);
          },
        };
        paint();
        loop();
        setReady(true);
      })
      .catch(() => setError(true));
    return () => {
      cancelled = true;
      state.current?.dispose();
      state.current = null;
    };
  }, [twin]);

  const latest = useRef({ cdsm, utci });
  latest.current = { cdsm, utci };

  function paint() {
    const s = state.current;
    if (!s) return;
    const { three: THREE, geometry, paper, crown } = s;
    const { cdsm: canopy, utci: heat } = latest.current;
    const n = twin.summary.grid.rows * twin.summary.grid.cols;
    const pos = geometry.getAttribute("position");
    const col = geometry.getAttribute("color");
    const color = new THREE.Color();
    // beyond the school wall colours sink into the night, exactly as the flat map's do
    const fade = (rgb: Rgb, k: number) =>
      rgb.map((v, j) => (paper[j] as number) + (v - (paper[j] as number)) * k) as Rgb;
    const outside = MAP.outsideAlpha / 255;
    let base = Number.POSITIVE_INFINITY;
    for (let i = 0; i < n; i++) base = Math.min(base, twin.dem[i] as number);
    for (let i = 0; i < n; i++) {
      const ground = (twin.dem[i] as number) - base;
      const roof = (twin.dsm[i] as number) - base;
      const tree = canopy[i] as number;
      const yard = twin.zones[i] === ZONE_GROUND;
      pos.setY(i, Math.max(roof, ground + tree));
      let rgb: Rgb;
      if (twin.zones[i] === ZONE_BUILDING) rgb = MAP.schoolRoof;
      else if (roof - ground > MAP.tallM) rgb = MAP.nearbyRoof;
      else if (tree > 0) rgb = yard ? crown : fade(crown, 0.5);
      else rgb = yard ? heatRgb(heat[i] as number) : fade(heatRgb(heat[i] as number), outside);
      // the palette is sRGB; vertex colours are linear
      color.setRGB(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, THREE.SRGBColorSpace);
      col.setXYZ(i, color.r, color.g, color.b);
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
    s.redraw();
  }

  // Repaint when the design or the hour changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: paint reads props through a ref
  useEffect(() => {
    paint();
  }, [cdsm, utci]);

  return (
    <div className="twin3d">
      <div className="twin3d-gl" ref={host} />
      {error ? (
        <p className="twin3d-msg small muted">
          The 3D view needs WebGL, which this browser didn't start. The map works without it.
        </p>
      ) : (
        !ready && <p className="twin3d-msg xs muted">Loading the 3D view…</p>
      )}
    </div>
  );
}
