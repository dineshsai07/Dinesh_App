/** Starfield + floating particles — cinematic depth. */
(function () {
  const canvas = document.getElementById("space");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let w, h, stars = [], sparks = [];

  function resize() {
    w = canvas.width = window.innerWidth * devicePixelRatio;
    h = canvas.height = window.innerHeight * devicePixelRatio;
    canvas.style.width = window.innerWidth + "px";
    canvas.style.height = window.innerHeight + "px";
    stars = Array.from({ length: 140 }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      z: Math.random() * 0.8 + 0.2,
      a: Math.random(),
    }));
    sparks = Array.from({ length: 28 }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.35,
      vy: -0.2 - Math.random() * 0.5,
      r: 1 + Math.random() * 2,
    }));
  }
  resize();
  window.addEventListener("resize", resize);

  let intensity = 1;
  window.DineshSpace = {
    setIntensity(v) { intensity = v; },
  };

  function frame() {
    ctx.clearRect(0, 0, w, h);
    const g = ctx.createRadialGradient(w / 2, h * 0.45, 0, w / 2, h * 0.45, w * 0.55);
    g.addColorStop(0, "rgba(8,40,60,0.55)");
    g.addColorStop(1, "rgba(1,4,9,1)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);

    for (const s of stars) {
      ctx.globalAlpha = (0.25 + s.a * 0.55) * intensity;
      ctx.fillStyle = "#9af8ff";
      ctx.fillRect(s.x, s.y, s.z * devicePixelRatio * 1.4, s.z * devicePixelRatio * 1.4);
    }
    ctx.globalAlpha = 1;

    for (const p of sparks) {
      p.x += p.vx * intensity;
      p.y += p.vy * intensity;
      if (p.y < -10) { p.y = h + 10; p.x = Math.random() * w; }
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r * devicePixelRatio, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(61,240,255,0.55)";
      ctx.fill();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
