const form = document.getElementById("upload-form");
const statusNode = document.getElementById("status");
const resultCard = document.getElementById("result-card");
const resultTitle = document.getElementById("result-title");
const scorePill = document.getElementById("score-pill");
const executiveSummary = document.getElementById("executive-summary");
const strengthsNode = document.getElementById("strengths");
const findingsNode = document.getElementById("findings");
const actionsNode = document.getElementById("actions");
const downloadsNode = document.getElementById("downloads");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("file-input");
  const file = fileInput.files[0];

  if (!file) {
    statusNode.textContent = "请先选择文件。";
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  statusNode.textContent = "正在评审，请稍候...";
  resultCard.classList.add("hidden");

  try {
    const response = await fetch("/api/reviews", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "评审失败");
    }

    renderResult(file.name, payload);
    statusNode.textContent = "评审完成，可以下载 Markdown / PDF 结果。";
  } catch (error) {
    statusNode.textContent = error.message || "上传失败";
  }
});

function renderResult(filename, payload) {
  resultCard.classList.remove("hidden");
  resultTitle.textContent = `${filename} | ${payload.status.toUpperCase()}`;
  scorePill.textContent = `${payload.overall_score.toFixed(1)} / 100`;
  scorePill.dataset.status = payload.status;
  executiveSummary.textContent = payload.executive_summary;

  strengthsNode.innerHTML = "";
  for (const item of payload.strengths || []) {
    const li = document.createElement("li");
    li.textContent = item;
    strengthsNode.appendChild(li);
  }

  findingsNode.innerHTML = "";
  for (const item of payload.findings || []) {
    const article = document.createElement("article");
    article.className = "finding";
    article.innerHTML = `
      <div class="finding-head">
        <span class="badge" data-severity="${item.severity}">${item.severity.toUpperCase()}</span>
        <strong>${escapeHtml(item.title)}</strong>
      </div>
      <p>${escapeHtml(item.detail)}</p>
      <p><b>建议：</b>${escapeHtml(item.recommendation)}</p>
      <p><b>目标章节：</b>${escapeHtml((item.target_sections || []).join(", ") || "N/A")}</p>
    `;
    findingsNode.appendChild(article);
  }

  actionsNode.innerHTML = "";
  for (const item of payload.improvement_actions || []) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${escapeHtml(item.title)}</strong>：${escapeHtml(item.action)}`;
    actionsNode.appendChild(li);
  }

  downloadsNode.innerHTML = "";
  for (const [key, url] of Object.entries(payload.download_urls || {})) {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.textContent = `下载 ${key.toUpperCase()}`;
    anchor.className = "download-link";
    downloadsNode.appendChild(anchor);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
