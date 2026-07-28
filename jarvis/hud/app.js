/** D.I.N.E.S.H HUD — dense command console client. */
(function () {
  const COPY = {
    boot: ["INITIALIZING", "Bringing the neural engine online…"],
    idle: ["READY", "Space to speak · Esc cancels · type below"],
    listening: ["LISTENING", "Speak now — Esc to cancel"],
    thinking: ["PROCESSING", "Working through the request…"],
    speaking: ["SPEAKING", "Responding"],
    busy: ["BUSY", "Esc to cancel stuck operation"],
  };

  const $ = (id) => document.getElementById(id);
  const els = {
    status: $("status-label"),
    hint: $("status-hint"),
    power: $("power-line"),
    feed: $("feed"),
    ops: $("ops"),
    input: $("text-input"),
    form: $("composer"),
    mic: $("mic-btn"),
    wake: $("wake-btn"),
    vision: $("vision-btn"),
    orb: $("orb-btn"),
    model: $("chip-model"),
    voice: $("chip-voice"),
    link: $("chip-link"),
    hw: $("k-hw"),
    visionModel: $("k-vision"),
    whisper: $("k-whisper"),
    mode: $("k-mode"),
    uptime: $("k-uptime"),
    powerPct: $("k-power"),
    boot: $("boot-overlay"),
    ticker: $("ticker-track"),
    clock: $("clock-time"),
    date: $("clock-date"),
    cpuPct: $("cpu-pct"),
    ramPct: $("ram-pct"),
    diskLabel: $("disk-label"),
    diskBar: $("disk-bar"),
    loadLabel: $("load-label"),
    loadBar: $("load-bar"),
    ringCpu: document.querySelector("#ring-cpu .val"),
    ringRam: document.querySelector("#ring-ram .val"),
    permList: $("perm-list"),
    visionPreview: $("vision-preview"),
    visionImg: $("vision-img"),
    visionLabel: $("vision-label"),
    linkAlert: $("link-alert"),
    retryLink: $("retry-link"),
  };

  let ws = null;
  let status = "boot";
  let listenWatch = null;
  let wakeOn = false;
  let visionOn = false;
  let streamEl = null;
  let reconnectTimer = null;
  let connectWarningTimer = null;
  let lastServerMessage = 0;

  function setLinkState(online) {
    if (els.link) {
      els.link.textContent = online ? "LINK SECURE" : "LINK DOWN";
      els.link.classList.toggle("live", online);
    }
    if (els.linkAlert) els.linkAlert.classList.toggle("show", !online);
    [els.mic, els.wake, els.vision].forEach((button) => {
      if (button) button.disabled = !online;
    });
    if (els.input) els.input.disabled = !online;
  }

  function setWake(on) {
    wakeOn = !!on;
    if (!els.wake) return;
    els.wake.classList.toggle("armed", wakeOn);
    els.wake.textContent = wakeOn ? "Wake ON" : "Wake";
  }

  function setVision(on) {
    visionOn = !!on;
    if (els.vision) {
      els.vision.classList.toggle("armed", visionOn);
      els.vision.textContent = visionOn ? "Eyes ON" : "Eyes";
    }
    if (els.visionPreview) els.visionPreview.hidden = !visionOn;
  }

  function showPermissions(perms) {
    if (!els.permList || !perms || !perms.items) return;
    els.permList.innerHTML = perms.items.map((item) => {
      const mark = item.ok ? "✓" : "!";
      const cls = item.ok ? "ok" : "bad";
      return '<li class="' + cls + '"><b>' + mark + " " + esc(item.label) + "</b> " + esc(item.detail) + "</li>";
    }).join("");
  }

  function beginStream() {
    if (!els.feed) return;
    streamEl = document.createElement("div");
    streamEl.className = "line dinesh streaming";
    streamEl.textContent = "D.I.N.E.S.H · ";
    els.feed.appendChild(streamEl);
    els.feed.scrollTop = els.feed.scrollHeight;
  }

  function appendToken(tok) {
    if (!streamEl) beginStream();
    streamEl.textContent += tok;
    els.feed.scrollTop = els.feed.scrollHeight;
  }

  function endStream(finalText) {
    if (streamEl && finalText) {
      streamEl.textContent = "D.I.N.E.S.H · " + finalText;
      streamEl.classList.remove("streaming");
    }
    streamEl = null;
  }

  function setRing(el, pct) {
    if (!el) return;
    const p = Math.max(0, Math.min(100, pct));
    el.style.strokeDashoffset = String(100 - p);
  }

  function setStatus(s, hintOverride) {
    status = s || status;
    document.body.dataset.status = status;
    const c = COPY[status] || COPY.idle;
    if (els.status) els.status.textContent = c[0];
    if (els.hint) els.hint.textContent = hintOverride || c[1];
    if (window.DineshReactor) window.DineshReactor.setStatus(status);
  }

  function line(text, cls) {
    if (!els.feed) return;
    const d = document.createElement("div");
    d.className = "line " + (cls || "system");
    d.textContent = text;
    els.feed.appendChild(d);
    els.feed.scrollTop = els.feed.scrollHeight;
    while (els.feed.children.length > 50) els.feed.removeChild(els.feed.firstChild);
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function addOp(tool) {
    if (!els.ops) return;
    const empty = els.ops.querySelector(".empty");
    if (empty) empty.remove();
    const li = document.createElement("li");
    li.innerHTML =
      '<span class="name">' + esc(String(tool.step).padStart(2, "0") + " · " + tool.name) + "</span>" +
      esc(tool.detail || "");
    els.ops.prepend(li);
    while (els.ops.children.length > 10) els.ops.removeChild(els.ops.lastChild);
  }

  function clearOps() {
    if (!els.ops) return;
    els.ops.innerHTML = '<li class="empty">Waiting for a directive</li>';
  }

  function meta(msg) {
    if (msg.model && els.model) els.model.textContent = "MODEL " + msg.model;
    if (msg.voice && els.voice) els.voice.textContent = "VOICE " + msg.voice;
    if (msg.ram_gb && els.hw) els.hw.textContent = "M4 · " + msg.ram_gb + "GB";
    if (msg.vision && els.visionModel) els.visionModel.textContent = msg.vision;
    if (msg.whisper && els.whisper) els.whisper.textContent = msg.whisper;
    if (typeof msg.full_control === "boolean" && els.mode) {
      els.mode.textContent = msg.full_control ? "FULL" : "SAFE";
    }
    if (els.ticker && (msg.model || msg.voice)) {
      const t =
        "NEURAL CORE " + (msg.model || "") +
        " · VOICE " + (msg.voice || "") +
        " · UPLINK NOMINAL · TOOL SURFACE READY · STANDING BY · ";
      els.ticker.textContent = t + t;
    }
  }

  function applyTelemetry(t) {
    if (!t) return;
    if (typeof t.cpu === "number") {
      if (els.cpuPct) els.cpuPct.textContent = Math.round(t.cpu) + "%";
      setRing(els.ringCpu, t.cpu);
    }
    if (typeof t.ram === "number") {
      if (els.ramPct) els.ramPct.textContent = Math.round(t.ram) + "%";
      setRing(els.ringRam, t.ram);
    }
    if (t.disk) {
      if (els.diskLabel) els.diskLabel.textContent = t.disk.label || "—";
      if (els.diskBar) els.diskBar.style.width = (t.disk.pct || 0) + "%";
    }
    if (t.load) {
      if (els.loadLabel) els.loadLabel.textContent = t.load.label || "—";
      if (els.loadBar) els.loadBar.style.width = Math.min(100, (t.load.pct || 0)) + "%";
    }
    if (t.uptime && els.uptime) {
      els.uptime.textContent = t.uptime;
    }
    if (t.battery) {
      const pct = Number(t.battery.pct) || 0;
      const state = t.battery.state || "battery";
      if (els.power) {
        els.power.textContent = "Battery " + pct + "% · " + state;
      }
      if (els.powerPct) {
        els.powerPct.textContent = pct + "% " + state;
      }
    }
  }

  function tickClock() {
    const now = new Date();
    if (els.clock) {
      els.clock.textContent = now.toLocaleTimeString([], { hour12: false });
    }
    if (els.date) {
      const weekday = now.toLocaleDateString([], { weekday: "long" });
      const day = now.toLocaleDateString([], { day: "numeric" });
      const month = now.toLocaleDateString([], { month: "long" });
      els.date.textContent = (weekday + "  " + day + " " + month).toUpperCase();
    }
  }

  function clearListenWatch() {
    if (listenWatch) {
      clearInterval(listenWatch);
      listenWatch = null;
    }
  }

  function startListenWatch() {
    clearListenWatch();
    const t0 = Date.now();
    listenWatch = setInterval(() => {
      if (status !== "listening") {
        clearListenWatch();
        return;
      }
      const sec = Math.floor((Date.now() - t0) / 1000);
      if (els.hint) els.hint.textContent = "Speak now — " + sec + "s · Esc cancels";
    }, 500);
  }

  function onMsg(msg) {
    if (typeof msg.wake === "boolean") setWake(msg.wake);
    if (typeof msg.vision_on === "boolean") setVision(msg.vision_on);
    if (msg.vision_status && els.visionLabel) els.visionLabel.textContent = msg.vision_status;
    if (msg.permissions) showPermissions(msg.permissions);
    if (msg.event === "telemetry" || msg.telemetry) {
      applyTelemetry(msg.telemetry || msg);
    }

    if (msg.event === "hello" || msg.event === "boot") {
      meta(msg);
      setStatus(msg.status || "idle", msg.hint);
      if (msg.telemetry) applyTelemetry(msg.telemetry);
      if (typeof msg.vision_on === "boolean") setVision(msg.vision_on);
      if (msg.permissions) showPermissions(msg.permissions);
      if (els.link) {
        els.link.textContent = "LINK SECURE";
        els.link.classList.add("live");
      }
      if (els.boot) setTimeout(() => els.boot.classList.add("hide"), 1600);
      return;
    }
    if (msg.status) setStatus(msg.status, msg.hint);
    else if (msg.hint && els.hint) els.hint.textContent = msg.hint;

    if (msg.status === "listening") startListenWatch();
    else clearListenWatch();

    if (msg.event === "transcript" && msg.transcript) {
      line("You · " + msg.transcript, "you");
      if (msg.understood && msg.understood !== msg.transcript) {
        line("Understood as · " + msg.understood, "system");
      }
    }
    if (msg.event === "reply_start") beginStream();
    if (msg.event === "token" && msg.token) appendToken(msg.token);
    if (msg.event === "reply" && msg.reply) {
      if (streamEl) endStream(msg.reply);
      else line("D.I.N.E.S.H · " + msg.reply, "dinesh");
    }
    if (msg.event === "error" && msg.reply) line("Fault · " + msg.reply, "system");
    if (msg.event === "system" && msg.reply) line(msg.reply, "system");
    if (msg.event === "tool" && msg.tool) addOp(msg.tool);
    if (msg.clear_tools) clearOps();
    if (msg.status === "listening") clearOps();
    if (msg.event === "vision_frame" && msg.jpeg && els.visionImg) {
      els.visionImg.src = "data:image/jpeg;base64," + msg.jpeg;
    }
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(proto + "://" + location.host + "/ws");
    clearTimeout(connectWarningTimer);
    connectWarningTimer = setTimeout(() => setLinkState(false), 2500);
    ws.onopen = () => {
      clearTimeout(connectWarningTimer);
      lastServerMessage = Date.now();
      setLinkState(true);
    };
    ws.onclose = () => {
      clearTimeout(connectWarningTimer);
      setLinkState(false);
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 1400);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (e) => {
      lastServerMessage = Date.now();
      try { onMsg(JSON.parse(e.data)); } catch (_) {}
    };
  }

  function send(action, extra) {
    if (!ws || ws.readyState !== 1) {
      line("No uplink — reconnecting…", "system");
      return;
    }
    ws.send(JSON.stringify({ action, ...(extra || {}) }));
  }

  function listen() {
    if (status === "listening" || status === "busy" || status === "thinking" || status === "speaking") {
      send("cancel");
      line("Cancelled.", "system");
      setStatus("idle");
      return;
    }
    send("listen");
  }

  function chat(t) {
    t = (t || "").trim();
    if (!t) return;
    if (status === "listening") send("cancel");
    send("chat", { text: t });
  }

  if (els.form) {
    els.form.addEventListener("submit", (e) => {
      e.preventDefault();
      const t = els.input.value;
      els.input.value = "";
      chat(t);
    });
  }
  if (els.mic) els.mic.addEventListener("click", listen);
  if (els.wake) els.wake.addEventListener("click", () => send("wake", { on: !wakeOn }));
  if (els.vision) els.vision.addEventListener("click", () => send("vision", { on: !visionOn, preview: true }));
  if (els.retryLink) {
    els.retryLink.addEventListener("click", () => {
      if (ws) ws.close();
      ws = null;
      setLinkState(false);
      connect();
    });
  }
  if (els.orb) els.orb.addEventListener("click", listen);
  window.addEventListener("keydown", (e) => {
    if (e.code === "Escape") {
      e.preventDefault();
      send("cancel");
      line("Cancelled.", "system");
      setStatus("idle");
      return;
    }
    if (e.code === "Space" && document.activeElement !== els.input) {
      e.preventDefault();
      listen();
    }
  });

  setStatus("boot");
  setLinkState(false);
  tickClock();
  setInterval(tickClock, 1000);
  setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "ping" }));
      if (lastServerMessage && Date.now() - lastServerMessage > 6500) ws.close();
    }
  }, 3000);
  connect();
})();
