const state = {
  websocket: null,
  activeChannel: "run",
  researchOptions: null,
  activePersona: "futures_desk",
  preview: null,
  previewSignature: "",
  activeRunId: "",
  reportFilters: {
    symbol: "",
    variety_code: "",
    target_date: "",
    limit: 12,
  },
};

const $ = (selector) => document.querySelector(selector);

function pretty(value) {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}

function appendLog(target, message) {
  target.textContent = `${message}\n${target.textContent}`.trim();
}

function buildWsUrl(channel) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/events?channel=${channel}`;
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch (error) {
    payload = text;
  }
  if (!response.ok) {
    throw new Error(pretty(payload));
  }
  return payload;
}

function formToObject(form) {
  const data = new FormData(form);
  const payload = {};
  for (const [key, value] of data.entries()) {
    if (value !== "") {
      payload[key] = value;
    }
  }
  return payload;
}

function truncate(text, limit = 520) {
  if (!text) {
    return "";
  }
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function getSelectedVariety() {
  if (!state.researchOptions) {
    return null;
  }
  const code = $("#variety-select").value;
  return state.researchOptions.varieties.find((item) => item.code === code) || null;
}

function getSelectedSymbol() {
  return $("#contract-select").value || $("#variety-select").value;
}

function getResearchProfile() {
  return {
    horizon: $("#horizon-select").value,
    persona: state.activePersona,
    user_focus: $("#focus-input").value.trim(),
  };
}

function getPreviewSignature() {
  return JSON.stringify({
    symbol: getSelectedSymbol(),
    horizon: $("#horizon-select").value,
    persona: state.activePersona,
    focus: $("#focus-input").value.trim(),
  });
}

function setSelectionSummary() {
  const variety = getSelectedVariety();
  const horizon = $("#horizon-select").selectedOptions[0]?.textContent || "中线";
  const persona = state.researchOptions?.personas.find((item) => item.id === state.activePersona);
  if (!variety) {
    $("#selection-summary").textContent = "等待加载品种配置";
    return;
  }
  $("#selection-summary").textContent = `${variety.name} / ${getSelectedSymbol()} / ${horizon} / ${
    persona?.label || "金融公司期货部门"
  }`;
}

async function refreshHealth() {
  const payload = await requestJson("/healthz");
  $("#health-status").textContent = payload.status === "ok" ? "在线" : pretty(payload);
  $("#storage-status").textContent = payload.storage_enabled ? "已开启" : "未配置";
  $("#model-status").textContent = payload.llm_model;
}

function disconnectEvents() {
  if (state.websocket) {
    state.websocket.close();
    state.websocket = null;
  }
  $("#event-connection-status").textContent = "未连接";
}

function connectEvents(channel) {
  disconnectEvents();
  state.activeChannel = channel;
  const url = buildWsUrl(channel);
  const log = $("#events-log");
  state.websocket = new WebSocket(url);
  $("#event-connection-status").textContent = `连接中：${channel}`;

  state.websocket.onopen = () => {
    $("#event-connection-status").textContent = `已连接 ${channel}`;
  };

  state.websocket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.event_type !== "subscribed") {
        if (!state.activeRunId || !payload.run_id || payload.run_id === state.activeRunId || payload.batch_id) {
          appendLog(log, pretty(payload));
        }
      }
      handleRuntimeEvent(payload).catch((error) => {
        appendLog(log, `[Event Handler Error] ${String(error)}`);
      });
    } catch (error) {
      appendLog(log, `[Parse Error] ${String(error)}`);
    }
  };

  state.websocket.onerror = () => {
    appendLog(log, "[WebSocket Error] 连接发生异常");
  };

  state.websocket.onclose = () => {
    $("#event-connection-status").textContent = "已断开";
    state.websocket = null;
  };
}

async function loadResearchOptions() {
  const payload = await requestJson("/research/options");
  state.researchOptions = payload;

  const varietySelect = $("#variety-select");
  varietySelect.innerHTML = payload.varieties
    .map((item) => `<option value="${item.code}">${item.name} (${item.code})</option>`)
    .join("");
  varietySelect.value = payload.varieties.find((item) => item.code === "CF")?.code || payload.varieties[0]?.code || "";

  const horizonSelect = $("#horizon-select");
  horizonSelect.innerHTML = payload.horizons
    .map((item) => `<option value="${item.id}">${item.label}</option>`)
    .join("");
  horizonSelect.value = payload.horizons.find((item) => item.id === "medium_term")?.id || payload.horizons[0]?.id || "";

  state.activePersona =
    payload.personas.find((item) => item.id === "futures_desk")?.id || payload.personas[0]?.id || "futures_desk";

  renderPersonaGrid(payload.personas);
  syncContracts();
  setSelectionSummary();
}

function renderPersonaGrid(personas) {
  const grid = $("#persona-grid");
  grid.innerHTML = "";
  personas.forEach((persona, index) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `persona-card${persona.id === state.activePersona ? " selected" : ""}`;
    card.dataset.personaId = persona.id;
    card.innerHTML = `
      <span class="persona-index">${String(index + 1).padStart(2, "0")}</span>
      <strong>${persona.label}</strong>
      <p>${persona.description}</p>
    `;
    card.addEventListener("click", () => {
      state.activePersona = persona.id;
      renderPersonaGrid(personas);
      invalidatePreview();
      setSelectionSummary();
    });
    grid.appendChild(card);
  });
}

function syncContracts() {
  const variety = getSelectedVariety();
  const contractSelect = $("#contract-select");
  contractSelect.innerHTML = "";
  if (!variety) {
    return;
  }
  const contracts = variety.contracts.length ? variety.contracts : [variety.default_contract || variety.code];
  contracts.forEach((contract) => {
    const option = document.createElement("option");
    option.value = contract;
    option.textContent = contract;
    contractSelect.appendChild(option);
  });
  contractSelect.value = variety.default_contract || contracts[0];
  invalidatePreview();
  setSelectionSummary();
}

function invalidatePreview() {
  state.preview = null;
  state.previewSignature = "";
  $("#preview-empty").classList.remove("hidden");
  $("#preview-content").classList.add("hidden");
  $("#preview-template").classList.add("hidden");
  $("#preview-summary").textContent = "";
  $("#preview-key-points").innerHTML = "";
  $("#preview-directives").innerHTML = "";
}

function renderPreview(payload) {
  state.preview = payload;
  state.previewSignature = getPreviewSignature();
  $("#preview-empty").classList.add("hidden");
  $("#preview-content").classList.remove("hidden");
  $("#preview-summary").textContent = payload.summary;
  $("#preview-template").textContent = payload.recommended_template;
  $("#preview-template").classList.remove("hidden");
  renderList("#preview-key-points", payload.key_points || []);
  renderList("#preview-directives", payload.writing_directives || []);
}

function renderList(selector, items) {
  const node = $(selector);
  node.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    node.appendChild(li);
  });
}

async function previewResearch() {
  const payload = await requestJson("/research/preview", {
    method: "POST",
    body: JSON.stringify({
      symbol: getSelectedSymbol(),
      research_profile: getResearchProfile(),
    }),
  });
  renderPreview(payload);
  $("#run-status").textContent = "需求已梳理，可以开始生成。";
  $("#active-run-meta").textContent = `${payload.variety} ${payload.resolved_symbol}`;
  return payload;
}

async function ensurePreview() {
  if (state.preview && state.previewSignature === getPreviewSignature()) {
    return state.preview;
  }
  return previewResearch();
}

async function generateReport() {
  const preview = await ensurePreview();
  const payload = await requestJson("/runs", {
    method: "POST",
    body: JSON.stringify({
      symbol: getSelectedSymbol(),
      target_date: $("#target-date").value,
      research_profile: {
        ...getResearchProfile(),
        briefing_summary: preview.summary,
        key_points: preview.key_points || [],
        writing_directives: preview.writing_directives || [],
        recommended_template: preview.recommended_template || "",
      },
    }),
  });
  state.activeRunId = payload.run_id;
  $("#run-status").textContent = "已提交生成请求，等待事件回传。";
  $("#active-run-meta").textContent = `${payload.requested_symbol} -> ${payload.resolved_symbol} | run_id: ${payload.run_id}`;
  hideDownloadLinks();
  $("#report-snippet").textContent = "研报生成中，等待审核和落库完成。";
  return payload;
}

function hideDownloadLinks() {
  $("#download-md").classList.add("hidden");
  $("#download-pdf").classList.add("hidden");
}

async function submitBatchRun(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = formToObject(form);
  payload.all_varieties = form.elements.all_varieties.checked;
  payload.symbols = payload.symbols
    ? payload.symbols.split(",").map((item) => item.trim()).filter(Boolean)
    : [];
  payload.concurrency = Number(payload.concurrency || 2);
  const result = await requestJson("/batches", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  $("#batch-run-result").textContent = pretty(result);
}

async function refreshReports() {
  const params = new URLSearchParams();
  Object.entries(state.reportFilters).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  try {
    const payload = await requestJson(`/reports${query ? `?${query}` : ""}`);
    renderReports(payload);
  } catch (error) {
    $("#reports-state").textContent =
      "报告查询不可用，通常是因为尚未配置 DATABASE_URL 或数据库中还没有数据。";
    $("#reports-table-body").innerHTML = "";
  }
}

function renderReports(payload) {
  const tbody = $("#reports-table-body");
  tbody.innerHTML = "";
  if (!payload.length) {
    $("#reports-state").textContent = "当前没有符合条件的报告。";
    return;
  }
  $("#reports-state").textContent = `共 ${payload.length} 条记录，点击任意行可查看并切换下载链接。`;
  payload.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.runId = item.run_id;
    row.innerHTML = `
      <td>${item.run_id}</td>
      <td>${item.variety}</td>
      <td>${item.symbol}</td>
      <td>${item.target_date}</td>
      <td>${item.final_score ?? "-"}</td>
      <td>${item.sentiment || "-"}</td>
      <td>${item.review_passed ? "是" : "否"}</td>
    `;
    row.addEventListener("click", () => loadReportDetail(item.run_id));
    tbody.appendChild(row);
  });
}

async function loadReportDetail(runId) {
  const payload = await requestJson(`/reports/${runId}`);
  renderLatestReport(payload);
}

function renderLatestReport(payload) {
  const report = payload.final_report || {};
  const review = payload.review_result || {};
  const cards = [
    { label: "合约", value: report.symbol || payload.symbol || "-" },
    { label: "评分", value: report.final_score ?? review.total_score ?? "-" },
    { label: "情绪", value: report.sentiment || "-" },
    { label: "状态", value: review.passed ? "PASS" : "MARGINAL" },
  ];
  $("#latest-report-metrics").innerHTML = cards
    .map(
      (card) => `
        <div class="metric-card">
          <span>${card.label}</span>
          <strong>${card.value}</strong>
        </div>
      `
    )
    .join("");
  $("#report-snippet").textContent = truncate(report.content || report.summary || "未获取到正文内容。", 1200);
  if (report.markdown_url) {
    $("#download-md").href = report.markdown_url;
    $("#download-md").classList.remove("hidden");
  } else {
    $("#download-md").classList.add("hidden");
  }
  if (report.pdf_url) {
    $("#download-pdf").href = report.pdf_url;
    $("#download-pdf").classList.remove("hidden");
  } else {
    $("#download-pdf").classList.add("hidden");
  }
  if (payload.run_id) {
    state.activeRunId = payload.run_id;
  }
}

async function handleRuntimeEvent(event) {
  if (event.event_type === "subscribed") {
    return;
  }
  if (event.run_id && state.activeRunId && event.run_id !== state.activeRunId) {
    return;
  }
  if (event.event_type === "run_started") {
    $("#run-status").textContent = `开始生成 ${event.variety || ""} ${event.resolved_symbol || ""}`;
    $("#active-run-meta").textContent = `run_id: ${event.run_id}`;
    return;
  }
  if (event.event_type === "step_started") {
    $("#run-status").textContent = `正在执行：${event.step}`;
    return;
  }
  if (event.event_type === "review_round_completed") {
    const totalScore = event.payload?.total_score ?? "-";
    $("#run-status").textContent = `审核完成，第 ${event.review_round} 轮，当前得分 ${totalScore}`;
    return;
  }
  if (event.event_type === "run_completed") {
    $("#run-status").textContent = `生成完成，最终得分 ${event.payload?.final_score ?? "-"}`;
    if (event.run_id) {
      await loadReportDetail(event.run_id);
    }
    await refreshReports();
    return;
  }
  if (event.event_type === "run_failed") {
    $("#run-status").textContent = "生成失败，请查看事件日志。";
  }
}

function seedDates() {
  const today = new Date().toISOString().slice(0, 10);
  document.querySelectorAll('input[type="date"]').forEach((input) => {
    if (!input.value) {
      input.value = today;
    }
  });
}

function bindEvents() {
  $("#refresh-health").addEventListener("click", async () => {
    try {
      await refreshHealth();
    } catch (error) {
      $("#health-status").textContent = "检查失败";
    }
  });
  $("#variety-select").addEventListener("change", () => {
    syncContracts();
    setSelectionSummary();
  });
  $("#contract-select").addEventListener("change", () => {
    invalidatePreview();
    setSelectionSummary();
  });
  $("#horizon-select").addEventListener("change", () => {
    invalidatePreview();
    setSelectionSummary();
  });
  $("#focus-input").addEventListener("input", () => {
    invalidatePreview();
  });
  document.querySelectorAll(".suggestion-pill").forEach((button) => {
    button.addEventListener("click", () => {
      const addition = button.dataset.suggestion || "";
      const textarea = $("#focus-input");
      textarea.value = textarea.value ? `${textarea.value}\n${addition}` : addition;
      textarea.dispatchEvent(new Event("input"));
    });
  });
  $("#preview-request").addEventListener("click", async () => {
    try {
      await previewResearch();
    } catch (error) {
      $("#run-status").textContent = `需求梳理失败：${String(error)}`;
    }
  });
  $("#generate-report").addEventListener("click", async () => {
    try {
      await generateReport();
    } catch (error) {
      $("#run-status").textContent = `触发失败：${String(error)}`;
    }
  });
  $("#clear-focus").addEventListener("click", () => {
    $("#focus-input").value = "";
    invalidatePreview();
  });
  $("#connect-run-events").addEventListener("click", () => connectEvents("run"));
  $("#connect-batch-events").addEventListener("click", () => connectEvents("batch"));
  $("#disconnect-events").addEventListener("click", disconnectEvents);
  $("#batch-run-form").addEventListener("submit", async (event) => {
    try {
      await submitBatchRun(event);
    } catch (error) {
      $("#batch-run-result").textContent = String(error);
    }
  });
  $("#refresh-reports").addEventListener("click", refreshReports);
  $("#reports-filter-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const payload = formToObject(event.currentTarget);
    state.reportFilters = {
      symbol: payload.symbol || "",
      variety_code: payload.variety_code || "",
      target_date: payload.target_date || "",
      limit: Number(payload.limit || 12),
    };
    refreshReports();
  });
}

async function bootstrap() {
  seedDates();
  bindEvents();
  try {
    await Promise.all([refreshHealth(), loadResearchOptions(), refreshReports()]);
  } catch (error) {
    $("#health-status").textContent = "加载失败";
    $("#run-status").textContent = String(error);
  }
  connectEvents("run");
}

bootstrap();
