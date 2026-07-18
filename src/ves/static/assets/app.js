const state = {
  modules: [],
  activeModule: null,
  activeCase: null,
  evidence: null,
  reviewPrompts: [],
  reviewStatus: null,
};

const el = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function stateLabel(value) {
  return value === "ready" ? "Ready" : value === "preview" ? "Preview" : "Handoff pending";
}

function fallbackReasonLabel(value) {
  const labels = {
    not_configured: "API credential pending",
    client_limit: "visitor live limit reached",
    daily_limit: "daily live budget reached",
    busy: "live reviewer busy",
    guard_error: "cost guard unavailable",
    api_error: "live API error",
  };
  return labels[value] || "deterministic fallback";
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

function renderModuleCards() {
  el("module-cards").innerHTML = state.modules
    .map(
      (module) => `
        <article class="module-card" style="--module-accent:${escapeHtml(module.accent)}">
          <div class="module-card-head">
            <span class="module-icon">${escapeHtml(module.icon)}</span>
            <span class="state-label">${escapeHtml(stateLabel(module.state))}</span>
          </div>
          <h3>${escapeHtml(module.title)}</h3>
          <p>${escapeHtml(module.description)}</p>
          <div class="capabilities">
            ${module.capabilities.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
          </div>
        </article>`,
    )
    .join("");
}

function renderTabs() {
  el("module-tabs").innerHTML = state.modules
    .map(
      (module) => `
        <button
          type="button"
          class="module-tab ${state.activeModule?.id === module.id ? "active" : ""}"
          data-module="${escapeHtml(module.id)}"
          style="--tab-accent:${escapeHtml(module.accent)}"
        >
          <span class="tab-icon">${escapeHtml(module.icon)}</span>
          <span>${escapeHtml(module.short_title)}</span>
        </button>`,
    )
    .join("");
  document.querySelectorAll(".module-tab").forEach((button) => {
    button.addEventListener("click", () => selectModule(button.dataset.module));
  });
}

async function selectModule(moduleId) {
  state.activeModule = state.modules.find((module) => module.id === moduleId);
  renderTabs();
  el("review-result").className = "review-result empty";
  el("review-result").innerHTML = "<p>Loading the selected evidence bundle…</p>";
  try {
    const [cases, reviewPrompts] = await Promise.all([
      fetchJson(`/api/modules/${encodeURIComponent(moduleId)}/cases`),
      fetchJson(`/api/modules/${encodeURIComponent(moduleId)}/review-prompts`),
    ]);
    state.activeCase = cases[0];
    state.reviewPrompts = reviewPrompts;
    state.evidence = await fetchJson(
      `/api/modules/${encodeURIComponent(moduleId)}/cases/${encodeURIComponent(state.activeCase.id)}/evidence`,
    );
    renderCase();
  } catch (error) {
    el("review-result").innerHTML = `<p>${escapeHtml(error.message)}</p>`;
  }
}

function renderCase() {
  const module = state.activeModule;
  const caseInfo = state.activeCase;
  const evidence = state.evidence;
  el("case-discipline").textContent = module.discipline;
  el("case-title").textContent = caseInfo.title;
  el("case-summary").textContent = caseInfo.summary;
  el("case-package-digest").textContent = caseInfo.package_sha256
    ? `package sha256 · ${caseInfo.package_sha256}`
    : "";
  el("case-package-digest").title = caseInfo.package_sha256 || "";
  el("case-state").textContent = stateLabel(caseInfo.state);
  el("case-state").className = `status-chip ${caseInfo.state === "ready" ? "" : "preview"}`;

  el("metric-grid").innerHTML = evidence.metrics
    .slice(0, 8)
    .map(
      (metric) => `
        <article class="metric-card" title="${escapeHtml(metric.source)}">
          <small>${escapeHtml(metric.label)}</small>
          <strong>${escapeHtml(metric.display)}</strong>
        </article>`,
    )
    .join("");

  el("artifact-count").textContent = `${evidence.artifacts.length} artifacts`;
  el("artifacts").innerHTML = evidence.artifacts.map(renderArtifact).join("");
  el("evidence-provenance").innerHTML = Object.entries(evidence.provenance)
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("");
  el("method-references").innerHTML = evidence.references.length
    ? evidence.references.map(renderMethodReference).join("")
    : "<p>No method references supplied.</p>";
  renderReviewPrompts();
  el("review-result").className = "review-result empty";
  el("review-result").innerHTML =
    "<p>Run the review to see deterministic checks, a structured verdict and provenance.</p>";
}

function renderMethodReference(reference) {
  const title = reference.url
    ? `<a href="${escapeHtml(reference.url)}" target="_blank" rel="noreferrer">${escapeHtml(reference.title)} ↗</a>`
    : escapeHtml(reference.title);
  return `
    <article class="method-reference">
      <span>${escapeHtml(reference.id)}</span>
      <strong>${title}</strong>
      <p>${escapeHtml(reference.citation)}</p>
      <small>${escapeHtml(reference.scope)}</small>
    </article>`;
}

function renderReviewPrompts() {
  const prompts = state.reviewPrompts || [];
  el("review-prompts").innerHTML = prompts
    .map(
      (prompt, index) => `
        <button type="button" class="review-prompt ${index === 0 ? "active" : ""}" data-prompt="${escapeHtml(prompt.id)}">
          ${escapeHtml(prompt.label)}
        </button>`,
    )
    .join("");
  if (prompts.length) el("review-question").value = prompts[0].question;
  document.querySelectorAll(".review-prompt").forEach((button) => {
    button.addEventListener("click", () => {
      const prompt = prompts.find((item) => item.id === button.dataset.prompt);
      if (!prompt) return;
      el("review-question").value = prompt.question;
      document.querySelectorAll(".review-prompt").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
    });
  });
}

function renderArtifact(artifact) {
  const copy = `
    <div class="artifact-copy">
      <strong>${escapeHtml(artifact.title)}</strong>
      <small>${escapeHtml(artifact.caption)}</small>
    </div>`;
  if (artifact.kind === "image") {
    return `<article class="artifact"><img src="${escapeHtml(artifact.href)}" alt="${escapeHtml(artifact.title)}" loading="lazy" />${copy}</article>`;
  }
  if (artifact.kind === "video") {
    return `<article class="artifact"><video src="${escapeHtml(artifact.href)}" muted loop controls preload="metadata"></video>${copy}</article>`;
  }
  return `
    <a class="artifact artifact-link" href="${escapeHtml(artifact.href)}" target="_blank" rel="noreferrer">
      <span>↗</span>
      <strong>${escapeHtml(artifact.title)}</strong>
      <small>${escapeHtml(artifact.caption)}</small>
    </a>`;
}

function renderReview(payload) {
  const verdict = payload.verdict;
  const provenance = payload.provenance;
  const modeParts = [provenance.mode, provenance.model];
  if (provenance.cache_hit) modeParts.push("cache hit");
  if (provenance.fallback_reason) {
    modeParts.push(fallbackReasonLabel(provenance.fallback_reason));
  }
  el("review-result").className = "review-result";
  el("review-result").innerHTML = `
    <div class="verdict-head">
      <span class="verdict-status ${escapeHtml(verdict.status)}">${escapeHtml(verdict.status)}</span>
      <span class="verdict-mode">${escapeHtml(modeParts.join(" · "))}</span>
    </div>
    <p class="review-summary">${escapeHtml(verdict.summary)}</p>
    <div class="review-section-head">
      <strong>Deterministic gates</strong>
      <span>${payload.checks.filter((check) => check.status === "pass").length}/${payload.checks.length} pass</span>
    </div>
    <div class="check-list">
      ${payload.checks.map(renderCheck).join("")}
    </div>
    <div class="review-section-head"><strong>Structured findings</strong></div>
    <div class="finding-list">
      ${verdict.findings
        .map(
          (finding) => `
            <article class="finding ${escapeHtml(finding.severity)}">
              <strong>${escapeHtml(finding.title)}</strong>
              <p>${escapeHtml(finding.detail)}</p>
              ${renderReferenceChips(finding.evidence_refs)}
            </article>`,
        )
        .join("")}
    </div>
    ${
      verdict.caveats.length
        ? `<strong>Caveats</strong><ul class="caveat-list">${verdict.caveats
            .map((caveat) => `<li>${escapeHtml(caveat)}</li>`)
            .join("")}</ul>`
        : ""
    }
    <strong>Next actions</strong>
    <ol class="next-actions">
      ${verdict.next_actions.map((action) => `<li>${escapeHtml(action)}</li>`).join("")}
    </ol>
    <div class="review-provenance">evidence sha256 · ${escapeHtml(provenance.evidence_sha256)}</div>`;
}

function renderCheck(check) {
  const references = (check.method_refs || [])
    .map((id) => state.evidence.references.find((reference) => reference.id === id))
    .filter(Boolean);
  return `
    <article class="check ${escapeHtml(check.status)}">
      <div class="check-title">
        <span>${escapeHtml(check.status)}</span>
        <strong>${escapeHtml(check.title)}</strong>
      </div>
      <p>${escapeHtml(check.detail)}</p>
      ${renderReferenceChips(check.evidence_refs)}
      ${
        references.length
          ? `<small class="method-citation">Method · ${references
              .map((reference) => escapeHtml(reference.citation))
              .join(" · ")}</small>`
          : ""
      }
    </article>`;
}

function renderReferenceChips(references) {
  if (!references || !references.length) return "";
  return `<div class="reference-chips">${references
    .map((reference) => `<span>${escapeHtml(reference)}</span>`)
    .join("")}</div>`;
}

async function refreshReviewStatus() {
  try {
    const status = await fetchJson("/api/review/status");
    state.reviewStatus = status;
    if (status.live_ai_available) {
      el("review-mode-chip").textContent = `${status.model} live + gates`;
      el("review-availability").textContent =
        "Live AI is available. Successful identical reviews are cached to avoid duplicate cost.";
      el("review-availability").className = "review-availability live";
    } else {
      el("review-mode-chip").textContent = "Deterministic gates available";
      el("review-availability").textContent =
        `Live AI: ${fallbackReasonLabel(status.reason)}. The cost-safe deterministic review remains available.`;
      el("review-availability").className = "review-availability fallback";
    }
  } catch (_error) {
    el("review-mode-chip").textContent = "Fail-closed review";
    el("review-availability").textContent =
      "Live availability could not be confirmed. Deterministic gates remain available.";
    el("review-availability").className = "review-availability fallback";
  }
}

async function runReview() {
  if (!state.activeModule || !state.activeCase) return;
  const button = el("review-button");
  button.disabled = true;
  button.textContent = "Reviewing evidence…";
  el("review-result").className = "review-result empty";
  el("review-result").innerHTML = "<p>Running deterministic gates and preparing the structured verdict…</p>";
  try {
    const payload = await fetchJson("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        module_id: state.activeModule.id,
        case_id: state.activeCase.id,
        question: el("review-question").value,
      }),
    });
    renderReview(payload);
  } catch (error) {
    el("review-result").innerHTML = `<p>${escapeHtml(error.message)}</p>`;
  } finally {
    button.disabled = false;
    button.textContent = "Run verified review";
    refreshReviewStatus();
  }
}

async function init() {
  el("review-button").addEventListener("click", runReview);
  refreshReviewStatus();
  try {
    state.modules = await fetchJson("/api/modules");
    renderModuleCards();
    const initial = state.modules.find((module) => module.id === "cfd") || state.modules[0];
    await selectModule(initial.id);
  } catch (error) {
    el("module-cards").innerHTML = `<p>${escapeHtml(error.message)}</p>`;
  }
}

init();
