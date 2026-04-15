const consumerState = {
  websocket: null,
  activeRunId: "",
  activeReport: null,
  library: [],
  varieties: [],
};

const $ = (selector) => document.querySelector(selector);

function todayText() {
  return new Date().toISOString().slice(0, 10);
}

function wsUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/events?channel=run`;
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(payload?.detail || text || response.statusText);
  }
  return payload;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderMarkdown(markdown) {
  const lines = String(markdown || "").split("\n");
  const html = [];
  let inList = false;

  function closeList() {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  }

  lines.forEach((rawLine) => {
    const line = rawLine.trimEnd();
    if (!line.trim()) {
      closeList();
      return;
    }
    if (line.startsWith("<!--")) {
      closeList();
      return;
    }
    if (line.startsWith("# ")) {
      closeList();
      html.push(`<h1>${escapeHtml(line.slice(2))}</h1>`);
      return;
    }
    if (line.startsWith("## ")) {
      closeList();
      html.push(`<h2>${escapeHtml(line.slice(3))}</h2>`);
      return;
    }
    if (line.startsWith("### ")) {
      closeList();
      html.push(`<h3>${escapeHtml(line.slice(4))}</h3>`);
      return;
    }
    if (line.startsWith(">")) {
      closeList();
      html.push(`<blockquote>${escapeHtml(line.replace(/^>\s?/, ""))}</blockquote>`);
      return;
    }
    if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${escapeHtml(line.replace(/^[-*]\s+/, "").replace(/^\d+\.\s+/, ""))}</li>`);
      return;
    }
    closeList();
    html.push(`<p>${escapeHtml(line)}</p>`);
  });
  closeList();
  return html.join("");
}

function setStep(step, state) {
  const item = document.querySelector(`[data-step="${step}"]`);
  if (item) {
    item.classList.remove("active", "done");
    item.classList.add(state);
  }
}

function resetSteps() {
  document.querySelectorAll("#progress-steps span").forEach((item) => {
    item.classList.remove("active", "done");
  });
}

function appendEvent(payload) {
  const feed = $("#event-feed");
  const item = document.createElement("div");
  item.className = "event-item";
  const parts = [payload.event_type || "event"];
  if (payload.step) {
    parts.push(payload.step);
  }
  if (payload.variety_code) {
    parts.push(payload.variety_code);
  }
  item.textContent = parts.join(" / ");
  feed.prepend(item);
}

function connectEvents() {
  if (consumerState.websocket) {
    return;
  }
  consumerState.websocket = new WebSocket(wsUrl());
  consumerState.websocket.onmessage = async (event) => {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch (error) {
      return;
    }
    if (payload.event_type === "subscribed") {
      return;
    }
    appendEvent(payload);
    if (payload.event_type === "step_started" && payload.step) {
      setStep(payload.step, "active");
    }
    if (payload.event_type === "step_completed" && payload.step) {
      setStep(payload.step, "done");
    }
    if (payload.event_type === "run_started") {
      consumerState.activeRunId = payload.run_id || consumerState.activeRunId;
      $("#run-status").textContent = "研究任务已开始";
    }
    if (payload.event_type === "run_completed") {
      consumerState.activeRunId = payload.run_id || consumerState.activeRunId;
      $("#run-status").textContent = "报告生成完成";
      document.querySelectorAll("#progress-steps span").forEach((item) => item.classList.add("done"));
      if (consumerState.activeRunId) {
        await loadReport(consumerState.activeRunId);
        await refreshLibrary();
      }
    }
    if (payload.event_type === "run_failed") {
      $("#run-status").textContent = "研究任务失败";
    }
  };
  consumerState.websocket.onclose = () => {
    consumerState.websocket = null;
  };
}

async function refreshHealth() {
  const payload = await requestJson("/healthz");
  $("#health-status").textContent = payload.status === "ok" ? "在线" : "异常";
  $("#storage-status").textContent = payload.storage_enabled ? "已开启" : "未配置";
  $("#search-boundary").textContent = payload.web_search_enabled ? "web search 已启用" : "web search 未启用";
}

function varietyLabel(item) {
  return `${item.name} ${item.code}`;
}

function selectedVariety() {
  return consumerState.varieties.find((item) => item.code === $("#symbol-select").value) || consumerState.varieties[0];
}

function makePickerButton(label, active, onClick, subLabel = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = active ? "picker-option selected" : "picker-option";
  button.innerHTML = subLabel
    ? `<strong>${escapeHtml(label)}</strong><span>${escapeHtml(subLabel)}</span>`
    : `<strong>${escapeHtml(label)}</strong>`;
  button.setAttribute("aria-pressed", active ? "true" : "false");
  button.addEventListener("click", onClick);
  return button;
}

function populateSymbolOptions() {
  if (!consumerState.varieties.length) {
    return;
  }
  const hidden = $("#symbol-select");
  const current = hidden.value || "CF";
  const selected = consumerState.varieties.find((item) => item.code === current) || consumerState.varieties[0];
  hidden.value = selected.code;
  $("#symbol-trigger").textContent = varietyLabel(selected);
}

function updateContractOptions(preferredContract = "") {
  const contractHidden = $("#contract-select");
  const variety = selectedVariety();
  if (!variety || !variety.contracts.length) {
    contractHidden.value = "";
    $("#contract-trigger").textContent = "暂无合约";
    $("#contract-trigger").disabled = true;
    return;
  }
  const selectedContract = variety.contracts.includes(preferredContract)
    ? preferredContract
    : variety.contracts[0];
  contractHidden.value = selectedContract;
  $("#contract-trigger").disabled = false;
  $("#contract-trigger").textContent = selectedContract === variety.contracts[0]
    ? `${selectedContract}（主力）`
    : selectedContract;
}

function closePickerModal() {
  $("#picker-modal").classList.add("hidden");
}

function openPickerModal(kind) {
  const modal = $("#picker-modal");
  const title = $("#picker-modal-title");
  const options = $("#picker-options");
  options.innerHTML = "";

  if (kind === "symbol") {
    title.textContent = "选择品种";
    const selectedCode = $("#symbol-select").value;
    consumerState.varieties.forEach((item) => {
      options.appendChild(
        makePickerButton(
          item.name,
          item.code === selectedCode,
          () => {
            $("#symbol-select").value = item.code;
            populateSymbolOptions();
            updateContractOptions(item.contracts[0] || "");
            closePickerModal();
          },
          `${item.code} · ${item.exchange}`
        )
      );
    });
  } else {
    const variety = selectedVariety();
    title.textContent = `选择合约 - ${varietyLabel(variety)}`;
    const selectedContract = $("#contract-select").value;
    variety.contracts.forEach((contract, index) => {
      options.appendChild(
        makePickerButton(
          contract,
          contract === selectedContract,
          () => {
            updateContractOptions(contract);
            closePickerModal();
          },
          index === 0 ? "主力合约" : "可选合约"
        )
      );
    });
  }
  modal.classList.remove("hidden");
}

async function refreshVarieties() {
  const payload = await requestJson("/varieties");
  consumerState.varieties = payload;
  populateSymbolOptions();
  updateContractOptions();
}

function buildRunPayload(form) {
  const data = new FormData(form);
  return {
    symbol: String(data.get("symbol") || "CF"),
    contract: String(data.get("contract") || "").trim(),
    target_date: String(data.get("target_date") || todayText()),
    report_render_mode: String(data.get("report_render_mode") || "hybrid"),
    research_profile: {
      persona: String(data.get("persona") || "institution"),
      user_focus: String(data.get("prompt") || "").trim(),
    },
  };
}

async function submitResearch(event) {
  event.preventDefault();
  connectEvents();
  resetSteps();
  $("#answer-empty").classList.remove("hidden");
  $("#report-view").classList.add("hidden");
  $("#follow-up-answer").textContent = "";
  $("#event-feed").innerHTML = "";
  $("#run-status").textContent = "已提交，等待运行事件";
  const payload = buildRunPayload(event.currentTarget);
  await requestJson("/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setTimeout(refreshLibrary, 5000);
}

function renderSources(payload) {
  const report = payload.final_report || {};
  const rawData = payload.raw_data || {};
  const sources = report.data_sources || rawData.sources || [];
  const gaps = rawData.data_gaps || [];
  const externalCount = (rawData.external_market_facts || []).length;
  const fundamentalCount = (rawData.fundamental_facts || []).length;
  const sourceList = $("#source-list");
  sourceList.innerHTML = "";

  [
    ["数据来源", sources.length ? sources.join("；") : "暂无可核验来源"],
    ["外盘/宏观", externalCount ? `${externalCount} 条结构化事实` : "暂无可引用结构化事实"],
    ["基本面", fundamentalCount ? `${fundamentalCount} 条结构化事实` : "暂无可引用结构化事实"],
    ["数据缺口", gaps.length ? gaps.slice(0, 4).join("；") : "当前报告未登记额外缺口"],
  ].forEach(([label, value]) => {
    const node = document.createElement("div");
    node.className = "source-pill";
    node.innerHTML = `<strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span>`;
    sourceList.appendChild(node);
  });
}

async function loadReport(runId) {
  const payload = await requestJson(`/reports/${runId}`);
  consumerState.activeRunId = runId;
  consumerState.activeReport = payload;
  const report = payload.final_report || {};
  const content = report.content || payload.report_draft || "";
  $("#answer-empty").classList.add("hidden");
  $("#report-view").classList.remove("hidden");
  $("#report-view").innerHTML = renderMarkdown(content);
  renderSources(payload);

  const md = $("#download-md");
  const pdf = $("#download-pdf");
  if (report.markdown_url) {
    md.href = report.markdown_url;
    md.classList.remove("hidden");
  } else {
    md.classList.add("hidden");
  }
  if (report.pdf_url) {
    pdf.href = report.pdf_url;
    pdf.classList.remove("hidden");
  } else {
    pdf.classList.add("hidden");
  }
  return payload;
}

async function askFollowUp() {
  const question = $("#follow-up-input").value.trim();
  if (!question) {
    $("#follow-up-answer").textContent = "请输入一个问题。";
    return;
  }
  if (!consumerState.activeRunId) {
    $("#follow-up-answer").textContent = "请先生成或打开一份报告。";
    return;
  }
  const payload = await requestJson(`/reports/${consumerState.activeRunId}/ask`, {
    method: "POST",
    body: JSON.stringify({ question, persona: $("#persona-select").value }),
  });
  $("#follow-up-answer").textContent = payload.answer;
}

function renderLibrary(items) {
  const library = $("#report-library");
  library.innerHTML = "";
  if (!items.length) {
    library.innerHTML = '<p class="empty-state">暂无历史报告。</p>';
    return;
  }
  items.slice(0, 9).forEach((item) => {
    const card = document.createElement("article");
    card.className = "report-card";
    card.innerHTML = `
      <h3>${escapeHtml(item.variety)} ${escapeHtml(item.symbol)}</h3>
      <p class="report-meta">${escapeHtml(item.target_date)} / ${escapeHtml(item.sentiment || "-")} / 评分 ${escapeHtml(item.final_score ?? "-")}</p>
      <p class="report-meta">${escapeHtml(item.summary || "暂无摘要")}</p>
      <button class="ghost" type="button">打开报告</button>
    `;
    card.querySelector("button").addEventListener("click", () => loadReport(item.run_id));
    library.appendChild(card);
  });
}

async function refreshLibrary() {
  try {
    const payload = await requestJson("/reports?limit=9");
    consumerState.library = payload;
    renderLibrary(payload);
  } catch (error) {
    $("#report-library").innerHTML = '<p class="empty-state">报告库暂不可用。</p>';
  }
}

function bindConsumerEvents() {
  $("#target-date").value = todayText();
  $("#consumer-run-form").addEventListener("submit", submitResearch);
  $("#symbol-trigger").addEventListener("click", () => openPickerModal("symbol"));
  $("#contract-trigger").addEventListener("click", () => openPickerModal("contract"));
  $("#picker-close").addEventListener("click", closePickerModal);
  $("#picker-modal").addEventListener("click", (event) => {
    if (event.target.id === "picker-modal") {
      closePickerModal();
    }
  });
  $("#refresh-consumer-health").addEventListener("click", async () => {
    try {
      await refreshHealth();
    } catch (error) {
      $("#health-status").textContent = "检查失败";
    }
  });
  $("#refresh-library").addEventListener("click", refreshLibrary);
  $("#ask-follow-up").addEventListener("click", async () => {
    try {
      await askFollowUp();
    } catch (error) {
      $("#follow-up-answer").textContent = String(error);
    }
  });
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      $("#research-prompt").value = button.dataset.prompt || "";
    });
  });
}

bindConsumerEvents();
connectEvents();
refreshVarieties().catch(() => updateContractOptions());
refreshHealth().catch(() => {
  $("#health-status").textContent = "检查失败";
});
refreshLibrary();
