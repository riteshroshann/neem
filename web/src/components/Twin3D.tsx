import { useEffect, useRef, useState } from "react";
import { heatRgb } from "../lib/palette";
import { ZONE_BUILDING, ZONE_GROUND } from "../lib/physics";
import type { Twin } from "../lib/twin";

interface Props {
  twin: Twin;
  cdsm: Float32Array;
  utci: Float32Array;
}

type Three = typeof import("three");
type Controls = typeof import("three/examples/jsm/controls/OrbitControls.js");

/**
 * The school as a heightfield: ground coloured by feels-like heat, roofs in grey, crowns in
 * green. three.js is loaded on first use, so the planner page stays light until someone asks.
 */
export default function Twin3D({ twin, cdsm, utci }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const state = useRef<{
    three: Three;
    geometry: import("three").BufferGeometry;
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
        const width = el.clientWidth;
        const height = Math.round(width * 0.66);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(width, height);
        renderer.setClearColor(0xffffff);
        el.appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(40, width / height, 1, 5000);
        const span = Math.max(rows, cols) * px;
        camera.position.set(span * 0.55, span * 0.75, span * 0.75);
        const controls = new OrbitControls(camera, renderer.domElement);
        controls.target.set(0, 0, 0);
        controls.enableDamping = true;
        controls.maxPolarAngle = Math.PI * 0.47;

        // A plane with one vertex per cell; heights and colours are filled in by `paint`.
        const geometry = new THREE.PlaneGeometry(cols * px, rows * px, cols - 1, rows - 1);
        geometry.rotateX(-Math.PI / 2);
        geometry.setAttribute(
          "color",
          new THREE.BufferAttribute(new Float32Array(rows * cols * 3), 3),
        );
        const mesh = new THREE.Mesh(
          geometry,
          new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true }),
        );
        scene.add(mesh);
        scene.add(new THREE.HemisphereLight(0xffffff, 0xbbbbbb, 2.2));
        const sun = new THREE.DirectionalLight(0xffffff, 1.4);
        sun.position.set(-span, span * 2, span * 0.5);
        scene.add(sun);

        let frame = 0;
        const loop = () => {
          controls.update();
          renderer.render(scene, camera);
          frame = requestAnimationFrame(loop);
        };
        loop();
        state.current = {
          three: THREE,
          geometry,
          dispose: () => {
            cancelAnimationFrame(frame);
            controls.dispose();
            renderer.dispose();
            geometry.dispose();
            el.removeChild(renderer.domElement);
          },
        };
        paint();
      })
      .catch((e: unknown) => setError(String(e)));
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
    const { cdsm: canopy, utci: heat } = latest.current;
    const n = twin.summary.grid.rows * twin.summary.grid.cols;
    const pos = s.geometry.getAttribute("position");
    const col = s.geometry.getAttribute("color");
    let base = Number.POSITIVE_INFINITY;
    for (let i = 0; i < n; i++) base = Math.min(base, twin.dem[i] as number);
    for (let i = 0; i < n; i++) {
      const ground = (twin.dem[i] as number) - base;
      const roof = (twin.dsm[i] as number) - base;
      const crown = ground + (canopy[i] as number);
      pos.setY(i, Math.max(roof, crown));
      let rgb: [number, number, number];
      if (twin.zones[i] === ZONE_BUILDING || roof - ground > 2.5) rgb = [214, 214, 214];
      else if ((canopy[i] as number) > 0) rgb = [62, 112, 70];
      else {
        rgb = heatRgb(heat[i] as number);
        if (twin.zones[i] !== ZONE_GROUND) rgb = rgb.map((v) => v + (255 - v) * 0.45) as typeof rgb;
      }
      col.setXYZ(i, rgb[0] / 255, rgb[1] / 255, rgb[2] / 255);
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
    s.geometry.computeVertexNormals();
  }

  // Repaint when the design or the hour changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: paint reads props through a ref
  useEffect(() => {
    paint();
  }, [cdsm, utci]);

  if (error) return <p className="small muted">The 3D view needs WebGL: {error}</p>;
  return (
    <div className="twin3d">
      <div ref={host} />
      <p className="xs muted">
        Drag to orbit, scroll to zoom. Ground coloured by feels-like temperature; grey roofs, green
        crowns, including the trees you plant.
      </p>
    </div>
  );
}
