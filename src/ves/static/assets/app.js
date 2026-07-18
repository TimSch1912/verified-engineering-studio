const state = {
  modules: [],
  activeModule: null,
  activeCase: null,
  evidence: null,
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
    const cases = await fetchJson(`/api/modules/${encodeURIComponent(moduleId)}/cases`);
    state.activeCase = cases[0];
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
  el("review-result").className = "review-result empty";
  el("review-result").innerHTML =
    "<p>Run the review to see deterministic checks, a structured verdict and provenance.</p>";
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
  el("review-result").className = "review-result";
  el("review-result").innerHTML = `
    <div class="verdict-head">
      <span class="verdict-status ${escapeHtml(verdict.status)}">${escapeHtml(verdict.status)}</span>
      <span class="verdict-mode">${escapeHtml(provenance.mode)} · ${escapeHtml(provenance.model)}</span>
    </div>
    <p class="review-summary">${escapeHtml(verdict.summary)}</p>
    <div class="finding-list">
      ${verdict.findings
        .map(
          (finding) => `
            <article class="finding ${escapeHtml(finding.severity)}">
              <strong>${escapeHtml(finding.title)}</strong>
              <p>${escapeHtml(finding.detail)}</p>
            </article>`,
        )
        .join("")}
    </div>
    <strong>Next actions</strong>
    <ol class="next-actions">
      ${verdict.next_actions.map((action) => `<li>${escapeHtml(action)}</li>`).join("")}
    </ol>
    <div class="review-provenance">evidence sha256 · ${escapeHtml(provenance.evidence_sha256)}</div>`;
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
  }
}

async function init() {
  el("review-button").addEventListener("click", runReview);
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

