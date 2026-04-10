const state = {
  websocket: null,
  selectedRunIds: new Set(),
  currentRunId: "",
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

function formatTimestamp(value) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString("zh-CN", { hour12: false });
}

function estimateTokensFromText(text) {
  if (!text) {
    return 0;
  }
  return Math.max(1, Math.round(text.length / 1.6));
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
    cache: "no-store",
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

function appendEventCard(target, payload) {
  const card = document.createElement("article");
  card.className = "event-card";

  const header = document.createElement("div");
  header.className = "event-card-header";

  const title = document.createElement("strong");
  title.textContent = payload.event_type || "event";

  const meta = document.createElement("span");
  const metaParts = [];
  if (payload.channel) {
    metaParts.push(`channel=${payload.channel}`);
  }
  if (payload.step) {
    metaParts.push(`step=${payload.step}`);
  }
  if (payload.run_id) {
    metaParts.push(`run_id=${payload.run_id}`);
  }
  if (payload.batch_id) {
    metaParts.push(`batch_id=${payload.batch_id}`);
  }
  meta.textContent = metaParts.join(" | ") || "实时事件";

  const body = document.createElement("pre");
  body.className = "event-card-body";
  body.textContent = pretty(payload);

  header.append(title, meta);
  card.append(header, body);
  target.prepend(card);
}

async function refreshHealth() {
  const payload = await requestJson("/healthz");
  $("#health-status").textContent = payload.status === "ok" ? "在线" : pretty(payload);
  $("#storage-status").textContent = payload.storage_enabled ? "已开启" : "未配置";
  $("#model-status").textContent = `${payload.llm_model} @ ${payload.llm_base_url}`;
  const suffix = payload.process_id ? ` (PID ${payload.process_id})` : "";
  $("#started-at-status").textContent = `${formatTimestamp(payload.started_at)}${suffix}`;
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
    try {
      appendEventCard(log, JSON.parse(event.data));
    } catch (error) {
      appendEventCard(log, { event_type: "invalid_event", raw: event.data });
    }
  };

  state.websocket.onerror = () => {
    appendEventCard(log, { event_type: "websocket_error", message: "连接发生异常" });
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

function updateSelectAllState(rows) {
  const selectable = rows.filter((item) => item.run_id);
  const allChecked = selectable.length > 0 && selectable.every((item) => state.selectedRunIds.has(item.run_id));
  $("#select-all-reports").checked = allChecked;
}

function renderReports(payload) {
  const tbody = $("#reports-table-body");
  tbody.innerHTML = "";
  if (!payload.length) {
    $("#reports-state").textContent = "当前没有符合条件的报告。";
    $("#select-all-reports").checked = false;
    return;
  }

  $("#reports-state").textContent = `共 ${payload.length} 条记录，已选 ${state.selectedRunIds.size} 条。`;

  payload.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.runId = item.run_id;

    const checkboxCell = document.createElement("td");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selectedRunIds.has(item.run_id);
    checkbox.addEventListener("click", (event) => event.stopPropagation());
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        state.selectedRunIds.add(item.run_id);
      } else {
        state.selectedRunIds.delete(item.run_id);
      }
      $("#reports-state").textContent = `共 ${payload.length} 条记录，已选 ${state.selectedRunIds.size} 条。`;
      updateSelectAllState(payload);
    });
    checkboxCell.appendChild(checkbox);

    row.innerHTML = `
      <td class="cell-run-id">${item.run_id}</td>
      <td>${item.variety}</td>
      <td>${item.symbol}</td>
      <td>${formatTimestamp(item.generated_at)}</td>
      <td>${item.target_date}</td>
      <td>${item.final_score ?? "-"}</td>
      <td>${item.estimated_tokens ?? "-"}</td>
      <td>${item.sentiment || "-"}</td>
      <td>${item.review_passed ? "是" : "否"}</td>
    `;
    row.prepend(checkboxCell);
    row.addEventListener("click", () => loadReportDetail(item.run_id));
    tbody.appendChild(row);
  });

  updateSelectAllState(payload);
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
    $("#current-run-id").textContent = "-";
  }
}

function renderDetailStats(payload) {
  const report = payload.final_report || {};
  const content = report.content || payload.report_draft || "";
  $("#detail-generated-at").textContent = formatTimestamp(report.generated_at);
  $("#detail-char-count").textContent = content ? String(content.length) : "-";
  $("#detail-estimated-tokens").textContent = content ? String(estimateTokensFromText(content)) : "-";
  $("#detail-review-rounds").textContent = report.review_rounds ?? payload.review_round ?? "-";
}

async function loadReportDetail(runId) {
  const payload = await requestJson(`/reports/${runId}`);
  state.currentRunId = payload.run_id || runId;
  $("#current-run-id").textContent = state.currentRunId;
  $("#report-detail").textContent = pretty(payload);
  renderDetailStats(payload);
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

async function deleteCurrentReport() {
  if (!state.currentRunId) {
    $("#reports-state").textContent = "请先点击一条报告，再执行删除当前。";
    return;
  }
  await requestJson(`/reports/${state.currentRunId}`, { method: "DELETE" });
  state.selectedRunIds.delete(state.currentRunId);
  clearReportDetail();
  await refreshReports();
}

async function deleteSelectedReports() {
  const runIds = Array.from(state.selectedRunIds);
  if (!runIds.length) {
    $("#reports-state").textContent = "请先勾选至少一条报告。";
    return;
  }
  await requestJson("/reports/delete-batch", {
    method: "POST",
    body: JSON.stringify({ run_ids: runIds }),
  });
  if (state.currentRunId && state.selectedRunIds.has(state.currentRunId)) {
    clearReportDetail();
  }
  state.selectedRunIds.clear();
  await refreshReports();
}

function clearReportDetail() {
  state.currentRunId = "";
  $("#report-detail").textContent = "";
  $("#current-run-id").textContent = "-";
  $("#detail-generated-at").textContent = "-";
  $("#detail-char-count").textContent = "-";
  $("#detail-estimated-tokens").textContent = "-";
  $("#detail-review-rounds").textContent = "-";
  $("#open-report-pdf").classList.add("hidden");
  $("#open-report-md").classList.add("hidden");
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
  $("#delete-selected-reports").addEventListener("click", async () => {
    try {
      await deleteSelectedReports();
    } catch (error) {
      $("#reports-state").textContent = `批量删除失败：${String(error)}`;
    }
  });
  $("#delete-current-report").addEventListener("click", async () => {
    try {
      await deleteCurrentReport();
    } catch (error) {
      $("#reports-state").textContent = `删除当前失败：${String(error)}`;
    }
  });
  $("#select-all-reports").addEventListener("change", (event) => {
    const checked = event.currentTarget.checked;
    document.querySelectorAll("#reports-table-body tr").forEach((row) => {
      const runId = row.dataset.runId;
      const checkbox = row.querySelector('input[type="checkbox"]');
      if (!runId || !checkbox) {
        return;
      }
      checkbox.checked = checked;
      if (checked) {
        state.selectedRunIds.add(runId);
      } else {
        state.selectedRunIds.delete(runId);
      }
    });
  });
  $("#clear-events").addEventListener("click", () => {
    $("#events-log").innerHTML = "";
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
    clearReportDetail();
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
    $("#started-at-status").textContent = "不可用";
  }
  await refreshReports();
}

bootstrap();
