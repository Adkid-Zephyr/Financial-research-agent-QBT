const state = {
  websocket: null,
  reportFilters: {
    symbol: "",
    variety_code: "",
    target_date: "",
    limit: 20,
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

async function refreshHealth() {
  const payload = await requestJson("/healthz");
  $("#health-status").textContent = payload.status === "ok" ? "在线" : pretty(payload);
  $("#storage-status").textContent = payload.storage_enabled ? "已开启" : "未配置";
  $("#model-status").textContent = `${payload.llm_model} @ ${payload.llm_base_url}`;
}

function setOrigins() {
  $("#api-origin").textContent = window.location.origin;
  $("#ws-origin").textContent = buildWsUrl("run");
}

function disconnectEvents() {
  if (state.websocket) {
    state.websocket.close();
    state.websocket = null;
  }
  $("#event-connection-status").textContent = "当前未连接。";
}

function connectEvents(channel) {
  disconnectEvents();
  const url = buildWsUrl(channel);
  const log = $("#events-log");
  state.websocket = new WebSocket(url);
  $("#event-connection-status").textContent = `连接中：${url}`;

  state.websocket.onopen = () => {
    $("#event-connection-status").textContent = `已连接 ${channel} 事件流`;
  };

  state.websocket.onmessage = (event) => {
    appendLog(log, pretty(JSON.parse(event.data)));
  };

  state.websocket.onerror = () => {
    appendLog(log, "[WebSocket Error] 连接发生异常");
  };

  state.websocket.onclose = () => {
    $("#event-connection-status").textContent = "连接已关闭。";
    state.websocket = null;
  };
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

async function submitSingleRun(event) {
  event.preventDefault();
  const payload = formToObject(event.currentTarget);
  const result = await requestJson("/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  $("#single-run-result").textContent = pretty(result);
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

function renderReports(payload) {
  const tbody = $("#reports-table-body");
  tbody.innerHTML = "";
  if (!payload.length) {
    $("#reports-state").textContent = "当前没有符合条件的报告。";
    return;
  }
  $("#reports-state").textContent = `共 ${payload.length} 条记录，点击任意行可查看详情。`;
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
      "报告查询不可用。通常是因为尚未配置 DATABASE_URL 或数据库里还没有数据。";
    $("#reports-table-body").innerHTML = "";
    $("#report-detail").textContent = String(error);
  }
}

async function loadReportDetail(runId) {
  const payload = await requestJson(`/reports/${runId}`);
  $("#report-detail").textContent = pretty(payload);
  const report = payload.final_report || {};
  const pdfLink = $("#open-report-pdf");
  const mdLink = $("#open-report-md");
  if (report.pdf_url) {
    pdfLink.href = report.pdf_url;
    pdfLink.classList.remove("hidden");
  } else {
    pdfLink.classList.add("hidden");
  }
  if (report.markdown_url) {
    mdLink.href = report.markdown_url;
    mdLink.classList.remove("hidden");
  } else {
    mdLink.classList.add("hidden");
  }
}

function bindEvents() {
  $("#refresh-health").addEventListener("click", async () => {
    try {
      await refreshHealth();
    } catch (error) {
      $("#health-status").textContent = "检查失败";
      $("#storage-status").textContent = String(error);
    }
  });
  $("#refresh-reports").addEventListener("click", refreshReports);
  $("#refresh-reports-inline").addEventListener("click", refreshReports);
  $("#clear-events").addEventListener("click", () => {
    $("#events-log").textContent = "";
  });
  $("#connect-run-events").addEventListener("click", () => connectEvents("run"));
  $("#connect-batch-events").addEventListener("click", () => connectEvents("batch"));
  $("#disconnect-events").addEventListener("click", disconnectEvents);
  $("#single-run-form").addEventListener("submit", async (event) => {
    try {
      await submitSingleRun(event);
    } catch (error) {
      $("#single-run-result").textContent = String(error);
    }
  });
  $("#batch-run-form").addEventListener("submit", async (event) => {
    try {
      await submitBatchRun(event);
    } catch (error) {
      $("#batch-run-result").textContent = String(error);
    }
  });
  $("#reports-filter-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const payload = formToObject(event.currentTarget);
    state.reportFilters = {
      symbol: payload.symbol || "",
      variety_code: payload.variety_code || "",
      target_date: payload.target_date || "",
      limit: Number(payload.limit || 20),
    };
    refreshReports();
  });
  $("#clear-report-detail").addEventListener("click", () => {
    $("#report-detail").textContent = "";
    $("#open-report-pdf").classList.add("hidden");
    $("#open-report-md").classList.add("hidden");
  });
}

function seedDates() {
  const today = new Date().toISOString().slice(0, 10);
  document.querySelectorAll('input[type="date"]').forEach((input) => {
    if (!input.value) {
      input.value = today;
    }
  });
}

async function bootstrap() {
  setOrigins();
  seedDates();
  bindEvents();
  try {
    await refreshHealth();
  } catch (error) {
    $("#health-status").textContent = "检查失败";
    $("#storage-status").textContent = String(error);
  }
  await refreshReports();
}

bootstrap();
