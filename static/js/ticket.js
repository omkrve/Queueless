(function () {
  const page = document.querySelector(".ticket-page");
  const slug = page.dataset.slug;
  const storageKey = `queueless:${slug}:token`;
  const historyKey = `queueless:${slug}:history`;

  const joinPanel = document.getElementById("joinPanel");
  const ticketPanel = document.getElementById("ticketPanel");
  const joinBtn = document.getElementById("joinBtn");
  const leaveBtn = document.getElementById("leaveBtn");
  const joinHeadline = document.getElementById("joinHeadline");
  const joinSub = document.getElementById("joinSub");
  const joinNowServing = document.getElementById("joinNowServing");
  const joinWaitingCount = document.getElementById("joinWaitingCount");

  const statusBadge = document.getElementById("statusBadge");
  const tokenLabel = document.getElementById("tokenLabel");
  const peopleAhead = document.getElementById("peopleAhead");
  const estWait = document.getElementById("estWait");
  const nowServingLive = document.getElementById("nowServingLive");
  const progressFill = document.getElementById("progressFill");
  const dots = Array.from(document.querySelectorAll(".progress-dot"));
  const historyList = document.getElementById("historyList");

  let pollTimer = null;

  function fmtWait(min) {
    if (min === null || min === undefined) return "—";
    if (min <= 0) return "now";
    return `~${min} min`;
  }

  function stageFor(token) {
    if (token.status === "completed" || token.status === "cancelled") return "done";
    if (token.status === "serving") return "turn";
    const ahead = token.people_ahead ?? 99;
    if (ahead === 0) return "next";
    if (ahead <= 2) return "almost";
    return "waiting";
  }

  const stageOrder = ["waiting", "almost", "next", "turn"];
  const stageFillPct = { waiting: 8, almost: 38, next: 68, turn: 100 };
  const stageBadge = {
    waiting: { text: "Waiting", cls: "" },
    almost: { text: "Almost up", cls: "" },
    next: { text: "Next", cls: "ticket-status--next" },
    turn: { text: "Your turn", cls: "ticket-status--turn" },
    done: { text: "Completed", cls: "ticket-status--done" },
  };

  function renderStage(stage) {
    const badge = stageBadge[stage];
    statusBadge.textContent = badge.text;
    statusBadge.className = "ticket-status " + badge.cls;
    progressFill.style.width = (stageFillPct[stage] ?? 0) + "%";
    const currentIdx = stageOrder.indexOf(stage);
    dots.forEach((d) => {
      const idx = stageOrder.indexOf(d.dataset.step);
      d.classList.toggle("active", idx <= currentIdx && stage !== "done");
      d.classList.toggle("current", idx === currentIdx && stage !== "done");
    });
  }

  function saveHistoryEntry(token) {
    const list = JSON.parse(localStorage.getItem(historyKey) || "[]");
    if (list.some((h) => h.id === token.id)) return;
    list.unshift({
      id: token.id,
      label: token.label,
      completed_at: token.completed_at,
      status: token.status,
    });
    localStorage.setItem(historyKey, JSON.stringify(list.slice(0, 12)));
  }

  function renderHistory() {
    const list = JSON.parse(localStorage.getItem(historyKey) || "[]");
    if (!list.length) {
      historyList.innerHTML = '<li class="history-empty">No completed visits yet on this device.</li>';
      return;
    }
    historyList.innerHTML = list
      .map((h) => {
        const when = h.completed_at ? new Date(h.completed_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
        const statusText = h.status === "cancelled" ? "Skipped" : "Completed";
        return `<li class="history-item"><span class="h-label">${h.label}</span><span class="h-meta">${statusText} · ${when}</span></li>`;
      })
      .join("");
  }

  function showJoinPanel() {
    joinPanel.classList.remove("hidden");
    ticketPanel.classList.add("hidden");
    refreshJoinPanelStats();
  }

  function showTicketPanel() {
    joinPanel.classList.add("hidden");
    ticketPanel.classList.remove("hidden");
  }

  async function refreshJoinPanelStats() {
    try {
      const res = await fetch(`/api/queue/${slug}/state`);
      const data = await res.json();
      joinNowServing.textContent = data.now_serving ? data.now_serving.label : "—";
      joinWaitingCount.textContent = data.waiting_count;
    } catch (e) { /* silent */ }
  }

  async function joinQueue() {
    joinBtn.disabled = true;
    joinBtn.textContent = "Joining…";
    try {
      const res = await fetch(`/api/queue/${slug}/join`, { method: "POST" });
      const data = await res.json();
      localStorage.setItem(storageKey, JSON.stringify({ id: data.token_id, label: data.label }));
      showTicketPanel();
      pollStatus();
      startPolling();
    } catch (e) {
      joinBtn.textContent = "Join queue";
      joinBtn.disabled = false;
    }
  }

  async function pollStatus() {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
    if (!saved) return;

    try {
      const res = await fetch(`/api/queue/${slug}/status/${saved.id}`);
      if (!res.ok) throw new Error("gone");
      const token = await res.json();

      const stateRes = await fetch(`/api/queue/${slug}/state`);
      const state = await stateRes.json();
      nowServingLive.textContent = state.now_serving ? state.now_serving.label : "—";

      tokenLabel.textContent = token.label;

      if (token.status === "completed" || token.status === "cancelled") {
        renderStage("done");
        peopleAhead.textContent = "0";
        estWait.textContent = "done";
        saveHistoryEntry(token);
        renderHistory();
        localStorage.removeItem(storageKey);
        stopPolling();
        setTimeout(showJoinPanel, 2200);
        return;
      }

      const stage = stageFor(token);
      renderStage(stage);
      peopleAhead.textContent = token.people_ahead ?? "—";
      estWait.textContent = fmtWait(token.estimated_wait_minutes);
    } catch (e) {
      localStorage.removeItem(storageKey);
      stopPolling();
      showJoinPanel();
    }
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(pollStatus, 3000);
  }
  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  function leaveQueue() {
    localStorage.removeItem(storageKey);
    stopPolling();
    showJoinPanel();
  }

  joinBtn.addEventListener("click", joinQueue);
  leaveBtn.addEventListener("click", leaveQueue);

  // init
  renderHistory();
  const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
  if (saved) {
    showTicketPanel();
    pollStatus();
    startPolling();
  } else {
    showJoinPanel();
  }
})();
