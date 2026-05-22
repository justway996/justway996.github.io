import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const canvas = document.querySelector("#viewport");
const positionReadout = document.querySelector("#positionReadout");
const poseReadout = document.querySelector("#poseReadout");
const reachReadout = document.querySelector("#reachReadout");
const gripReadout = document.querySelector("#gripReadout");
const jointControls = document.querySelector("#jointControls");
const resetBtn = document.querySelector("#resetBtn");
const randomBtn = document.querySelector("#randomBtn");
const demoBtn = document.querySelector("#demoBtn");

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x101216);
scene.fog = new THREE.Fog(0x101216, 16, 34);

const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
camera.position.set(7.6, 5.4, 8.4);

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(1.05, 2.15, 0);
controls.maxPolarAngle = Math.PI * 0.49;
controls.minDistance = 5;
controls.maxDistance = 18;

const materials = {
  base: new THREE.MeshStandardMaterial({
    color: 0x202936,
    emissive: 0x02070d,
    metalness: 0.78,
    roughness: 0.28,
  }),
  shell: new THREE.MeshStandardMaterial({
    color: 0xdfe9f2,
    emissive: 0x071019,
    metalness: 0.48,
    roughness: 0.22,
  }),
  linkA: new THREE.MeshStandardMaterial({
    color: 0x17c7d5,
    emissive: 0x042d32,
    metalness: 0.64,
    roughness: 0.2,
  }),
  linkB: new THREE.MeshStandardMaterial({
    color: 0xffb13d,
    emissive: 0x321b02,
    metalness: 0.56,
    roughness: 0.22,
  }),
  wrist: new THREE.MeshStandardMaterial({
    color: 0xf0f6fb,
    emissive: 0x080e15,
    metalness: 0.62,
    roughness: 0.2,
  }),
  dark: new THREE.MeshStandardMaterial({ color: 0x0c1118, metalness: 0.64, roughness: 0.4 }),
  rubber: new THREE.MeshStandardMaterial({ color: 0x07090c, metalness: 0.05, roughness: 0.84 }),
  bolt: new THREE.MeshStandardMaterial({ color: 0xaab6c3, metalness: 0.85, roughness: 0.18 }),
  safe: new THREE.MeshStandardMaterial({
    color: 0x77d970,
    emissive: 0x123814,
    metalness: 0.2,
    roughness: 0.42,
  }),
  cable: new THREE.MeshStandardMaterial({ color: 0x0b0f14, metalness: 0.18, roughness: 0.62 }),
  armor: new THREE.MeshStandardMaterial({
    color: 0x101820,
    emissive: 0x02080d,
    metalness: 0.7,
    roughness: 0.24,
  }),
  armorPanel: new THREE.MeshStandardMaterial({
    color: 0xf1f6fb,
    emissive: 0x071019,
    metalness: 0.52,
    roughness: 0.2,
  }),
  glass: new THREE.MeshStandardMaterial({
    color: 0x48f4ff,
    emissive: 0x0b3d44,
    metalness: 0.1,
    roughness: 0.08,
    transparent: true,
    opacity: 0.74,
  }),
  neonBlue: new THREE.MeshBasicMaterial({ color: 0x36f4ff }),
  neonAmber: new THREE.MeshBasicMaterial({ color: 0xffc247 }),
  neonRed: new THREE.MeshBasicMaterial({ color: 0xff466a }),
};

const jointConfig = [
  {
    key: "base",
    label: "J1 底座回转",
    meta: "回转台，带机械限位",
    min: -170,
    max: 170,
    value: 18,
    unit: "deg",
  },
  {
    key: "shoulder",
    label: "J2 肩关节俯仰",
    meta: "叉耳轴承支撑主臂",
    min: -10,
    max: 74,
    value: 18,
    unit: "deg",
  },
  {
    key: "elbow",
    label: "J3 肘关节折叠",
    meta: "双侧板前臂，预留转轴间隙",
    min: -96,
    max: 25,
    value: -82,
    unit: "deg",
  },
  {
    key: "wristPitch",
    label: "J4 腕部俯仰",
    meta: "紧凑腕座，避让法兰",
    min: -72,
    max: 72,
    value: 28,
    unit: "deg",
  },
  {
    key: "wristRoll",
    label: "J5 工具法兰滚转",
    meta: "同轴输出法兰",
    min: -180,
    max: 180,
    value: 0,
    unit: "deg",
  },
  {
    key: "gripper",
    label: "J6 平行夹爪开口",
    meta: "丝杆滑台驱动",
    min: 12,
    max: 92,
    value: 42,
    unit: "%",
  },
];

const state = Object.fromEntries(jointConfig.map((joint) => [joint.key, joint.value]));
const jointNodes = {};
const valueNodes = {};
const groundPlaneY = -0.01;
let lastSafeState = { ...state };
let groundLimitActive = false;
let demoActive = false;
let startTime = performance.now();

setupLights();
setupEnvironment();
buildRobotArm();
buildControls();
applyState();
resize();
animate();

window.addEventListener("resize", resize);
resetBtn.addEventListener("click", resetPose);
randomBtn.addEventListener("click", randomPose);
demoBtn.addEventListener("click", toggleDemo);

function setupLights() {
  scene.add(new THREE.HemisphereLight(0xd8f4ff, 0x15191f, 2));

  const key = new THREE.DirectionalLight(0xffffff, 2.8);
  key.position.set(6, 9, 6);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.near = 1;
  key.shadow.camera.far = 30;
  key.shadow.camera.left = -10;
  key.shadow.camera.right = 10;
  key.shadow.camera.top = 10;
  key.shadow.camera.bottom = -10;
  scene.add(key);

  const rim = new THREE.PointLight(0x36d1dc, 2.6, 16);
  rim.position.set(-5, 4, -5);
  scene.add(rim);

  const underGlow = new THREE.PointLight(0x36f4ff, 1.8, 7);
  underGlow.position.set(0, 0.85, 0);
  scene.add(underGlow);

  const warningGlow = new THREE.PointLight(0xffb13d, 1.1, 8);
  warningGlow.position.set(3.4, 2.1, 2.8);
  scene.add(warningGlow);
}

function setupEnvironment() {
  const grid = new THREE.GridHelper(16, 32, 0x3f4b57, 0x27313d);
  grid.position.y = -0.01;
  scene.add(grid);

  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(7.5, 128),
    new THREE.MeshStandardMaterial({ color: 0x15191f, roughness: 0.82, metalness: 0.05 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  const envelope = new THREE.Mesh(
    new THREE.TorusGeometry(5.25, 0.01, 8, 128),
    new THREE.MeshBasicMaterial({ color: 0x36f4ff, transparent: true, opacity: 0.38 }),
  );
  envelope.rotation.x = Math.PI / 2;
  envelope.position.y = 0.025;
  scene.add(envelope);

  const dangerRing = new THREE.Mesh(
    new THREE.TorusGeometry(1.58, 0.012, 8, 128),
    new THREE.MeshBasicMaterial({ color: 0xff466a, transparent: true, opacity: 0.55 }),
  );
  dangerRing.rotation.x = Math.PI / 2;
  dangerRing.position.y = 0.035;
  scene.add(dangerRing);
}

function buildRobotArm() {
  const baseTurn = new THREE.Group();
  jointNodes.base = baseTurn;
  scene.add(baseTurn);

  addBaseAssembly(baseTurn);

  const shoulderFixed = new THREE.Group();
  shoulderFixed.position.y = 1.08;
  baseTurn.add(shoulderFixed);
  addYoke(shoulderFixed, 0.74, 0.92, 0.72, materials.base);
  addShoulderShell(shoulderFixed);

  const shoulder = new THREE.Group();
  shoulder.position.y = 1.08;
  jointNodes.shoulder = shoulder;
  baseTurn.add(shoulder);
  addBearing(shoulder, 0.46, 0.86, materials.dark, materials.bolt);

  const upperLength = 2.22;
  const upperLink = makeParallelLink({
    length: upperLength,
    railWidth: 0.22,
    railDepth: 0.18,
    railSeparation: 0.72,
    material: materials.linkA,
    coverMaterial: materials.shell,
  });
  upperLink.position.y = 0.24;
  shoulder.add(upperLink);
  addArmShell(shoulder, upperLength, 0.24, materials.armorPanel, materials.glass);
  addNeonStrip(shoulder, 0.015, 1.48, 0.47, materials.neonBlue);

  const elbow = new THREE.Group();
  elbow.position.y = upperLength + 0.28;
  jointNodes.elbow = elbow;
  shoulder.add(elbow);
  addBearing(elbow, 0.38, 0.76, materials.dark, materials.bolt);

  const forearmLength = 1.72;
  const forearm = makeTaperedBox(0.44, forearmLength, 0.54, materials.linkB);
  forearm.position.y = forearmLength / 2 + 0.18;
  elbow.add(forearm);
  addForearmShell(elbow, forearmLength);
  addSideCable(elbow, forearmLength);
  addNeonStrip(elbow, -0.27, 1.05, 0.31, materials.neonAmber);

  const wristPitch = new THREE.Group();
  wristPitch.position.y = forearmLength + 0.38;
  jointNodes.wristPitch = wristPitch;
  elbow.add(wristPitch);
  addBearing(wristPitch, 0.31, 0.58, materials.dark, materials.bolt);

  const wristOffset = makeBox(0.42, 0.74, 0.42, materials.wrist);
  wristOffset.position.y = 0.42;
  wristPitch.add(wristOffset);
  addWristShell(wristPitch);
  addNeonStrip(wristPitch, 0.24, 0.48, 0.24, materials.neonBlue, 0.025);

  const wristRoll = new THREE.Group();
  wristRoll.position.y = 0.82;
  jointNodes.wristRoll = wristRoll;
  wristPitch.add(wristRoll);

  const rollMotor = makeCylinder(0.3, 0.32, 0.7, materials.dark);
  rollMotor.rotation.z = Math.PI / 2;
  wristRoll.add(rollMotor);
  addFlange(wristRoll, 0.38, 0.13, 0.42);

  const gripperRoot = new THREE.Group();
  gripperRoot.position.y = 0.45;
  jointNodes.gripperRoot = gripperRoot;
  wristRoll.add(gripperRoot);
  addGripper(gripperRoot);

  scene.add(makeCoordinateMarkers());
}

function addBaseAssembly(parent) {
  const plinth = makeCylinder(1.44, 1.5, 0.28, materials.base);
  plinth.position.y = 0.14;
  parent.add(plinth);

  const bearingRing = makeCylinder(1.08, 1.14, 0.18, materials.dark);
  bearingRing.position.y = 0.38;
  parent.add(bearingRing);

  const column = makeCylinder(0.62, 0.78, 0.74, materials.shell);
  column.position.y = 0.76;
  parent.add(column);

  addBoltCircle(parent, 0.98, 0.54, 12, 0.055);
  addBoltCircle(parent, 0.52, 1.15, 8, 0.045);

  const skirt = makeCylinder(1.22, 1.32, 0.34, materials.armor);
  skirt.position.y = 0.5;
  parent.add(skirt);

  const lightBand = makeCylinder(1.26, 1.26, 0.018, materials.neonBlue);
  lightBand.position.y = 0.68;
  parent.add(lightBand);
}

function addShoulderShell(parent) {
  const cowling = makeCapsule(0.44, 0.58, materials.armorPanel);
  cowling.rotation.z = Math.PI / 2;
  cowling.position.set(-0.06, 0.04, 0);
  cowling.scale.set(1, 1.18, 0.88);
  parent.add(cowling);

  const darkInsert = makeBox(0.82, 0.18, 0.7, materials.armor);
  darkInsert.position.set(0.1, -0.18, 0);
  parent.add(darkInsert);
}

function addYoke(parent, height, width, depth, material) {
  const back = makeBox(0.34, height, 0.18, material);
  back.position.set(-0.34, 0, 0);
  parent.add(back);

  [-1, 1].forEach((side) => {
    const cheek = makeBox(width, height, 0.16, material);
    cheek.position.set(0, 0, side * depth * 0.5);
    parent.add(cheek);
  });

  const lowerStop = makeBox(0.74, 0.12, depth + 0.12, materials.dark);
  lowerStop.position.set(0.08, -0.42, 0);
  parent.add(lowerStop);
}

function addBearing(parent, radius, width, bodyMaterial, boltMaterial) {
  const barrel = makeCylinder(radius, radius, width, bodyMaterial);
  barrel.rotation.x = Math.PI / 2;
  parent.add(barrel);

  const faceA = makeCylinder(radius * 1.08, radius * 1.08, 0.055, boltMaterial);
  faceA.rotation.x = Math.PI / 2;
  faceA.position.z = width * 0.5 + 0.03;
  parent.add(faceA);

  const faceB = faceA.clone();
  faceB.position.z = -width * 0.5 - 0.03;
  parent.add(faceB);

  addAxisRing(parent, radius * 1.28, "z");
  addBoltCircle(parent, radius * 0.78, width * 0.52 + 0.08, 6, 0.025, "z");
}

function addFlange(parent, radius, thickness, y) {
  const flange = makeCylinder(radius, radius, thickness, materials.bolt);
  flange.position.y = y;
  parent.add(flange);
  addBoltCircle(parent, radius * 0.72, y + thickness * 0.52, 6, 0.026);
}

function addGripper(parent) {
  const adapter = makeBox(0.62, 0.18, 0.5, materials.bolt);
  adapter.position.y = 0.08;
  parent.add(adapter);

  const slide = makeBox(0.98, 0.2, 0.26, materials.armor);
  slide.position.y = 0.28;
  parent.add(slide);

  const slideCover = makeBox(0.72, 0.16, 0.34, materials.armorPanel);
  slideCover.position.y = 0.44;
  parent.add(slideCover);

  const lens = makeBox(0.26, 0.035, 0.36, materials.glass);
  lens.position.set(0, 0.54, 0);
  parent.add(lens);

  const screw = makeCylinder(0.035, 0.035, 0.92, materials.bolt);
  screw.rotation.z = Math.PI / 2;
  screw.position.y = 0.31;
  parent.add(screw);

  const leftFinger = makeFinger(1);
  const rightFinger = makeFinger(-1);
  jointNodes.leftFinger = leftFinger;
  jointNodes.rightFinger = rightFinger;
  parent.add(leftFinger, rightFinger);

  const targetDot = new THREE.Mesh(
    new THREE.SphereGeometry(0.055, 18, 18),
    new THREE.MeshBasicMaterial({ color: 0xffffff }),
  );
  targetDot.position.y = 1.05;
  targetDot.name = "endEffector";
  parent.add(targetDot);
}

function makeParallelLink({ length, railWidth, railDepth, railSeparation, material, coverMaterial }) {
  const group = new THREE.Group();
  [-1, 1].forEach((side) => {
    const rail = makeBox(railWidth, length, railDepth, material);
    rail.position.set(0.02, length / 2, side * railSeparation * 0.5);
    group.add(rail);
  });

  const webA = makeBox(0.46, 0.12, railSeparation + 0.16, coverMaterial);
  webA.position.y = 0.46;
  group.add(webA);

  const webB = webA.clone();
  webB.position.y = length - 0.28;
  group.add(webB);

  const serviceCover = makeBox(0.12, length * 0.66, 0.11, materials.dark);
  serviceCover.position.set(-0.25, length * 0.5, 0);
  group.add(serviceCover);

  return group;
}

function addArmShell(parent, length, offsetY, shellMaterial, windowMaterial) {
  const shell = makeCapsule(0.31, length * 0.74, shellMaterial);
  shell.position.set(0.04, offsetY + length * 0.52, 0);
  shell.scale.set(0.86, 1, 1.18);
  parent.add(shell);

  const sideIntakeA = makeBox(0.08, length * 0.52, 0.08, materials.armor);
  sideIntakeA.position.set(-0.31, offsetY + length * 0.55, 0.42);
  parent.add(sideIntakeA);

  const sideIntakeB = sideIntakeA.clone();
  sideIntakeB.position.z = -0.42;
  parent.add(sideIntakeB);

  const window = makeBox(0.04, length * 0.42, 0.46, windowMaterial);
  window.position.set(0.31, offsetY + length * 0.55, 0);
  parent.add(window);
}

function addForearmShell(parent, length) {
  const shell = makeCapsule(0.29, length * 0.66, materials.armor);
  shell.position.set(0.02, length * 0.56 + 0.18, 0);
  shell.scale.set(0.92, 1, 1.14);
  parent.add(shell);

  const topPanel = makeBox(0.48, length * 0.5, 0.08, materials.armorPanel);
  topPanel.position.set(0, length * 0.56 + 0.18, 0.35);
  parent.add(topPanel);

  const blade = makeBox(0.1, length * 0.42, 0.5, materials.neonAmber);
  blade.position.set(-0.27, length * 0.58 + 0.18, 0);
  parent.add(blade);
}

function addWristShell(parent) {
  const wristPod = makeCapsule(0.28, 0.42, materials.armorPanel);
  wristPod.position.y = 0.42;
  wristPod.scale.set(1.08, 1, 1.08);
  parent.add(wristPod);

  const blackBelt = makeCylinder(0.34, 0.34, 0.08, materials.armor);
  blackBelt.position.y = 0.74;
  parent.add(blackBelt);
}

function makeTaperedBox(width, height, depth, material) {
  const group = new THREE.Group();
  const body = makeBox(width, height, depth, material);
  body.position.y = height / 2;
  group.add(body);

  const ribA = makeBox(width + 0.1, height * 0.72, 0.045, materials.dark);
  ribA.position.set(0, height * 0.5, depth * 0.5 + 0.03);
  group.add(ribA);

  const ribB = ribA.clone();
  ribB.position.z = -depth * 0.5 - 0.03;
  group.add(ribB);

  const endCap = makeBox(width + 0.12, 0.16, depth + 0.08, materials.shell);
  endCap.position.y = height - 0.05;
  group.add(endCap);
  return group;
}

function makeFinger(side) {
  const group = new THREE.Group();
  const carriage = makeBox(0.2, 0.2, 0.28, materials.bolt);
  carriage.position.set(side * 0.34, 0.34, 0);
  group.add(carriage);

  const jaw = makeBox(0.13, 0.76, 0.18, materials.dark);
  jaw.position.set(side * 0.34, 0.76, 0);
  group.add(jaw);

  const pad = makeBox(0.08, 0.38, 0.2, materials.rubber);
  pad.position.set(side * 0.27, 0.98, 0);
  group.add(pad);
  return group;
}

function addSideCable(parent, length) {
  const curve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-0.34, 0.1, -0.32),
    new THREE.Vector3(-0.54, length * 0.38, -0.38),
    new THREE.Vector3(-0.42, length * 0.76, -0.34),
    new THREE.Vector3(-0.2, length + 0.22, -0.28),
  ]);
  const cable = new THREE.Mesh(new THREE.TubeGeometry(curve, 36, 0.025, 8, false), materials.cable);
  cable.castShadow = true;
  parent.add(cable);
}

function addNeonStrip(parent, x, y, z, material, radius = 0.018) {
  const strip = makeCylinder(radius, radius, 1.24, material);
  strip.rotation.x = Math.PI / 2;
  strip.position.set(x, y, z);
  parent.add(strip);

  const glow = new THREE.PointLight(material.color, 0.35, 2.1);
  glow.position.set(x, y, z);
  parent.add(glow);
}

function makeCoordinateMarkers() {
  const group = new THREE.Group();
  const axes = [
    [0xff6b8a, [2.35, 0.025, 0], [Math.PI / 2, 0, Math.PI / 2]],
    [0x77d970, [0, 2.35, 0], [0, 0, 0]],
    [0x36d1dc, [0, 0.025, 2.35], [Math.PI / 2, 0, 0]],
  ];

  axes.forEach(([color, position, rotation]) => {
    const axis = makeCylinder(0.016, 0.016, 4.7, new THREE.MeshBasicMaterial({ color }));
    axis.position.set(...position);
    axis.rotation.set(...rotation);
    group.add(axis);
  });
  return group;
}

function addAxisRing(parent, radius, axis) {
  const ring = new THREE.Mesh(new THREE.TorusGeometry(radius, 0.012, 12, 96), materials.safe);
  if (axis === "z") ring.rotation.y = Math.PI / 2;
  if (axis === "x") ring.rotation.x = Math.PI / 2;
  parent.add(ring);
}

function addBoltCircle(parent, radius, yOrZ, count, boltRadius, plane = "xy") {
  for (let i = 0; i < count; i += 1) {
    const angle = (i / count) * Math.PI * 2;
    const bolt = makeCylinder(boltRadius, boltRadius, boltRadius * 0.9, materials.bolt);
    if (plane === "xy") {
      bolt.position.set(Math.cos(angle) * radius, yOrZ, Math.sin(angle) * radius);
    } else {
      bolt.rotation.x = Math.PI / 2;
      bolt.position.set(Math.cos(angle) * radius, Math.sin(angle) * radius, yOrZ);
    }
    parent.add(bolt);
  }
}

function makeCylinder(radiusTop, radiusBottom, height, material) {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radiusTop, radiusBottom, height, 56), material);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function makeCapsule(radius, length, material) {
  const geometry = new THREE.CapsuleGeometry(radius, length, 10, 28);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function makeBox(width, height, depth, material) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function buildControls() {
  const fragment = document.createDocumentFragment();

  jointConfig.forEach((joint) => {
    const item = document.createElement("label");
    item.className = "joint-control";
    item.innerHTML = `
      <span class="joint-topline">
        <span class="joint-name">${joint.label}</span>
        <span class="joint-value" data-value="${joint.key}">${joint.value}${joint.unit}</span>
      </span>
      <span class="joint-meta">${joint.meta}</span>
      <span class="range-wrap">
        <span>${joint.min}</span>
        <input
          type="range"
          min="${joint.min}"
          max="${joint.max}"
          value="${joint.value}"
          step="1"
          data-joint="${joint.key}"
          aria-label="${joint.label}"
        />
        <span>${joint.max}</span>
      </span>
    `;
    fragment.appendChild(item);
  });

  jointControls.appendChild(fragment);
  jointControls.querySelectorAll("input").forEach((input) => {
    valueNodes[input.dataset.joint] = jointControls.querySelector(`[data-value="${input.dataset.joint}"]`);
    input.addEventListener("input", () => {
      demoActive = false;
      updateDemoButton();
      state[input.dataset.joint] = Number(input.value);
      applyState();
    });
  });
}

function applyState({ enforceGround = true } = {}) {
  state.gripper = THREE.MathUtils.clamp(state.gripper, 12, 92);
  setRobotTransforms();

  if (enforceGround && isBelowGround()) {
    Object.assign(state, lastSafeState);
    setRobotTransforms();
    groundLimitActive = true;
  } else {
    lastSafeState = { ...state };
    groundLimitActive = false;
  }

  syncInputs();
  updateReadouts();
}

function setRobotTransforms() {
  jointNodes.base.rotation.y = THREE.MathUtils.degToRad(state.base);
  jointNodes.shoulder.rotation.z = THREE.MathUtils.degToRad(-state.shoulder);
  jointNodes.elbow.rotation.z = THREE.MathUtils.degToRad(state.elbow);
  jointNodes.wristPitch.rotation.z = THREE.MathUtils.degToRad(state.wristPitch);
  jointNodes.wristRoll.rotation.y = THREE.MathUtils.degToRad(state.wristRoll);

  const gripDistance = THREE.MathUtils.lerp(0.23, 0.48, state.gripper / 100);
  jointNodes.leftFinger.position.x = gripDistance;
  jointNodes.rightFinger.position.x = -gripDistance;
  jointNodes.base.updateMatrixWorld(true);
}

function isBelowGround() {
  const box = new THREE.Box3().setFromObject(jointNodes.base);
  return box.min.y < groundPlaneY;
}

function syncInputs() {
  jointConfig.forEach((joint) => {
    const input = jointControls.querySelector(`[data-joint="${joint.key}"]`);
    if (input) input.value = state[joint.key];
    if (valueNodes[joint.key]) valueNodes[joint.key].textContent = `${Math.round(state[joint.key])}${joint.unit}`;
  });
}

function updateReadouts() {
  const endEffector = scene.getObjectByName("endEffector");
  const world = new THREE.Vector3();
  endEffector.getWorldPosition(world);
  const radius = Math.hypot(world.x, world.z);

  positionReadout.textContent = `X ${world.x.toFixed(2)} · Y ${world.y.toFixed(2)} · Z ${world.z.toFixed(2)}`;
  reachReadout.textContent = `${radius.toFixed(2)} m`;
  gripReadout.textContent = `${Math.round(state.gripper)}%`;

  if (groundLimitActive) {
    poseReadout.textContent = "地面限位锁定";
  } else if (world.y < 0.65) {
    poseReadout.textContent = "接近地面限位";
  } else if (radius > 5.25) {
    poseReadout.textContent = "外展安全区";
  } else if (world.y > 3.8) {
    poseReadout.textContent = "高位装配区";
  } else {
    poseReadout.textContent = "安全工作区";
  }
  document.body.classList.toggle("limit-active", groundLimitActive);
}

function resetPose() {
  demoActive = false;
  jointConfig.forEach((joint) => {
    state[joint.key] = joint.value;
  });
  updateDemoButton();
  applyState();
}

function randomPose() {
  demoActive = false;
  const safeSnapshot = { ...lastSafeState };
  for (let attempt = 0; attempt < 40; attempt += 1) {
    jointConfig.forEach((joint) => {
      state[joint.key] = THREE.MathUtils.randInt(joint.min, joint.max);
    });
    setRobotTransforms();
    if (!isBelowGround()) break;
    Object.assign(state, safeSnapshot);
  }
  updateDemoButton();
  applyState();
}

function toggleDemo() {
  demoActive = !demoActive;
  startTime = performance.now();
  updateDemoButton();
}

function updateDemoButton() {
  demoBtn.setAttribute("aria-pressed", String(demoActive));
  demoBtn.querySelector("span[aria-hidden='true']").textContent = demoActive ? "⏸" : "▶";
}

function updateDemo(now) {
  if (!demoActive) return;

  const t = (now - startTime) * 0.001;
  state.base = Math.sin(t * 0.5) * 112;
  state.shoulder = 28 + Math.sin(t * 0.78) * 18;
  state.elbow = -64 + Math.sin(t * 0.95 + 0.7) * 24;
  state.wristPitch = Math.sin(t * 1.22 + 1.4) * 38;
  state.wristRoll = ((t * 48) % 360) - 180;
  state.gripper = 52 + Math.sin(t * 2.0) * 28;
  applyState();
}

function resize() {
  const { clientWidth, clientHeight } = canvas.parentElement;
  camera.aspect = clientWidth / clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(clientWidth, clientHeight, false);
}

function animate(now = performance.now()) {
  updateDemo(now);
  controls.update();
  renderer.render(scene, camera);
  updateDebugPixels();
  requestAnimationFrame(animate);
}

function updateDebugPixels() {
  try {
    const gl = renderer.getContext();
    const width = renderer.domElement.width;
    const height = renderer.domElement.height;
    const samples = [
      [0.28, 0.36],
      [0.5, 0.5],
      [0.72, 0.42],
      [0.38, 0.68],
      [0.62, 0.72],
    ];
    const pixel = new Uint8Array(4);
    let nonDark = 0;

    samples.forEach(([xRatio, yRatio]) => {
      gl.readPixels(
        Math.floor(width * xRatio),
        Math.floor(height * yRatio),
        1,
        1,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        pixel,
      );
      if (pixel[0] + pixel[1] + pixel[2] > 80) nonDark += 1;
    });

    writeDebugState({
      canvasWidth: width,
      canvasHeight: height,
      nonDarkSamples: nonDark,
      sceneObjects: scene.children.length,
    });
  } catch (error) {
    writeDebugState({
      error: error.message,
      sceneObjects: scene.children.length,
    });
  }
}

function writeDebugState(detail) {
  const root = document.documentElement;
  const frames = Number(root.dataset.armFrames || 0) + 1;
  root.dataset.armFrames = String(frames);
  root.dataset.armDebug = JSON.stringify({ frames, ...detail });
}
