const state = {
  modules: [],
  activeModule: null,
  activeCase: null,
  evidence: null,
  reviewPrompts: [],
  reviewStatus: null,
  activeArtifactId: null,
  reviewPayload: null,
  selectionToken: 0,
};

const el = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function stateLabel(value) {
  const labels = { ready: "Ready", preview: "Preview", handoff_pending: "Handoff pending" };
  return labels[value] || String(value).replaceAll("_", " ");
}

function verdictLabel(value) {
  const labels = { verified: "Verified", review: "Needs verification", blocked: "Blocked" };
  return labels[value] || value;
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

function humanizeKey(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
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
      (module, index) => `
        <button
          type="button"
          class="module-card ${state.activeModule?.id === module.id ? "active" : ""}"
          data-module="${escapeHtml(module.id)}"
          aria-pressed="${state.activeModule?.id === module.id}"
          style="--module-accent:${escapeHtml(module.accent)}"
        >
          <span class="module-number">0${index + 1}</span>
          <span class="module-card-head">
            <span class="module-icon">${escapeHtml(module.icon)}</span>
            <span class="state-label ${escapeHtml(module.state)}">${escapeHtml(stateLabel(module.state))}</span>
          </span>
          <span class="module-card-copy">
            <small>${escapeHtml(module.discipline)}</small>
            <strong>${escapeHtml(module.title)}</strong>
            <span>${escapeHtml(module.description)}</span>
          </span>
          <span class="capabilities">
            ${module.capabilities.map((item) => `<i>${escapeHtml(item.replaceAll("-", " "))}</i>`).join("")}
          </span>
          <span class="module-open">Open module <b>↗</b></span>
        </button>`,
    )
    .join("");

  document.querySelectorAll(".module-card").forEach((button) => {
    button.addEventListener("click", async () => {
      await selectModule(button.dataset.module);
      el("studio").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function renderTabs() {
  el("module-tabs").innerHTML = state.modules
    .map(
      (module) => `
        <button
          type="button"
          role="tab"
          class="module-tab ${state.activeModule?.id === module.id ? "active" : ""}"
          data-module="${escapeHtml(module.id)}"
          aria-selected="${state.activeModule?.id === module.id}"
          tabindex="${state.activeModule?.id === module.id ? "0" : "-1"}"
          style="--tab-accent:${escapeHtml(module.accent)}"
        >
          <span class="tab-icon">${escapeHtml(module.icon)}</span>
          <span>${escapeHtml(module.short_title)}</span>
          ${module.state !== "ready" ? `<small>${escapeHtml(stateLabel(module.state))}</small>` : ""}
        </button>`,
    )
    .join("");

  document.querySelectorAll(".module-tab").forEach((button) => {
    button.addEventListener("click", () => selectModule(button.dataset.module));
    button.addEventListener("keydown", (event) => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      const tabs = [...document.querySelectorAll(".module-tab")];
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(tabs.indexOf(button) + direction + tabs.length) % tabs.length];
      next.focus();
      selectModule(next.dataset.module);
    });
  });
}

function updateModuleUrl(moduleId) {
  const url = new URL(window.location.href);
  url.searchParams.set("module", moduleId);
  history.replaceState({ moduleId }, "", `${url.pathname}${url.search}${url.hash}`);
}

async function selectModule(moduleId, options = {}) {
  const module = state.modules.find((item) => item.id === moduleId);
  if (!module) return;
  const token = ++state.selectionToken;
  state.activeModule = module;
  state.reviewPayload = null;
  el("studio-shell").setAttribute("aria-busy", "true");
  renderTabs();
  renderModuleCards();
  resetReviewResult("Loading the selected evidence package…");

  try {
    const [cases, reviewPrompts] = await Promise.all([
      fetchJson(`/api/modules/${encodeURIComponent(moduleId)}/cases`),
      fetchJson(`/api/modules/${encodeURIComponent(moduleId)}/review-prompts`),
    ]);
    if (token !== state.selectionToken) return;
    if (!cases.length) throw new Error("This module does not expose a public case yet.");
    state.activeCase = cases[0];
    state.reviewPrompts = reviewPrompts;
    state.evidence = await fetchJson(
      `/api/modules/${encodeURIComponent(moduleId)}/cases/${encodeURIComponent(state.activeCase.id)}/evidence`,
    );
    if (token !== state.selectionToken) return;
    state.activeArtifactId = state.evidence.artifacts.find((artifact) => artifact.kind !== "link")?.id || null;
    renderCase();
    if (options.updateUrl !== false) updateModuleUrl(moduleId);
  } catch (error) {
    resetReviewResult(error.message, true);
  } finally {
    if (token === state.selectionToken) el("studio-shell").setAttribute("aria-busy", "false");
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
  el("case-state").className = `status-chip ${caseInfo.state}`;

  const packageProof = el("package-proof");
  if (caseInfo.package_sha256) {
    packageProof.hidden = false;
    el("case-package-digest").textContent = `${caseInfo.package_sha256.slice(0, 12)}…${caseInfo.package_sha256.slice(-8)}`;
    el("case-package-digest").title = caseInfo.package_sha256;
  } else {
    packageProof.hidden = true;
    el("case-package-digest").textContent = "";
  }

  const primaryMetrics = evidence.metrics.slice(0, Math.min(4, evidence.metrics.length));
  el("metric-grid").className = `metric-grid count-${primaryMetrics.length}`;
  el("metric-grid").innerHTML = primaryMetrics
    .map(
      (metric, index) => `
        <article class="metric-card ${index === 0 ? "featured" : ""}">
          <span class="metric-order">0${index + 1}</span>
          <small>${escapeHtml(metric.label)}</small>
          <strong>${escapeHtml(metric.display)}</strong>
          <p>${escapeHtml(metric.source)}</p>
        </article>`,
    )
    .join("");

  el("metric-count").textContent = `${evidence.metrics.length} reported ${evidence.metrics.length === 1 ? "value" : "values"}`;
  el("metric-table-body").innerHTML = evidence.metrics
    .map(
      (metric) => `
        <tr>
          <th scope="row"><code>${escapeHtml(metric.id)}</code><span>${escapeHtml(metric.label)}</span></th>
          <td><strong>${escapeHtml(metric.display)}</strong></td>
          <td>${escapeHtml(metric.source)}</td>
        </tr>`,
    )
    .join("");

  renderMediaGallery();
  el("evidence-provenance").innerHTML = Object.entries(evidence.provenance)
    .map(([key, value]) => `<dt>${escapeHtml(humanizeKey(key))}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("");
  el("method-references").innerHTML = evidence.references.length
    ? evidence.references.map(renderMethodReference).join("")
    : `<div class="reference-empty"><strong>Stable handoff pending</strong><p>Method references will be attached to the verified package when this preview is replaced.</p></div>`;
  renderReviewPrompts();
  resetReviewResult();
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

function renderMediaGallery() {
  const visuals = state.evidence.artifacts.filter((artifact) => artifact.kind !== "link");
  const links = state.evidence.artifacts.filter((artifact) => artifact.kind === "link");
  if (!visuals.some((artifact) => artifact.id === state.activeArtifactId)) {
    state.activeArtifactId = visuals[0]?.id || null;
  }

  const mediaLabel = `${visuals.length} ${visuals.length === 1 ? "medium" : "media"}`;
  const linkLabel = links.length ? ` · ${links.length} context ${links.length === 1 ? "link" : "links"}` : "";
  el("artifact-count").textContent = `${mediaLabel}${linkLabel}`;
  renderActiveArtifact();

  el("artifact-thumbnails").innerHTML = visuals
    .map((artifact, index) => {
      const preview = artifact.kind === "image"
        ? `<img src="${escapeHtml(artifact.href)}" alt="" loading="lazy" />`
        : `<span class="video-thumbnail"><b>▶</b><small>VIDEO</small></span>`;
      return `
        <button
          type="button"
          class="artifact-thumbnail ${artifact.id === state.activeArtifactId ? "active" : ""}"
          data-artifact="${escapeHtml(artifact.id)}"
          aria-pressed="${artifact.id === state.activeArtifactId}"
        >
          <span class="thumbnail-visual">${preview}<i>0${index + 1}</i></span>
          <span><strong>${escapeHtml(artifact.title)}</strong><small>${escapeHtml(artifact.kind)}</small></span>
        </button>`;
    })
    .join("");

  document.querySelectorAll(".artifact-thumbnail").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeArtifactId = button.dataset.artifact;
      renderMediaGallery();
    });
  });

  el("evidence-links").innerHTML = links
    .map(
      (artifact) => `
        <a href="${escapeHtml(artifact.href)}" target="_blank" rel="noreferrer">
          <span>↗</span>
          <div><small>EXTERNAL CONTEXT</small><strong>${escapeHtml(artifact.title)}</strong><p>${escapeHtml(artifact.caption)}</p></div>
        </a>`,
    )
    .join("");
}

function renderActiveArtifact() {
  const artifact = state.evidence.artifacts.find((item) => item.id === state.activeArtifactId);
  if (!artifact) {
    el("media-stage").innerHTML = `
      <div class="no-media"><span>◇</span><strong>No packaged media yet</strong><p>The stable handoff will populate this evidence viewer.</p></div>`;
    return;
  }

  const media = artifact.kind === "image"
    ? `<button class="stage-image-button" type="button" data-open-media aria-label="Expand ${escapeHtml(artifact.title)}"><img src="${escapeHtml(artifact.href)}" alt="${escapeHtml(artifact.title)}" /></button>`
    : `<video src="${escapeHtml(artifact.href)}" controls muted loop playsinline preload="metadata" aria-label="${escapeHtml(artifact.title)}"></video>`;
  const hash = artifact.sha256
    ? `<button class="hash-button" type="button" data-copy-artifact title="${escapeHtml(artifact.sha256)}">SHA‑256 ${escapeHtml(artifact.sha256.slice(0, 10))}… <span>Copy</span></button>`
    : "";

  el("media-stage").innerHTML = `
    <div class="stage-toolbar">
      <span>${escapeHtml(artifact.kind.toUpperCase())} · PACKAGED EVIDENCE</span>
      <button class="expand-media" type="button" data-open-media>Expand <b>↗</b></button>
    </div>
    <div class="stage-canvas">${media}</div>
    <div class="stage-caption">
      <div><strong>${escapeHtml(artifact.title)}</strong><p>${escapeHtml(artifact.caption)}</p></div>
      <div class="stage-metadata"><span>${escapeHtml(artifact.rights)}</span>${hash}</div>
    </div>`;

  el("media-stage").querySelectorAll("[data-open-media]").forEach((button) => {
    button.addEventListener("click", openMediaDialog);
  });
  el("media-stage").querySelector("[data-copy-artifact]")?.addEventListener("click", () => {
    copyText(artifact.sha256, "Artifact hash copied");
  });
}

function openMediaDialog() {
  const artifact = state.evidence.artifacts.find((item) => item.id === state.activeArtifactId);
  if (!artifact) return;
  el("media-dialog-title").textContent = artifact.title;
  el("media-dialog-caption").textContent = artifact.caption;
  el("media-dialog-content").innerHTML = artifact.kind === "video"
    ? `<video src="${escapeHtml(artifact.href)}" controls autoplay muted loop playsinline aria-label="${escapeHtml(artifact.title)}"></video>`
    : `<img src="${escapeHtml(artifact.href)}" alt="${escapeHtml(artifact.title)}" />`;
  el("media-dialog").showModal();
}

function closeMediaDialog() {
  const media = el("media-dialog-content").querySelector("video");
  if (media) media.pause();
  el("media-dialog").close();
  el("media-dialog-content").innerHTML = "";
}

async function requestMediaFullscreen() {
  const media = el("media-dialog-content").querySelector("img, video");
  if (!media?.requestFullscreen) {
    showToast("Browser fullscreen is not available here");
    return;
  }
  try {
    await media.requestFullscreen();
  } catch (_error) {
    showToast("The browser declined fullscreen mode");
  }
}

function renderReviewPrompts() {
  const prompts = state.reviewPrompts || [];
  el("review-prompts").innerHTML = prompts
    .map(
      (prompt, index) => `
        <button
          type="button"
          class="review-prompt ${index === 0 ? "active" : ""}"
          data-prompt="${escapeHtml(prompt.id)}"
          aria-pressed="${index === 0}"
        >${escapeHtml(prompt.label)}</button>`,
    )
    .join("");
  if (prompts.length) el("review-question").value = prompts[0].question;
  document.querySelectorAll(".review-prompt").forEach((button) => {
    button.addEventListener("click", () => {
      const prompt = prompts.find((item) => item.id === button.dataset.prompt);
      if (!prompt) return;
      el("review-question").value = prompt.question;
      document.querySelectorAll(".review-prompt").forEach((item) => {
        const active = item === button;
        item.classList.toggle("active", active);
        item.setAttribute("aria-pressed", active);
      });
    });
  });
}

function resetReviewResult(message = "", error = false) {
  state.reviewPayload = null;
  el("review-result").className = `review-result empty${error ? " error" : ""}`;
  el("review-result").innerHTML = `
    <div class="empty-result-icon">${error ? "!" : "↗"}</div>
    <div>
      <strong>${escapeHtml(message || "Your decision brief will appear here.")}</strong>
      ${message ? "" : "<p>Run a guided review to inspect checks, findings, caveats and provenance.</p>"}
    </div>`;
}

function uniqueModeParts(provenance) {
  const values = [provenance.mode];
  if (!String(provenance.mode).includes("fallback")) values.push(provenance.model);
  if (provenance.cache_hit) values.push("cache hit");
  if (provenance.fallback_reason) values.push(fallbackReasonLabel(provenance.fallback_reason));
  return values.filter((value, index, array) => value && array.findIndex((item) => item?.toLowerCase() === value.toLowerCase()) === index);
}

function renderReview(payload) {
  state.reviewPayload = payload;
  const verdict = payload.verdict;
  const provenance = payload.provenance;
  const passing = payload.checks.filter((check) => check.status === "pass").length;
  const caveats = verdict.caveats.length
    ? `<ul>${verdict.caveats.map((caveat) => `<li>${escapeHtml(caveat)}</li>`).join("")}</ul>`
    : "<p>No additional caveats were returned.</p>";

  el("review-result").className = "review-result";
  el("review-result").innerHTML = `
    <div class="review-result-toolbar">
      <div><span>DECISION BRIEF</span><small>${escapeHtml(uniqueModeParts(provenance).join(" · "))}</small></div>
      <div>
        <button id="copy-review" type="button">Copy Markdown</button>
        <button id="download-review" type="button">Download JSON</button>
      </div>
    </div>
    <div class="verdict-hero ${escapeHtml(verdict.status)}">
      <span class="verdict-status">${escapeHtml(verdictLabel(verdict.status))}</span>
      <div><h5>${escapeHtml(verdict.summary)}</h5><p>${passing}/${payload.checks.length} deterministic gates passed.</p></div>
    </div>
    <div class="review-output-grid">
      <section>
        <div class="result-section-heading"><span>01</span><div><strong>Deterministic gates</strong><small>Rules before language</small></div></div>
        <div class="check-list">${payload.checks.map(renderCheck).join("")}</div>
      </section>
      <section>
        <div class="result-section-heading"><span>02</span><div><strong>Structured findings</strong><small>Evidence-linked interpretation</small></div></div>
        <div class="finding-list">${verdict.findings.map(renderFinding).join("")}</div>
      </section>
    </div>
    <div class="review-conclusion-grid">
      <section><div class="result-section-heading"><span>03</span><div><strong>Caveats</strong><small>Decision boundaries</small></div></div>${caveats}</section>
      <section><div class="result-section-heading"><span>04</span><div><strong>Next actions</strong><small>Ordered verification work</small></div></div><ol>${verdict.next_actions.map((action) => `<li>${escapeHtml(action)}</li>`).join("")}</ol></section>
    </div>
    <div class="review-provenance"><span>Evidence SHA‑256</span><code>${escapeHtml(provenance.evidence_sha256)}</code></div>`;

  el("copy-review").addEventListener("click", () => copyText(reviewToMarkdown(payload), "Review copied as Markdown"));
  el("download-review").addEventListener("click", downloadReview);
  el("review-result").focus({ preventScroll: true });
  el("review-result").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCheck(check) {
  const references = (check.method_refs || [])
    .map((id) => state.evidence.references.find((reference) => reference.id === id))
    .filter(Boolean);
  return `
    <details class="check ${escapeHtml(check.status)}" ${check.status === "pass" ? "" : "open"}>
      <summary><span>${escapeHtml(check.status)}</span><strong>${escapeHtml(check.title)}</strong><i>+</i></summary>
      <div class="check-body">
        <p>${escapeHtml(check.detail)}</p>
        ${renderReferenceChips(check.evidence_refs)}
        ${references.length ? `<small class="method-citation">Method · ${references.map((reference) => escapeHtml(reference.citation)).join(" · ")}</small>` : ""}
      </div>
    </details>`;
}

function renderFinding(finding) {
  return `
    <details class="finding ${escapeHtml(finding.severity)}" ${finding.severity === "positive" ? "" : "open"}>
      <summary>
        <span>${escapeHtml(finding.severity)}</span>
        <strong>${escapeHtml(finding.title)}</strong>
        <i>+</i>
      </summary>
      <div class="finding-body">
        <p>${escapeHtml(finding.detail)}</p>
        ${renderReferenceChips(finding.evidence_refs)}
      </div>
    </details>`;
}

function renderReferenceChips(references) {
  if (!references?.length) return "";
  return `<div class="reference-chips">${references.map((reference) => `<span>${escapeHtml(reference)}</span>`).join("")}</div>`;
}

function reviewToMarkdown(payload) {
  const verdict = payload.verdict;
  const lines = [
    `# ${state.activeCase.title} — engineering review`,
    "",
    `**Status:** ${verdictLabel(verdict.status)}`,
    `**Summary:** ${verdict.summary}`,
    "",
    "## Deterministic gates",
    ...payload.checks.map((check) => `- **${check.status.toUpperCase()} — ${check.title}:** ${check.detail}`),
    "",
    "## Findings",
    ...verdict.findings.map((finding) => `- **${finding.title}:** ${finding.detail}`),
    "",
    "## Caveats",
    ...verdict.caveats.map((caveat) => `- ${caveat}`),
    "",
    "## Next actions",
    ...verdict.next_actions.map((action, index) => `${index + 1}. ${action}`),
    "",
    `Evidence SHA-256: ${payload.provenance.evidence_sha256}`,
  ];
  return lines.join("\n");
}

function downloadReview() {
  if (!state.reviewPayload) return;
  const blob = new Blob([JSON.stringify(state.reviewPayload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${state.activeModule.id}-${state.activeCase.id}-review.json`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  showToast("Review JSON downloaded");
}

async function copyText(value, message) {
  try {
    await navigator.clipboard.writeText(value);
    showToast(message);
  } catch (_error) {
    const area = document.createElement("textarea");
    area.value = value;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    showToast(message);
  }
}

let toastTimer;
function showToast(message) {
  clearTimeout(toastTimer);
  el("toast").textContent = message;
  el("toast").classList.add("show");
  toastTimer = setTimeout(() => el("toast").classList.remove("show"), 2400);
}

async function refreshReviewStatus() {
  try {
    const status = await fetchJson("/api/review/status");
    state.reviewStatus = status;
    if (status.live_ai_available) {
      el("review-mode-chip").textContent = `${status.model} live + gates`;
      el("review-availability").textContent = "Live reviewer available · identical successful reviews are cached to control cost.";
      el("review-availability").className = "review-availability live";
    } else {
      el("review-mode-chip").textContent = "Deterministic gates available";
      el("review-availability").textContent = `Live reviewer: ${fallbackReasonLabel(status.reason)} · deterministic review remains available.`;
      el("review-availability").className = "review-availability fallback";
    }
  } catch (_error) {
    el("review-mode-chip").textContent = "Fail-closed review";
    el("review-availability").textContent = "Live availability could not be confirmed · deterministic gates remain available.";
    el("review-availability").className = "review-availability fallback";
  }
}

async function runReview() {
  if (!state.activeModule || !state.activeCase) return;
  const button = el("review-button");
  button.disabled = true;
  button.innerHTML = "Reviewing evidence…";
  resetReviewResult("Running deterministic gates and preparing the structured verdict…");
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
    resetReviewResult(error.message, true);
  } finally {
    button.disabled = false;
    button.innerHTML = "Run verified review <span>→</span>";
    refreshReviewStatus();
  }
}

function setupNavigation() {
  const button = el("menu-button");
  const navigation = el("primary-navigation");
  button.addEventListener("click", () => {
    const open = !navigation.classList.contains("open");
    navigation.classList.toggle("open", open);
    button.classList.toggle("open", open);
    button.setAttribute("aria-expanded", open);
    button.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  });
  navigation.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      navigation.classList.remove("open");
      button.classList.remove("open");
      button.setAttribute("aria-expanded", "false");
    });
  });
}

async function init() {
  setupNavigation();
  el("review-button").addEventListener("click", runReview);
  el("copy-package-digest").addEventListener("click", () => {
    if (state.activeCase?.package_sha256) copyText(state.activeCase.package_sha256, "Package hash copied");
  });
  el("media-dialog-close").addEventListener("click", closeMediaDialog);
  el("media-browser-fullscreen").addEventListener("click", requestMediaFullscreen);
  el("media-dialog").addEventListener("click", (event) => {
    if (event.target === el("media-dialog")) closeMediaDialog();
  });
  el("media-dialog").addEventListener("close", () => {
    const video = el("media-dialog-content").querySelector("video");
    if (video) video.pause();
  });
  refreshReviewStatus();

  try {
    state.modules = await fetchJson("/api/modules");
    const requestedModule = new URLSearchParams(window.location.search).get("module");
    const initial = state.modules.find((module) => module.id === requestedModule)
      || state.modules.find((module) => module.id === "cfd")
      || state.modules[0];
    state.activeModule = initial;
    renderModuleCards();
    await selectModule(initial.id, { updateUrl: false });
  } catch (error) {
    el("module-cards").innerHTML = `<p class="load-error">${escapeHtml(error.message)}</p>`;
    resetReviewResult(error.message, true);
  }
}

init();
