/** Soft cyan mesh field for the command console. */
(function () {
  const canvas = document.getElementById("space");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let w, h, nodes = [], intensity = 1;

  function resize() {
    w = canvas.width = window.innerWidth * devicePixelRatio;
    h = canvas.height = window.innerHeight * devicePixelRatio;
    canvas.style.width = window.innerWidth + "px";
    canvas.style.height = window.innerHeight + "px";
    const count = Math.floor((window.innerWidth * window.innerHeight) / 16000);
    nodes = Array.from({ length: Math.max(32, Math.min(80, count)) }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.2 * devicePixelRatio,
      vy: (Math.random() - 0.5) * 0.2 * devicePixelRatio,
      r: (0.6 + Math.random() * 1.4) * devicePixelRatio,
    }));
  }
  resize();
  window.addEventListener("resize", resize);

  window.DineshSpace = {
    setIntensity(v) { intensity = v; },
  };

  function frame() {
    ctx.clearRect(0, 0, w, h);
    const g = ctx.createRadialGradient(w / 2, h * 0.45, 0, w / 2, h * 0.45, w * 0.55);
    g.addColorStop(0, "rgba(8,40,60,0.55)");
    g.addColorStop(1, "rgba(2,6,12,1)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);

    const maxDist = 130 * devicePixelRatio * intensity;
    for (const n of nodes) {
      n.x += n.vx * intensity;
      n.y += n.vy * intensity;
      if (n.x < 0 || n.x > w) n.vx *= -1;
      if (n.y < 0 || n.y > h) n.vy *= -1;
    }
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.hypot(dx, dy);
        if (d < maxDist) {
          ctx.strokeStyle = `rgba(61,240,255,${(0.14 * (1 - d / maxDist) * intensity).toFixed(3)})`;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }
    for (const n of nodes) {
      ctx.fillStyle = `rgba(154,248,255,${0.28 * intensity})`;
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fill();
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
