/** Dinesh HUD client — uplink, feed, boot sequence. */
(function () {
  const COPY = {
    boot: ["INITIALIZING", "Calibrating holographic interface…"],
    idle: ["SYSTEMS ONLINE", "Space to speak · Esc cancels · type below"],
    listening: ["LISTENING", "Speak now — Esc to cancel"],
    thinking: ["PROCESSING", "Working the problem…"],
    speaking: ["SPEAKING", "Responding"],
    busy: ["ENGAGED", "Esc to cancel stuck operation"],
  };

  const $ = (id) => document.getElementById(id);
  const els = {
    status: $("status-label"),
    hint: $("status-hint"),
    feed: $("feed"),
    ops: $("ops"),
    input: $("text-input"),
    form: $("composer"),
    mic: $("mic-btn"),
    orb: $("orb-btn"),
    model: $("chip-model"),
    voice: $("chip-voice"),
    link: $("chip-link"),
    hw: $("k-hw"),
    vision: $("k-vision"),
    whisper: $("k-whisper"),
    mode: $("k-mode"),
    boot: $("boot-overlay"),
    ticker: $("ticker-track"),
    gCpu: document.querySelector("#g-cpu .val"),
    gNet: document.querySelector("#g-net .val"),
  };

  let ws = null;
  let status = "boot";
  let listenWatch = null;

  function setStatus(s, hintOverride) {
    status = s || status;
    document.body.dataset.status = status;
    const c = COPY[status] || COPY.idle;
    els.status.textContent = c[0];
    els.hint.textContent = hintOverride || c[1];
    if (window.DineshReactor) window.DineshReactor.setStatus(status);
    if (els.gCpu) {
      const off = status === "thinking" ? 30 : status === "listening" ? 55 : 90;
      els.gCpu.style.strokeDashoffset = String(off);
    }
    if (els.gNet) {
      els.gNet.style.strokeDashoffset = status === "busy" ? 120 : 40;
    }
  }

  function line(text, cls) {
    const d = document.createElement("div");
    d.className = "line " + (cls || "system");
    d.textContent = text;
    els.feed.appendChild(d);
    els.feed.scrollTop = els.feed.scrollHeight;
    while (els.feed.children.length > 36) els.feed.removeChild(els.feed.firstChild);
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function addOp(tool) {
    const empty = els.ops.querySelector(".empty");
    if (empty) empty.remove();
    const li = document.createElement("li");
    li.innerHTML =
      '<span class="name">' + esc(String(tool.step).padStart(2, "0") + " · " + tool.name) + "</span>" +
      esc(tool.detail || "");
    els.ops.prepend(li);
    while (els.ops.children.length > 12) els.ops.removeChild(els.ops.lastChild);
  }

  function clearOps() {
    els.ops.innerHTML = '<li class="empty">No active directives</li>';
  }

  function meta(msg) {
    if (msg.model) els.model.textContent = "MODEL " + msg.model;
    if (msg.voice) els.voice.textContent = "VOICE " + msg.voice;
    if (msg.ram_gb) els.hw.textContent = "M4 · " + msg.ram_gb + "GB";
    if (msg.vision) els.vision.textContent = msg.vision;
    if (msg.whisper) els.whisper.textContent = msg.whisper;
    if (typeof msg.full_control === "boolean") {
      els.mode.textContent = msg.full_control ? "FULL" : "SAFE";
    }
    if (msg.model || msg.voice) {
      els.ticker.textContent =
        "NEURAL CORE " + (msg.model || "") +
        " · VOICE " + (msg.voice || "") +
        " · UPLINK NOMINAL · TOOL SURFACE READY · STANDING BY · " +
        "NEURAL CORE " + (msg.model || "") +
        " · VOICE " + (msg.voice || "") +
        " · UPLINK NOMINAL · TOOL SURFACE READY · STANDING BY · ";
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
      els.hint.textContent = "Speak now — " + sec + "s · Esc cancels · auto-stops on silence";
    }, 500);
  }

  function onMsg(msg) {
    if (msg.event === "hello" || msg.event === "boot") {
      meta(msg);
      setStatus(msg.status || "idle", msg.hint);
      els.link.textContent = "LINK SECURE";
      els.link.style.color = "#5dffb0";
      if (els.boot) {
        setTimeout(() => els.boot.classList.add("hide"), 900);
      }
      return;
    }
    if (msg.status) setStatus(msg.status, msg.hint);
    else if (msg.hint) els.hint.textContent = msg.hint;

    if (msg.status === "listening") startListenWatch();
    else clearListenWatch();

    if (msg.event === "transcript" && msg.transcript) line("YOU · " + msg.transcript, "you");
    if (msg.event === "reply" && msg.reply) line("D.I.N.E.S.H · " + msg.reply, "dinesh");
    if (msg.event === "error" && msg.reply) line("FAULT · " + msg.reply, "system");
    if (msg.event === "system" && msg.reply) line(msg.reply, "system");
    if (msg.event === "tool" && msg.tool) addOp(msg.tool);
    if (msg.clear_tools) clearOps();
    if (msg.status === "listening") clearOps();
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(proto + "://" + location.host + "/ws");
    ws.onopen = () => {
      els.link.textContent = "LINK SECURE";
      els.link.style.color = "#5dffb0";
      line("Secure channel established.", "system");
    };
    ws.onclose = () => {
      els.link.textContent = "LINK DOWN";
      els.link.style.color = "#ff5a6a";
      setTimeout(connect, 1400);
    };
    ws.onmessage = (e) => {
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
    line("YOU · " + t, "you");
    send("chat", { text: t });
  }

  els.form.addEventListener("submit", (e) => {
    e.preventDefault();
    const t = els.input.value;
    els.input.value = "";
    chat(t);
  });
  els.mic.addEventListener("click", listen);
  els.orb.addEventListener("click", listen);
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
  connect();
})();
