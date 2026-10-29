(function () {
  const page = document.querySelector(".admin-page");
  const slug = page.dataset.slug;

  const servingLabel = document.getElementById("servingLabel");
  const upNextLabel = document.getElementById("upNextLabel");
  const waitingList = document.getElementById("waitingList");
  const waitingCountLabel = document.getElementById("waitingCountLabel");
  const callNextBtn = document.getElementById("callNextBtn");
  const skipBtn = document.getElementById("skipBtn");

  const statWaiting = document.getElementById("statWaiting");
  const statServed = document.getElementById("statServed");
  const statAvg = document.getElementById("statAvg");

  function renderQueue(data) {
    servingLabel.textContent = data.now_serving ? data.now_serving.label : "—";
    upNextLabel.textContent = data.waiting.length ? data.waiting[0].label : "—";

    waitingCountLabel.textContent = `(${data.waiting.length})`;
    statWaiting.textContent = data.waiting.length;

    if (data.stats) {
      statServed.textContent = data.stats.served_today;
      statAvg.textContent = data.stats.avg_service_minutes ?? "—";
    }

    skipBtn.disabled = !data.now_serving;

    if (!data.waiting.length) {
      waitingList.innerHTML = '<li class="stub-empty">Queue is empty.</li>';
      return;
    }
    waitingList.innerHTML = data.waiting
      .map(
        (t, i) => `<li class="stub-item">
          <span class="stub-rank">${String(i + 1).padStart(2, "0")}</span>
          <span class="stub-label">${t.label}</span>
          <span class="stub-wait">joined ${new Date(t.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
        </li>`
      )
      .join("");
  }

  async function refresh() {
    try {
      const res = await fetch(`/api/admin/${slug}/queue`);
      const data = await res.json();
      renderQueue(data);
    } catch (e) { /* silent */ }
  }

  async function callNext() {
    callNextBtn.disabled = true;
    try {
      const res = await fetch(`/api/admin/${slug}/call-next`, { method: "POST" });
      const data = await res.json();
      await refresh();
    } finally {
      callNextBtn.disabled = false;
    }
  }

  async function skip() {
    skipBtn.disabled = true;
    try {
      await fetch(`/api/admin/${slug}/skip`, { method: "POST" });
      await refresh();
    } finally {
      skipBtn.disabled = false;
    }
  }

  callNextBtn.addEventListener("click", callNext);
  skipBtn.addEventListener("click", skip);

  refresh();
  setInterval(refresh, 4000);
})();
