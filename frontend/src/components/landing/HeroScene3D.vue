<script setup>
// Real-time 3D diorama for the landing page: a farm fire whose smoke drifts
// into a city, watched by an orbiting satellite. Built from primitives, so
// there are no model files or licences involved.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  // "Smog vision": 0 = clear air; higher AQI thickens real 3D fog.
  aqi: { type: Number, default: 0 },
})

const host = ref(null)
const failed = ref(false)
let api = null
let unmounted = false

onMounted(async () => {
  try {
    const built = await buildScene(host.value)
    // Three.js loads asynchronously: if the page was left meanwhile, tear the
    // scene down at once instead of leaving a WebGL context running forever.
    if (unmounted) {
      built.cleanup()
      return
    }
    api = built
    api.setSmog(props.aqi)
  } catch (err) {
    console.warn('3D scene unavailable:', err)
    failed.value = true
  }
})

watch(() => props.aqi, (v) => api?.setSmog(v))

onBeforeUnmount(() => {
  unmounted = true
  api?.cleanup()
})

async function buildScene(el) {
  const THREE = await import('three')
  const { RoundedBoxGeometry } = await import('three/examples/jsm/geometries/RoundedBoxGeometry.js')

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  el.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  scene.fog = new THREE.FogExp2(0xdfe8f5, 0)
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100)
  camera.position.set(9, 7.2, 11)
  camera.lookAt(0, 0.6, 0)

  // ---------- lights ----------
  scene.add(new THREE.HemisphereLight(0xdfeaff, 0xffe2c8, 1.25))
  const sun = new THREE.DirectionalLight(0xffffff, 2.2)
  sun.position.set(6, 10, 5)
  sun.castShadow = true
  sun.shadow.mapSize.set(1024, 1024)
  sun.shadow.camera.left = -7
  sun.shadow.camera.right = 7
  sun.shadow.camera.top = 7
  sun.shadow.camera.bottom = -7
  sun.shadow.radius = 4
  scene.add(sun)
  const rim = new THREE.DirectionalLight(0x9cc9ff, 0.8)
  rim.position.set(-6, 4, -6)
  scene.add(rim)

  // ---------- materials (glossy "toy" plastic) ----------
  const glossy = (color, extra = {}) => new THREE.MeshPhysicalMaterial({
    color, roughness: 0.35, clearcoat: 0.7, clearcoatRoughness: 0.25, ...extra,
  })
  const M = {
    grass: glossy(0xbfe8c4, { roughness: 0.5, clearcoat: 0.4 }),
    soil: glossy(0xe8b98c),
    soilDark: glossy(0xc98f5f),
    road: glossy(0xc9d2e3, { roughness: 0.6 }),
    roadLine: glossy(0xffffff),
    navy: glossy(0x233a7a),
    navyLight: glossy(0x3a5bb5),
    orange: glossy(0xff8a3d),
    white: glossy(0xffffff),
    sky: glossy(0x9cc9ff),
    window: glossy(0xffd76a, { emissive: 0xffc23d, emissiveIntensity: 0.35 }),
    wheat: glossy(0xf2c66d),
    field: glossy(0x9bd48b),
    furrow: glossy(0xd9a066),
    leaf: glossy(0x5fc27a),
    trunk: glossy(0xb07a4f),
    panel: glossy(0x2b4a9e, { metalness: 0.3 }),
    metal: glossy(0xd8dde8, { metalness: 0.6, roughness: 0.3 }),
    cloud: glossy(0xffffff, { roughness: 0.6, clearcoat: 0.2 }),
  }

  const disposables = [renderer, ...Object.values(M)]
  const keep = (geo) => { disposables.push(geo); return geo }
  const mesh = (geo, mat, { x = 0, y = 0, z = 0, cast = true, receive = false } = {}) => {
    const m = new THREE.Mesh(keep(geo), mat)
    m.position.set(x, y, z)
    m.castShadow = cast
    m.receiveShadow = receive
    return m
  }

  const world = new THREE.Group()
  scene.add(world)

  // ---------- island base ----------
  // layered like a toy diorama: grass on top, soil underneath
  world.add(mesh(new THREE.CylinderGeometry(4.35, 4.1, 0.9, 64), M.soilDark, { y: -0.62, cast: false }))
  world.add(mesh(new THREE.CylinderGeometry(4.55, 4.4, 0.35, 64), M.soil, { y: -0.2, cast: false, receive: true }))
  world.add(mesh(new THREE.CylinderGeometry(4.6, 4.6, 0.14, 64), M.grass, { y: 0, cast: false, receive: true }))

  // road between the farm and the city
  const road = mesh(new RoundedBoxGeometry(0.75, 0.04, 8.2, 2, 0.02), M.road, { x: 0.05, y: 0.08, z: 0.3, cast: false, receive: true })
  road.rotation.y = -0.35
  world.add(road)
  for (let i = -3; i <= 3; i++) {
    const dash = mesh(new THREE.BoxGeometry(0.06, 0.02, 0.45), M.roadLine, { x: 0.05 + Math.sin(-0.35) * i * 1.1, y: 0.11, z: 0.3 + Math.cos(-0.35) * i * 1.1, cast: false })
    dash.rotation.y = -0.35
    world.add(dash)
  }

  // ---------- farm (left/back) with wheat stripes ----------
  const farm = new THREE.Group()
  farm.position.set(-2.1, 0.06, -0.6)
  farm.add(mesh(new RoundedBoxGeometry(3.1, 0.12, 2.6, 2, 0.05), M.field, { receive: true }))
  for (let i = 0; i < 6; i++) {
    const row = mesh(new RoundedBoxGeometry(2.7, 0.16, 0.22, 2, 0.06), i % 2 ? M.wheat : M.furrow, { y: 0.1, z: -1.0 + i * 0.4, receive: true })
    farm.add(row)
  }
  world.add(farm)

  // ---------- fire on the farm ----------
  const fire = new THREE.Group()
  fire.position.set(-2.6, 0.2, -0.2)
  // Flame tongues: stretched spheres, so it reads as fire rather than a cone.
  const flameMats = [
    glossy(0xff5a1f, { emissive: 0xff3d00, emissiveIntensity: 0.9, clearcoat: 0.3 }),
    glossy(0xff9a2e, { emissive: 0xff7a00, emissiveIntensity: 0.9, clearcoat: 0.3 }),
    glossy(0xffe066, { emissive: 0xffc400, emissiveIntensity: 1.0, clearcoat: 0.3 }),
  ]
  disposables.push(...flameMats)
  const flameGeo = keep(new THREE.SphereGeometry(0.2, 20, 16))
  const flames = [
    // x, z, height, width, material
    [0, 0, 1.9, 1.25, 0], [-0.22, 0.12, 1.3, 0.9, 0], [0.22, -0.08, 1.45, 0.95, 0],
    [0.02, 0.05, 1.35, 0.85, 1], [-0.1, -0.1, 0.95, 0.65, 1], [0.12, 0.12, 1.0, 0.7, 1],
    [0, 0.02, 0.7, 0.5, 2],
  ].map(([x, z, h, w, m]) => {
    const f = new THREE.Mesh(flameGeo, flameMats[m])
    f.position.set(x, 0.2 * h, z)
    f.scale.set(w, h, w)
    f.userData = { h, w, phase: Math.random() * 6 }
    fire.add(f)
    return f
  })
  // little logs of burning stubble
  for (const r of [0.4, -0.5, 1.4]) {
    const log = mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.55, 8), M.trunk, { y: 0.03 })
    log.rotation.set(Math.PI / 2, 0, r)
    fire.add(log)
  }
  // embers rising
  const EMBERS = 10
  const emberMat = new THREE.MeshBasicMaterial({ color: 0xffb347 })
  disposables.push(emberMat)
  const embers = new THREE.InstancedMesh(keep(new THREE.SphereGeometry(0.035, 6, 6)), emberMat, EMBERS)
  fire.add(embers)
  const emberSeeds = Array.from({ length: EMBERS }, () => ({ o: Math.random(), x: (Math.random() - 0.5) * 0.5, z: (Math.random() - 0.5) * 0.5 }))
  const fireLight = new THREE.PointLight(0xff7a2a, 3, 4)
  fireLight.position.set(0, 0.6, 0)
  fire.add(fireLight)
  world.add(fire)

  // ---------- city (right/front) ----------
  const city = new THREE.Group()
  city.position.set(1.7, 0.06, 0.5)
  const buildings = [
    // x, z, w, d, h, material
    [-0.6, -0.9, 0.8, 0.8, 2.4, M.navy],
    [0.4, -1.0, 0.7, 0.7, 1.7, M.white],
    [1.3, -0.5, 0.7, 0.9, 2.9, M.navyLight],
    [-0.1, 0.1, 0.8, 0.7, 1.3, M.orange],
    [1.1, 0.7, 0.8, 0.7, 1.9, M.white],
    [0.2, 1.1, 0.6, 0.6, 1.0, M.navy],
  ]
  for (const [x, z, w, d, h, mat] of buildings) {
    city.add(mesh(new RoundedBoxGeometry(w, h, d, 3, 0.1), mat, { x, y: h / 2, z, receive: true }))
    // a column of lit windows on the camera-facing side
    for (let fy = 0.35; fy < h - 0.25; fy += 0.42) {
      for (const fx of [-w / 4, w / 4]) {
        city.add(mesh(new RoundedBoxGeometry(0.16, 0.18, 0.04, 1, 0.02), M.window, { x: x + fx, y: fy, z: z + d / 2 + 0.01, cast: false }))
      }
    }
  }
  world.add(city)

  // ---------- school with a flag (front left) ----------
  const school = new THREE.Group()
  school.position.set(-0.4, 0.06, 2.3)
  school.add(mesh(new RoundedBoxGeometry(1.5, 0.75, 0.8, 3, 0.08), M.orange, { y: 0.38, receive: true }))
  const roof = mesh(new THREE.ConeGeometry(0.95, 0.5, 4), M.navy, { y: 1.0 })
  roof.rotation.y = Math.PI / 4
  roof.scale.set(1, 1, 0.55)
  school.add(roof)
  school.add(mesh(new RoundedBoxGeometry(0.28, 0.42, 0.04, 1, 0.03), M.white, { y: 0.22, z: 0.41 }))
  school.add(mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.9, 8), M.metal, { x: 0.55, y: 1.15 }))
  const flag = mesh(new THREE.BoxGeometry(0.32, 0.18, 0.02), M.sky, { x: 0.72, y: 1.48 })
  school.add(flag)
  world.add(school)

  // ---------- trees ----------
  const tree = (x, z, s = 1) => {
    const t = new THREE.Group()
    t.position.set(x, 0.06, z)
    t.scale.setScalar(s)
    t.add(mesh(new THREE.CylinderGeometry(0.06, 0.08, 0.35, 10), M.trunk, { y: 0.18 }))
    t.add(mesh(new THREE.SphereGeometry(0.3, 20, 16), M.leaf, { y: 0.55 }))
    return t
  }
  ;[[0.9, 2.6, 0.9], [-1.6, 2.0, 1], [3.4, -0.6, 0.8], [-0.6, -2.9, 0.9], [2.6, 2.4, 1.1]]
    .forEach(([x, z, s]) => world.add(tree(x, z, s)))

  // ---------- smoke: puffs travelling from the fire to the city ----------
  const path = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-2.6, 0.9, -0.2),
    new THREE.Vector3(-1.4, 2.0, -0.4),
    new THREE.Vector3(0.2, 2.5, 0.0),
    new THREE.Vector3(1.6, 2.6, 0.4),
    new THREE.Vector3(2.6, 3.2, 0.6),
  ])
  const PUFFS = 26
  const smokeMat = new THREE.MeshStandardMaterial({ color: 0xaeb5c4, roughness: 1, transparent: true, opacity: 0.55, depthWrite: false })
  disposables.push(smokeMat)
  const puffGeo = keep(new THREE.SphereGeometry(0.22, 16, 12))
  const smoke = new THREE.InstancedMesh(puffGeo, smokeMat, PUFFS)
  smoke.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
  world.add(smoke)
  const seeds = Array.from({ length: PUFFS }, (_, i) => ({ offset: i / PUFFS, wobble: Math.random() * Math.PI * 2 }))
  const tmp = new THREE.Object3D()

  // ---------- satellite on a tilted orbit ----------
  const orbit = new THREE.Group()
  orbit.rotation.set(0.35, 0, -0.25)
  const sat = new THREE.Group()
  sat.add(mesh(new RoundedBoxGeometry(0.42, 0.42, 0.6, 2, 0.06), M.white))
  sat.add(mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.2, 12), M.orange, { y: 0.3 }))
  for (const side of [-1, 1]) {
    const p = mesh(new RoundedBoxGeometry(0.9, 0.04, 0.42, 1, 0.02), M.panel, { x: side * 0.72 })
    sat.add(p)
    sat.add(mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.3, 6), M.metal, { x: side * 0.32 }))
  }
  const dish = mesh(new THREE.SphereGeometry(0.16, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), M.metal, { y: -0.28 })
  dish.rotation.x = Math.PI
  sat.add(dish)
  sat.scale.setScalar(0.85)
  orbit.add(sat)
  scene.add(orbit)

  // ---------- clouds ----------
  const cloud = (x, y, z, s) => {
    const c = new THREE.Group()
    c.position.set(x, y, z)
    c.scale.setScalar(s)
    ;[[0, 0, 0, 0.45], [0.45, -0.05, 0.05, 0.35], [-0.45, -0.08, 0, 0.32], [0.15, 0.22, 0, 0.32]]
      .forEach(([cx, cy, cz, r]) => c.add(mesh(new THREE.SphereGeometry(r, 20, 14), M.cloud, { x: cx, y: cy, z: cz })))
    return c
  }
  const clouds = [cloud(-3.2, 3.3, -2.4, 0.85), cloud(3.0, 3.6, -2.2, 0.7)]
  clouds.forEach((c) => scene.add(c))

  // ---------- sizing, interaction, loop ----------
  const resize = () => {
    const { clientWidth: w, clientHeight: h } = el
    if (!w || !h) return
    renderer.setSize(w, h, false)
    camera.aspect = w / h
    // Pull back on narrow screens so the whole island fits.
    camera.position.setLength(w / h < 1 ? 19 : 15.8)
    camera.updateProjectionMatrix()
  }
  const ro = new ResizeObserver(resize)
  ro.observe(el)
  resize()

  const pointer = { x: 0, y: 0 }
  const onPointer = (e) => {
    const r = el.getBoundingClientRect()
    pointer.x = ((e.clientX - r.left) / r.width - 0.5) * 2
    pointer.y = ((e.clientY - r.top) / r.height - 0.5) * 2
  }
  window.addEventListener('pointermove', onPointer)

  let visible = true
  const io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting })
  io.observe(el)

  const t0 = performance.now()
  let raf = 0

  const update = (t) => {
    // gentle turntable + mouse tilt
    world.rotation.y = Math.sin(t * 0.15) * 0.35 + pointer.x * 0.25
    world.rotation.x = pointer.y * 0.06

    // flicker: each tongue stretches and sways on its own rhythm
    for (const f of flames) {
      const { h, w, phase } = f.userData
      const k = 1 + Math.sin(t * 11 + phase) * 0.14 + Math.sin(t * 6.3 + phase * 2) * 0.08
      f.scale.set(w * (2 - k) * 0.95, h * k, w * (2 - k) * 0.95)
      f.position.y = 0.2 * h * k
      f.rotation.z = Math.sin(t * 4 + phase) * 0.12
    }
    fireLight.intensity = 2.4 + Math.sin(t * 17) * 0.6
    for (let i = 0; i < EMBERS; i++) {
      const e = emberSeeds[i]
      const u = (e.o + t * 0.45) % 1
      tmp.position.set(e.x + Math.sin(t * 3 + i) * 0.08, 0.2 + u * 1.4, e.z)
      tmp.scale.setScalar(1 - u)
      tmp.updateMatrix()
      embers.setMatrixAt(i, tmp.matrix)
    }
    embers.instanceMatrix.needsUpdate = true
    flag.rotation.y = Math.sin(t * 3) * 0.25

    // smoke puffs grow and fade along the path
    for (let i = 0; i < PUFFS; i++) {
      const s = seeds[i]
      const u = (s.offset + t * 0.06) % 1
      const p = path.getPointAt(u)
      tmp.position.set(p.x + Math.sin(t + s.wobble) * 0.12, p.y + Math.cos(t * 0.8 + s.wobble) * 0.08, p.z)
      // small near the fire, billowing out, then shrinking away as it disperses
      tmp.scale.setScalar(Math.sin(Math.PI * Math.min(u * 1.25, 1)) * (0.35 + u * 1.5) + 0.05)
      tmp.updateMatrix()
      smoke.setMatrixAt(i, tmp.matrix)
    }
    smoke.instanceMatrix.needsUpdate = true

    // satellite orbit + spin
    const a = t * 0.35
    sat.position.set(Math.cos(a) * 4.4, 3.4, Math.sin(a) * 4.4)
    sat.rotation.y = -a + Math.PI / 2

    clouds[0].position.x = -3.2 + Math.sin(t * 0.2) * 0.6
    clouds[1].position.x = 3.0 + Math.cos(t * 0.17) * 0.5
  }

  const loop = () => {
    raf = requestAnimationFrame(loop)
    if (!visible) return
    update((performance.now() - t0) / 1000)
    renderer.render(scene, camera)
  }

  if (reduced) {
    update(4) // a nice still frame
    renderer.render(scene, camera)
  } else {
    loop()
  }

  // ---------- smog vision ----------
  // Clear sky → yellow-grey smog → brown haze as AQI rises.
  const SMOG_STOPS = [
    [0, new THREE.Color(0xdfe8f5)],
    [200, new THREE.Color(0xd2cdb8)],
    [350, new THREE.Color(0xb8aa8c)],
    [500, new THREE.Color(0x9a8468)],
  ]
  const smogColor = new THREE.Color()
  const setSmog = (aqi) => {
    const a = Math.max(0, Math.min(aqi || 0, 500))
    let i = 0
    while (i < SMOG_STOPS.length - 2 && a > SMOG_STOPS[i + 1][0]) i++
    const [a0, c0] = SMOG_STOPS[i]
    const [a1, c1] = SMOG_STOPS[i + 1]
    smogColor.copy(c0).lerp(c1, (a - a0) / (a1 - a0))
    const k = a / 500
    // Exponential fog: at AQI 500 the city at ~16 units is mostly hidden.
    scene.fog.color.copy(smogColor)
    scene.fog.density = 0.095 * Math.pow(k, 0.85)
    renderer.setClearColor(smogColor, Math.min(k * 1.15, 0.92))
    sun.intensity = 2.2 * (1 - 0.45 * k)
    if (reduced || !visible) renderer.render(scene, camera)
  }

  const cleanup = () => {
    cancelAnimationFrame(raf)
    ro.disconnect()
    io.disconnect()
    window.removeEventListener('pointermove', onPointer)
    disposables.forEach((d) => d.dispose?.())
    renderer.domElement.remove()
  }

  return { cleanup, setSmog }
}
</script>

<template>
  <div ref="host" class="scene3d" role="img" aria-label="Animated 3D scene: smoke from a farm fire drifting into a city, watched by a satellite">
    <div v-if="failed" class="fallback" aria-hidden="true">
      <img src="/3d/fire.png" alt="" width="80" />
      <img src="/3d/fog.png" alt="" width="90" />
      <img src="/3d/cityscape.png" alt="" width="150" />
      <img src="/3d/satellite.png" alt="" width="70" />
    </div>
  </div>
</template>

<style scoped>
.scene3d {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 320px;
}

.scene3d :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

.fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
}
</style>
