const consumerState = {
  websocket: null,
  activeRunId: "",
  activeReport: null,
  library: [],
  varieties: [],
  pickerKind: "",
};

const $ = (selector) => document.querySelector(selector);

const STEP_ORDER = ["aggregate", "analyze", "write", "review"];
const STEP_COPY = {
  aggregate: {
    title: "正在整理行情数据",
    detail: "正在核对合约、行情和可用来源。",
  },
  analyze: {
    title: "正在形成研究观点",
    detail: "正在把价格、基差、外盘和基本面线索合成判断。",
  },
  write: {
    title: "正在撰写研报",
    detail: "正在把结论写成便于阅读的研究报告。",
  },
  review: {
    title: "正在检查风险",
    detail: "正在检查证据、风险提示和表达边界。",
  },
};

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
  return window.ConsumerMarkdownRenderer.render(markdown);
}

function setSubmitDisabled(disabled) {
  const button = $("#start-research");
  if (!button) {
    return;
  }
  button.disabled = disabled;
  button.textContent = disabled ? "研究中..." : "开始研究";
}

function setResearchStatus(kind, title, detail) {
  const status = $("#research-status");
  const spinner = $("#status-spinner");
  status.classList.remove("idle", "running", "done", "failed");
  status.classList.add(kind);
  $("#run-status").textContent = title;
  $("#status-detail").textContent = detail || "";
  spinner.classList.toggle("hidden", kind !== "running");
}

function setStep(step, state) {
  const index = STEP_ORDER.indexOf(step);
  document.querySelectorAll("#progress-steps span").forEach((item) => {
    const itemIndex = STEP_ORDER.indexOf(item.dataset.step);
    item.classList.remove("active", "done");
    if (state === "active" && itemIndex >= 0 && itemIndex < index) {
      item.classList.add("done");
    }
  });
  const item = document.querySelector(`[data-step="${step}"]`);
  if (item) {
    item.classList.add(state);
  }
}

function resetSteps() {
  document.querySelectorAll("#progress-steps span").forEach((item) => {
    item.classList.remove("active", "done");
  });
}

function completeSteps() {
  document.querySelectorAll("#progress-steps span").forEach((item) => {
    item.classList.remove("active");
    item.classList.add("done");
  });
}

function handleRuntimeEvent(payload) {
  if (payload.event_type === "run_started") {
    consumerState.activeRunId = payload.run_id || consumerState.activeRunId;
    setResearchStatus("running", "研究开始了", "正在为你准备数据和研究框架。");
    setSubmitDisabled(true);
    return;
  }
  if (payload.event_type === "step_started" && payload.step) {
    const copy = STEP_COPY[payload.step] || STEP_COPY.aggregate;
    setStep(payload.step, "active");
    setResearchStatus("running", copy.title, copy.detail);
    return;
  }
  if (payload.event_type === "review_round_completed") {
    setStep("review", "done");
    if (payload.payload?.passed) {
      setResearchStatus("running", "质量检查通过", "正在整理最终研报。");
    } else {
      setResearchStatus("running", "正在补充修订", "发现需要补足的地方，正在自动完善。");
    }
    return;
  }
  if (payload.event_type === "run_failed") {
    setResearchStatus("failed", "研究任务失败", "请稍后重试，后台运行日志里可以查看详细原因。");
    setSubmitDisabled(false);
  }
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
    handleRuntimeEvent(payload);
    if (payload.event_type === "run_completed") {
      consumerState.activeRunId = payload.run_id || consumerState.activeRunId;
      completeSteps();
      setResearchStatus("done", "研报生成完成", "可以滚动阅读正文。");
      setSubmitDisabled(false);
      if (consumerState.activeRunId) {
        await loadReport(consumerState.activeRunId);
      }
    }
  };
  consumerState.websocket.onclose = () => {
    consumerState.websocket = null;
  };
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

function renderPickerOptions() {
  const options = $("#picker-options");
  const search = $("#picker-search").value.trim().toLowerCase();
  options.innerHTML = "";

  if (consumerState.pickerKind === "symbol") {
    const selectedCode = $("#symbol-select").value;
    const matches = consumerState.varieties.filter((item) => {
      const haystack = `${item.name} ${item.code} ${item.exchange}`.toLowerCase();
      return !search || haystack.includes(search);
    });
    if (!matches.length) {
      options.innerHTML = '<p class="picker-empty">没有找到匹配品种。</p>';
      return;
    }
    matches.forEach((item) => {
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
    return;
  }

  const variety = selectedVariety();
  if (!variety) {
    options.innerHTML = '<p class="picker-empty">暂无可选合约。</p>';
    return;
  }
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

function openPickerModal(kind) {
  const modal = $("#picker-modal");
  const title = $("#picker-modal-title");
  const searchWrap = $("#picker-search-wrap");
  const searchInput = $("#picker-search");
  consumerState.pickerKind = kind;
  searchInput.value = "";

  if (kind === "symbol") {
    title.textContent = "选择品种";
    searchWrap.classList.remove("hidden");
    setTimeout(() => searchInput.focus(), 0);
  } else {
    const variety = selectedVariety();
    title.textContent = `选择合约 - ${variety ? varietyLabel(variety) : ""}`;
    searchWrap.classList.add("hidden");
  }
  renderPickerOptions();
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
      persona: "institution",
      user_focus: String(data.get("prompt") || "").trim(),
    },
  };
}

async function submitResearch(event) {
  event.preventDefault();
  connectEvents();
  resetSteps();
  $("#answer-empty").classList.remove("hidden");
  $("#report-shell").classList.add("hidden");
  $("#report-view").classList.add("hidden");
  $("#report-view").innerHTML = "";
  setResearchStatus("running", "正在提交研究任务", "请稍等，系统马上开始处理。");
  setSubmitDisabled(true);
  const payload = buildRunPayload(event.currentTarget);
  try {
    await requestJson("/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setResearchStatus("running", "任务已提交", "后台已经开始研究，页面会自动更新进度。");
  } catch (error) {
    setResearchStatus("failed", "提交失败", String(error.message || error));
    setSubmitDisabled(false);
  }
}

async function resolveReportContent(report, fallback) {
  if (report.content) {
    return report.content;
  }
  if (report.markdown_url) {
    try {
      const response = await fetch(report.markdown_url, { cache: "no-store" });
      if (response.ok) {
        return await response.text();
      }
    } catch (error) {
      return fallback || "";
    }
  }
  return fallback || "";
}

async function loadReport(runId) {
  const payload = await requestJson(`/reports/${runId}`);
  consumerState.activeRunId = runId;
  consumerState.activeReport = payload;
  const report = payload.final_report || {};
  const content = await resolveReportContent(report, payload.report_draft || "");
  $("#answer-empty").classList.add("hidden");
  $("#report-shell").classList.remove("hidden");
  $("#report-view").classList.remove("hidden");
  $("#report-view").innerHTML = renderMarkdown(content);

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

  setResearchStatus("done", "研报已打开", "可以滚动阅读正文。");
  setSubmitDisabled(false);
  return payload;
}

function bindConsumerEvents() {
  $("#target-date").value = todayText();
  $("#consumer-run-form").addEventListener("submit", submitResearch);
  $("#symbol-trigger").addEventListener("click", () => openPickerModal("symbol"));
  $("#contract-trigger").addEventListener("click", () => openPickerModal("contract"));
  $("#picker-close").addEventListener("click", closePickerModal);
  $("#picker-search").addEventListener("input", renderPickerOptions);
  $("#picker-modal").addEventListener("click", (event) => {
    if (event.target.id === "picker-modal") {
      closePickerModal();
    }
  });
}

bindConsumerEvents();
connectEvents();
refreshVarieties().catch(() => updateContractOptions());
