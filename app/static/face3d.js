/**
 * face3d.js — Kindalive's robot face, rendered as a retro LED dot-matrix
 * panel on a 2D canvas (no WebGL, no model files, no dependencies).
 *
 * The same 12-muscle FaceState that the neurochemical engine produces is
 * drawn as simple eye/brow/mouth shapes into a low-resolution mask, then
 * sampled onto a grid of glowing dots — so every expression reads as a
 * Cozmo/flip-dot-style face. On top of the driven expression it layers
 * its own life: blinking, eye saccades, a breathing glow, and a
 * syllable-rate mouth flap while the browser speaks the reply.
 *
 * (Filename kept for compatibility with the page wiring; this renderer
 * is 2D, not 3D.)
 *
 * Public API (set on window after init):
 *   window.kindaliveFace.setTargets({
 *     muscles: { brow_inner_raise: 0..1, ... },     // 12 FACS muscles
 *     mood:    { color: "#rrggbb", intensity: 0..1 },
 *   })
 *   window.kindaliveFace.setSpeaking(bool)   // talking mouth flap
 *   window.kindaliveFace.mouthPulse()        // word-boundary emphasis
 */

const MUSCLE_NAMES = [
  "brow_inner_raise", "brow_outer_raise", "brow_lower",
  "eyelid_upper_raise", "eyelid_lower_tighten", "cheek_raise",
  "nose_wrinkle", "lip_corner_pull", "lip_corner_depress",
  "jaw_open", "lip_pucker", "lip_press",
];

// Dot grid (fixed aspect; letterboxed into whatever the container is).
const COLS = 36;
const ROWS = 30;
const GRID_ASPECT = COLS / ROWS;

const DEFAULT_MOOD = "#46e0d8";

function hexRGB(hex) {
  const n = parseInt(String(hex).replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export default function initFace3D(containerId) {
  // NiceGUI mounts page content after this module runs, so the
  // container may not exist yet — poll until it appears.
  const container = document.getElementById(containerId);
  if (!container) {
    let tries = 0;
    const wait = setInterval(() => {
      if (document.getElementById(containerId)) {
        clearInterval(wait);
        initFace3D(containerId);
      } else if (++tries > 200) {
        clearInterval(wait);
        console.error("face3d: container #" + containerId + " never appeared");
      }
    }, 100);
    return;
  }
  startFaceLED(container);
}

function startFaceLED(container) {
  const canvas = document.createElement("canvas");
  canvas.style.width = "100%";
  canvas.style.height = "100%";
  canvas.style.display = "block";
  container.appendChild(canvas);
  const ctx = canvas.getContext("2d");

  // Low-res mask: one pixel per dot. Canvas anti-aliasing gives each
  // edge dot a fractional coverage → smooth-looking LED falloff.
  const mask = document.createElement("canvas");
  mask.width = COLS; mask.height = ROWS;
  const mctx = mask.getContext("2d");

  // ── State ───────────────────────────────────────────────────
  const target = {}, current = {};
  for (const n of MUSCLE_NAMES) { target[n] = 0; current[n] = 0; }
  let moodRGB = hexRGB(DEFAULT_MOOD);
  const moodCur = moodRGB.slice();
  let moodIntensity = 0.3;

  let speaking = false, speechJaw = 0, speechPulse = 0;

  // Autonomous life
  let blinkAt = 1.5, blinkPhase = -1;
  let saccadeAt = 2.0, sacc = 0, saccTarget = 0;
  let el = 0;

  window.kindaliveFace = {
    ready: true,
    setTargets(payload) {
      if (payload && payload.muscles) {
        for (const n of MUSCLE_NAMES) {
          const v = payload.muscles[n];
          if (typeof v === "number") target[n] = Math.max(0, Math.min(1, v));
        }
      }
      if (payload && payload.mood) {
        if (payload.mood.color) moodRGB = hexRGB(payload.mood.color);
        if (typeof payload.mood.intensity === "number") {
          moodIntensity = Math.max(0, Math.min(1, payload.mood.intensity));
        }
      }
    },
    setSpeaking(on) { speaking = !!on; if (!on) speechPulse = 0; },
    mouthPulse() { speechPulse = 1.0; },
  };

  // ── Layout (handles container resize / orientation) ─────────
  let DPR = Math.min(window.devicePixelRatio || 1, 2);
  let ox = 0, oy = 0, cell = 1;
  function layout() {
    const w = Math.max(container.clientWidth, 80);
    const h = Math.max(container.clientHeight, 80);
    canvas.width = Math.round(w * DPR);
    canvas.height = Math.round(h * DPR);
    const margin = 0.94;
    let panelW = canvas.width * margin;
    let panelH = panelW / GRID_ASPECT;
    if (panelH > canvas.height * margin) {
      panelH = canvas.height * margin;
      panelW = panelH * GRID_ASPECT;
    }
    cell = panelW / COLS;
    ox = (canvas.width - panelW) / 2;
    oy = (canvas.height - panelH) / 2;
  }
  new ResizeObserver(layout).observe(container);
  layout();

  // ── Expression → mask shapes (grid space: COLS×ROWS) ────────
  function drawMask(m, blink) {
    mctx.clearRect(0, 0, COLS, ROWS);
    mctx.fillStyle = "#fff";
    mctx.strokeStyle = "#fff";
    const cx = COLS / 2;
    const s = m.lip_corner_pull - m.lip_corner_depress;   // smile [-1,1]
    const eyeY = 10.5, dx = 7.6;

    const openK = Math.max(0.10, Math.min(1.2,
      0.52 + 0.55 * m.eyelid_upper_raise - 0.55 * m.eyelid_lower_tighten))
      * (1 - blink);

    // Brows (bars) — shown when furrowed or strongly raised
    const showBrow = m.brow_lower > 0.18 || m.brow_inner_raise > 0.28
      || m.brow_outer_raise > 0.4;
    for (const sx of [-1, 1]) {
      const ex = cx + sx * dx + sacc;
      // Eyes
      mctx.save();
      mctx.translate(ex, eyeY);
      if (s > 0.34 && blink < 0.5) {
        // Happy: upward arc (^)
        mctx.lineWidth = 2.2; mctx.lineCap = "round";
        mctx.beginPath();
        mctx.arc(0, 1.8, 4.0, Math.PI * 1.18, Math.PI * 1.82);
        mctx.stroke();
      } else {
        const angry = m.brow_lower;
        mctx.rotate(sx * angry * 0.45);
        const hh = Math.max(0.7, 1.0 + 3.6 * openK);
        mctx.beginPath();
        mctx.ellipse(0, 0, 3.3, hh, 0, 0, Math.PI * 2);
        mctx.fill();
      }
      mctx.restore();
      // Brow bar
      if (showBrow) {
        mctx.lineWidth = 1.7; mctx.lineCap = "round";
        const iy = eyeY - 5.2 + 2.6 * m.brow_lower - 1.6 * m.brow_inner_raise;
        const oy2 = eyeY - 5.2 - 1.3 * m.brow_outer_raise;
        mctx.beginPath();
        mctx.moveTo(ex - sx * 4, oy2);
        mctx.lineTo(ex + sx * 3, iy);
        mctx.stroke();
      }
    }

    // Mouth
    const my = 21.5, halfW = 7.0 * (1 - 0.3 * m.lip_pucker);
    const jaw = m.jaw_open;
    if (jaw > 0.10) {
      mctx.beginPath();
      mctx.ellipse(cx, my + 1.6 * s, halfW, 1.4 + 5.6 * jaw, 0, 0, Math.PI * 2);
      mctx.fill();
    } else {
      mctx.lineWidth = 2.1; mctx.lineCap = "round"; mctx.lineJoin = "round";
      mctx.beginPath();
      mctx.moveTo(cx - halfW, my - 1.6 * s);
      mctx.quadraticCurveTo(cx, my + 5.2 * s, cx + halfW, my - 1.6 * s);
      mctx.stroke();
    }
  }

  // ── Per-frame ───────────────────────────────────────────────
  let last = performance.now();
  function frame(now) {
    requestAnimationFrame(frame);
    const dt = Math.min((now - last) / 1000, 0.1); last = now;
    el += dt;
    const k = 1 - Math.exp(-dt / 0.11);
    for (const n of MUSCLE_NAMES) current[n] += (target[n] - current[n]) * k;
    for (let i = 0; i < 3; i++) moodCur[i] += (moodRGB[i] - moodCur[i]) * k;
    const m = current;

    // Blink
    if (blinkPhase >= 0) { blinkPhase += dt / 0.16; if (blinkPhase > 1) blinkPhase = -1; }
    else if (el > blinkAt) { blinkPhase = 0; blinkAt = el + 2.4 + Math.random() * 3.6; }
    const blink = blinkPhase >= 0 ? 1 - Math.abs(blinkPhase - 0.5) * 2 : 0;

    // Saccade (occasional glance)
    if (el > saccadeAt) { saccTarget = (Math.random() - 0.5) * 2.2; saccadeAt = el + 1.8 + Math.random() * 3.2; }
    sacc += (saccTarget - sacc) * (1 - Math.exp(-dt / 0.06));

    // Speaking flap → feeds the mouth's jaw_open
    let st = 0;
    if (speaking) {
      const osc = Math.abs(0.6 * Math.sin(el * 27.0) + 0.4 * Math.sin(el * 17.3 + 1.7));
      st = 0.10 + 0.55 * osc + 0.30 * speechPulse;
    }
    speechPulse *= Math.exp(-dt / 0.10);
    speechJaw += (st - speechJaw) * (1 - Math.exp(-dt / 0.05));

    const m2 = speechJaw > 0.001
      ? Object.assign({}, m, { jaw_open: Math.min(1, m.jaw_open + speechJaw) })
      : m;

    drawMask(m2, blink);
    const data = mctx.getImageData(0, 0, COLS, ROWS).data;

    // ── Draw the dot grid ─────────────────────────────────────
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const r = cell * 0.42;
    const breath = 0.92 + 0.08 * Math.sin(el * 1.6);
    const glow = (0.55 + 0.6 * moodIntensity) * breath;
    const [mr, mg, mb] = moodCur;
    for (let y = 0; y < ROWS; y++) {
      for (let x = 0; x < COLS; x++) {
        const lit = (data[(y * COLS + x) * 4 + 3] / 255);  // coverage
        const px = ox + (x + 0.5) * cell;
        const py = oy + (y + 0.5) * cell;
        if (lit > 0.06) {
          const a = 0.22 + 0.78 * Math.min(1, lit) * glow;
          ctx.beginPath();
          ctx.arc(px, py, r * (0.72 + 0.42 * lit), 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${mr|0},${mg|0},${mb|0},${a})`;
          ctx.shadowColor = `rgb(${mr|0},${mg|0},${mb|0})`;
          ctx.shadowBlur = 7 * lit * DPR;
          ctx.fill();
          ctx.shadowBlur = 0;
        } else {
          // Unlit dot — faint, so the panel reads as a grid.
          ctx.beginPath();
          ctx.arc(px, py, r * 0.5, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(255,255,255,0.035)";
          ctx.fill();
        }
      }
    }
  }
  requestAnimationFrame(frame);
}
