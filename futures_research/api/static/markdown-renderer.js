(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function safeHref(value) {
    const href = String(value || "").trim();
    if (/^(https?:|mailto:|\/)/i.test(href)) {
      return escapeHtml(href);
    }
    return "#";
  }

  function renderInlineText(value) {
    const parts = String(value || "").split(/(`[^`]*`)/g);
    return parts
      .map((part) => {
        if (part.startsWith("`") && part.endsWith("`")) {
          return `<code>${escapeHtml(part.slice(1, -1))}</code>`;
        }
        let html = escapeHtml(part);
        html = html.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)/g, (_match, label, href) => {
          return `<a href="${safeHref(href)}" target="_blank" rel="noreferrer">${label}</a>`;
        });
        html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        html = html.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
        return html;
      })
      .join("");
  }

  function splitTableRow(line) {
    const text = String(line || "").trim().replace(/^\|/, "").replace(/\|$/, "");
    const cells = [];
    let current = "";
    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      const previous = text[index - 1];
      if (char === "|" && previous !== "\\") {
        cells.push(current.replaceAll("\\|", "|").trim());
        current = "";
      } else {
        current += char;
      }
    }
    cells.push(current.replaceAll("\\|", "|").trim());
    return cells;
  }

  function isTableDivider(line) {
    const cells = splitTableRow(line);
    return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.trim()));
  }

  function alignmentFor(cell) {
    const value = String(cell || "").trim();
    if (value.startsWith(":") && value.endsWith(":")) {
      return "center";
    }
    if (value.endsWith(":")) {
      return "right";
    }
    return "left";
  }

  function renderTable(header, divider, rows) {
    const aligns = divider.map(alignmentFor);
    const width = Math.max(header.length, ...rows.map((row) => row.length));
    const headerHtml = Array.from({ length: width }, (_unused, index) => {
      const align = aligns[index] || "left";
      return `<th style="text-align:${align}">${renderInlineText(header[index] || "")}</th>`;
    }).join("");
    const bodyHtml = rows
      .map((row) => {
        const cells = Array.from({ length: width }, (_unused, index) => {
          const align = aligns[index] || "left";
          return `<td style="text-align:${align}">${renderInlineText(row[index] || "")}</td>`;
        }).join("");
        return `<tr>${cells}</tr>`;
      })
      .join("");
    return `<div class="md-table-wrap"><table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`;
  }

  function render(markdown) {
    const lines = normalizeDisplayMarkdown(markdown).replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let paragraph = [];
    let listType = "";
    let inCode = false;
    let codeLines = [];

    const closeList = () => {
      if (listType) {
        html.push(`</${listType}>`);
        listType = "";
      }
    };

    const flushParagraph = () => {
      if (paragraph.length) {
        html.push(`<p>${renderInlineText(paragraph.join(" "))}</p>`);
        paragraph = [];
      }
    };

    const flushCode = () => {
      html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
      codeLines = [];
    };

    for (let index = 0; index < lines.length; index += 1) {
      const rawLine = lines[index];
      const line = rawLine.trimEnd();
      const trimmed = line.trim();

      if (inCode) {
        if (/^(```|~~~)/.test(trimmed)) {
          flushCode();
          inCode = false;
        } else {
          codeLines.push(rawLine);
        }
        continue;
      }

      if (/^(```|~~~)/.test(trimmed)) {
        flushParagraph();
        closeList();
        inCode = true;
        codeLines = [];
        continue;
      }

      if (!trimmed) {
        flushParagraph();
        closeList();
        continue;
      }

      if (trimmed.startsWith("<!--")) {
        flushParagraph();
        closeList();
        continue;
      }

      const tableCandidate = line.includes("|") && lines[index + 1] && isTableDivider(lines[index + 1]);
      if (tableCandidate) {
        flushParagraph();
        closeList();
        const header = splitTableRow(line);
        const divider = splitTableRow(lines[index + 1]);
        const rows = [];
        index += 2;
        while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
          if (!isTableDivider(lines[index])) {
            rows.push(splitTableRow(lines[index]));
          }
          index += 1;
        }
        index -= 1;
        html.push(renderTable(header, divider, rows));
        continue;
      }

      const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        flushParagraph();
        closeList();
        const level = Math.min(heading[1].length, 4);
        html.push(`<h${level}>${renderInlineText(heading[2])}</h${level}>`);
        continue;
      }

      if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
        flushParagraph();
        closeList();
        html.push("<hr />");
        continue;
      }

      if (trimmed.startsWith(">")) {
        flushParagraph();
        closeList();
        const quoteLines = [];
        while (index < lines.length && lines[index].trim().startsWith(">")) {
          quoteLines.push(lines[index].trim().replace(/^>\s?/, ""));
          index += 1;
        }
        index -= 1;
        html.push(`<blockquote>${quoteLines.map(renderInlineText).join("<br />")}</blockquote>`);
        continue;
      }

      const unordered = trimmed.match(/^[-*+]\s+(.+)$/);
      const ordered = trimmed.match(/^\d+\.\s+(.+)$/);
      if (unordered || ordered) {
        flushParagraph();
        const nextListType = ordered ? "ol" : "ul";
        if (listType !== nextListType) {
          closeList();
          listType = nextListType;
          html.push(`<${listType}>`);
        }
        html.push(`<li>${renderInlineText((unordered || ordered)[1])}</li>`);
        continue;
      }

      closeList();
      paragraph.push(trimmed);
    }

    if (inCode) {
      flushCode();
    }
    flushParagraph();
    closeList();
    return html.join("");
  }

  function normalizeDisplayMarkdown(markdown) {
    const lines = String(markdown || "").split(/\r?\n/);
    const visible = [];
    let skippingConstraintSection = "";
    let skippingHtmlComment = false;
    for (const line of lines) {
      const trimmed = line.trim();
      if (skippingHtmlComment) {
        if (trimmed.includes("-->")) {
          skippingHtmlComment = false;
        }
        continue;
      }
      if (trimmed.startsWith("<!--")) {
        if (!trimmed.includes("-->")) {
          skippingHtmlComment = true;
        }
        continue;
      }
      if (/^##\s+七、数据说明与待补充项/.test(trimmed)) {
        skippingConstraintSection = "section";
        continue;
      }
      if (trimmed === "写作约束：") {
        skippingConstraintSection = "constraint";
        continue;
      }
      if (skippingConstraintSection) {
        const canResume =
          /^#{1,6}\s+/.test(trimmed) ||
          trimmed === "---" ||
          (skippingConstraintSection === "constraint" && !trimmed);
        if (canResume) {
          skippingConstraintSection = "";
        } else {
          continue;
        }
      }
      if (/^\d+\.\s+\*\*研究边界\*\*/.test(trimmed)) {
        continue;
      }
      visible.push(line);
    }
    return visible.join("\n");
  }

  window.ConsumerMarkdownRenderer = { render };
})();
