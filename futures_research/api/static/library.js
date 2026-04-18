const libraryState = {
  reports: [],
};

const $ = (selector) => document.querySelector(selector);

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

function renderLibrary(items) {
  const library = $("#report-library");
  library.innerHTML = "";
  if (!items.length) {
    library.innerHTML = '<p class="empty-state">暂无历史报告。</p>';
    return;
  }
  items.forEach((item) => {
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
    const payload = await requestJson("/reports?limit=30");
    libraryState.reports = payload;
    renderLibrary(payload);
  } catch (error) {
    $("#report-library").innerHTML = '<p class="empty-state">报告库暂不可用。</p>';
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
  const report = payload.final_report || {};
  const content = await resolveReportContent(report, payload.report_draft || "");
  $("#library-detail").classList.remove("hidden");
  $("#library-detail-title").textContent = `${payload.variety || report.variety || ""} ${payload.symbol || report.symbol || ""}`.trim() || "研报";
  $("#library-report-view").innerHTML = renderMarkdown(content);

  const md = $("#library-download-md");
  const pdf = $("#library-download-pdf");
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
  $("#library-detail").scrollIntoView({ behavior: "smooth", block: "start" });
}

$("#refresh-library").addEventListener("click", refreshLibrary);
refreshLibrary();
