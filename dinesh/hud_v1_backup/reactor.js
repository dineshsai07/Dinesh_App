/** Arc reactor v2 — denser rings, energy arcs, status-reactive core. */
(function () {
  const canvas = document.getElementById("reactor");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const DPR = Math.min(devicePixelRatio || 1, 2);
  let status = "idle";
  let t0 = performance.now();
  let energy = [];

  function resize() {
    const css = Math.min(window.innerHeight * 0.64, 540);
    canvas.style.width = css + "px";
    canvas.style.height = css + "px";
    canvas.width = Math.floor(css * DPR);
    canvas.height = Math.floor(css * DPR);
  }
  resize();
  window.addEventListener("resize", resize);

  window.DineshReactor = {
    setStatus(s) {
      status = s || "idle";
      if (window.DineshSpace) {
        window.DineshSpace.setIntensity(
          s === "thinking" ? 1.6 : s === "listening" ? 1.35 : s === "speaking" ? 1.25 : 1
        );
      }
    },
  };

  for (let i = 0; i < 18; i++) {
    energy.push({
      a: Math.random() * Math.PI * 2,
      len: 0.4 + Math.random() * 0.8,
      speed: 0.8 + Math.random() * 1.6,
      r: 0.55 + Math.random() * 0.3,
    });
  }

  function draw(now) {
    const w = canvas.width, h = canvas.height;
    const cx = w / 2, cy = h / 2;
    const S = w / 640;
    const t = (now - t0) / 1000;

    const speed =
      status === "listening" ? 2.4 :
      status === "thinking" ? 4.2 :
      status === "speaking" ? 1.9 : 1.05;
    const breathe = 0.5 + 0.5 * Math.sin(t * speed);

    ctx.clearRect(0, 0, w, h);

    // Bloom
    const bloom = ctx.createRadialGradient(cx, cy, 8 * S, cx, cy, 260 * S);
    const hot =
      status === "thinking" ? "255,200,87" :
      status === "listening" ? "93,255,176" : "61,240,255";
    bloom.addColorStop(0, `rgba(${hot},${0.45 + breathe * 0.25})`);
    bloom.addColorStop(0.35, `rgba(${hot},0.12)`);
    bloom.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = bloom;
    ctx.fillRect(0, 0, w, h);

    // Outer dashed rings
    for (let i = 0; i < 6; i++) {
      const r = (78 + i * 30) * S;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(61,240,255,${0.08 + i * 0.025})`;
      ctx.lineWidth = (1 + i * 0.2) * S;
      ctx.setLineDash([8 * S, 12 * S]);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    // Counter-rotating arcs
    for (let i = 0; i < 4; i++) {
      const r = (100 + i * 36) * S;
      const dir = i % 2 ? -1 : 1;
      const a = t * speed * dir + i * 0.7;
      ctx.beginPath();
      ctx.arc(cx, cy, r, a, a + 1.25);
      ctx.strokeStyle = i === 1 ? "#ffc857" : "#3df0ff";
      ctx.globalAlpha = 0.7;
      ctx.lineWidth = (3.5 - i * 0.4) * S;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(cx, cy, r, a + Math.PI, a + Math.PI + 0.55);
      ctx.globalAlpha = 0.35;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Energy bolts
    for (const e of energy) {
      const ang = e.a + t * e.speed * (status === "thinking" ? 2 : 1);
      const r0 = 48 * S;
      const r1 = (48 + 90 * e.r * (0.7 + breathe * 0.4)) * S;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(ang) * r0, cy + Math.sin(ang) * r0);
      const mid = (r0 + r1) / 2;
      const jitter = Math.sin(t * 8 + e.a) * 10 * S;
      ctx.quadraticCurveTo(
        cx + Math.cos(ang + 0.15) * mid + jitter,
        cy + Math.sin(ang + 0.15) * mid,
        cx + Math.cos(ang) * r1,
        cy + Math.sin(ang) * r1
      );
      ctx.strokeStyle = `rgba(${hot},0.45)`;
      ctx.lineWidth = 1.4 * S;
      ctx.stroke();
    }

    // Tick ring
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(t * 0.2 * speed);
    for (let i = 0; i < 72; i++) {
      const ang = (i / 72) * Math.PI * 2;
      const inner = 175 * S;
      const outer = inner + ((i % 6 === 0) ? 16 : 7) * S;
      ctx.beginPath();
      ctx.moveTo(Math.cos(ang) * inner, Math.sin(ang) * inner);
      ctx.lineTo(Math.cos(ang) * outer, Math.sin(ang) * outer);
      ctx.strokeStyle = "#3df0ff";
      ctx.globalAlpha = i % 6 === 0 ? 0.55 : 0.18;
      ctx.lineWidth = 1.4 * S;
      ctx.stroke();
    }
    ctx.restore();
    ctx.globalAlpha = 1;

    // Core
    const coreR = (32 + breathe * 8) * S;
    const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 2.4);
    cg.addColorStop(0, "#ffffff");
    cg.addColorStop(0.3, `rgba(${hot},1)`);
    cg.addColorStop(1, `rgba(${hot},0)`);
    ctx.beginPath();
    ctx.arc(cx, cy, coreR * 2.4, 0, Math.PI * 2);
    ctx.fillStyle = cg;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
    ctx.fillStyle = status === "thinking" ? "#ffc857" : status === "listening" ? "#5dffb0" : "#3df0ff";
    ctx.shadowColor = ctx.fillStyle;
    ctx.shadowBlur = 36 * S;
    ctx.fill();
    ctx.shadowBlur = 0;

    // Inner hex
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const ang = (i / 6) * Math.PI * 2 + t * 0.5;
      const rr = coreR * 0.52;
      const x = cx + Math.cos(ang) * rr;
      const y = cy + Math.sin(ang) * rr;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = "rgba(1,4,9,0.55)";
    ctx.lineWidth = 2.2 * S;
    ctx.stroke();

    // HUD glyphs around core
    ctx.font = `${11 * S}px Orbitron, sans-serif`;
    ctx.fillStyle = "rgba(61,240,255,0.45)";
    ctx.textAlign = "center";
    ctx.fillText("PRIMARY", cx, cy + 150 * S);
    ctx.fillText(status.toUpperCase(), cx, cy - 148 * S);

    requestAnimationFrame(draw);
  }
  requestAnimationFrame(draw);
})();
