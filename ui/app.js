(function () {
  "use strict";

  const viewElements = document.querySelectorAll("[data-view]");
  const navButtons = document.querySelectorAll("[data-nav]");
  const tabButtons = document.querySelectorAll('[role="tab"]');
  const panels = document.querySelectorAll("[data-panel]");
  const form = document.getElementById("analysis-form");
  const datasetField = document.getElementById("dataset");
  const questionField = document.getElementById("question");
  const runButton = document.querySelector("[data-run-button]");
  const formStatus = document.getElementById("form-status");
  const copyButton = document.querySelector("[data-copy-run-id]");
  const state = { run: null };

  function setView(viewName) {
    viewElements.forEach(function (view) {
      view.hidden = view.dataset.view !== viewName;
    });
    navButtons.forEach(function (button) {
      button.classList.toggle("is-current", button.dataset.nav === viewName);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function setTab(tabName) {
    const target = document.querySelector('[data-tab="' + tabName + '"]');
    if (!target || target.hidden) return;
    tabButtons.forEach(function (button) {
      const isActive = button.dataset.tab === tabName;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", String(isActive));
      button.tabIndex = isActive ? 0 : -1;
    });
    panels.forEach(function (panel) {
      panel.hidden = panel.dataset.panel !== tabName;
    });
  }

  async function request(path, options) {
    const response = await fetch(path, options);
    const payload = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(payload.error || "The local service could not complete that request.");
    return payload;
  }

  function setText(selector, value) {
    const element = document.querySelector(selector);
    if (element) element.textContent = value || "—";
  }

  function formatDataset(dataset) {
    return dataset.id + " · " + dataset.row_count.toLocaleString() + " rows";
  }

  function formatResources(resources) {
    if (!resources) return "No resource measurements recorded.";
    return [
      resources.model_calls + " model calls",
      resources.tool_calls + " tool calls",
      resources.table_pages + " table pages",
      resources.table_bytes.toLocaleString() + " bytes",
      resources.elapsed_seconds + "s"
    ].join(" · ");
  }

  function answerMessage(record) {
    if (record.message) return record.message;
    if (record.outcome === "unsupported") return "I can't answer that with my current capabilities.";
    if (record.outcome === "error") return "Sorry, I couldn't complete that request: " + (record.error || "unknown error") + ".";
    if (!record.answer || !record.task) return "No answer is available in the compact history record.";
    if (record.answer.groups) return Object.entries(record.answer.groups).map(function (entry) { return entry[0] + ": " + entry[1]; }).join("; ");
    return "Answer: " + record.answer.value;
  }

  function renderRun(run) {
    state.run = run;
    const dataset = run.dataset || { id: datasetField.value, row_count: 0 };
    setText("[data-run-id]", run.run_id);
    setText("[data-run-question]", run.question || questionField.value.trim());
    setText("[data-run-dataset]", dataset.row_count ? formatDataset(dataset) : dataset.id);
    setText("[data-outcome]", run.outcome);
    setText("[data-run-message]", answerMessage(run));
    setText("[data-outcome-heading]", run.outcome === "answered" ? "The analyst completed this bounded run." : run.outcome === "unsupported" ? "The analyst recorded an explicit capability gap." : "The analyst could not complete this run.");

    const answerDetails = document.querySelector("[data-answer-details]");
    const answerJson = document.querySelector("[data-answer-json]");
    answerDetails.hidden = !run.answer && !run.error;
    answerJson.textContent = JSON.stringify(run.answer || { error: run.error }, null, 2);

    const history = run.history || { status: run.history_status };
    setText("[data-history-status]", history.status === "recorded" || run.history_status === "completed" ? "Compact run record stored in Atlas." : "History status: " + (history.status || run.history_status || "unavailable"));
    setText("[data-history-badge]", history.status || run.history_status || "unavailable");
    const trace = run.trace || {};
    setText("[data-trace-detail]", trace.status === "available" ? "Trace " + trace.id + " was verified in " + trace.project + "." : "Trace status: " + (trace.status || "unavailable") + (trace.error_type ? " (" + trace.error_type + ")" : ""));
    const traceLink = document.querySelector("[data-trace-link]");
    traceLink.hidden = !trace.url;
    if (trace.url) traceLink.href = trace.url;
    setText("[data-resource-summary]", formatResources(run.resources));

    const gapTab = document.getElementById("gap-tab");
    gapTab.hidden = run.outcome !== "unsupported";
    setText("[data-gap-kind]", run.limitation_kind || "capability_gap");
    setText("[data-gap-reason]", run.limitation_reason || "The question could not be represented by the current task contract.");
    copyButton.disabled = !run.run_id;
    setView("run");
    setTab("result");
  }

  function emptyRow(message) {
    const row = document.createElement("div");
    row.className = "evaluation-row empty-row";
    row.textContent = message;
    return row;
  }

  function historyRow(run) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "evaluation-row history-row";
    const details = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = run.question || run.run_id;
    const meta = document.createElement("span");
    meta.textContent = (run.dataset && run.dataset.id ? run.dataset.id + " · " : "") + (run.outcome || "recorded") + (run.created_at ? " · " + new Date(run.created_at).toLocaleString() : "");
    details.append(title, meta);
    const badge = document.createElement("span");
    badge.className = "row-result";
    badge.textContent = run.outcome || "recorded";
    row.append(details, badge);
    row.addEventListener("click", async function () {
      try {
        renderRun(await request("/api/runs/" + encodeURIComponent(run.run_id)));
      } catch (error) {
        formStatus.textContent = error.message;
        setView("ask");
      }
    });
    return row;
  }

  function renderHistory(selector, runs, emptyMessage) {
    const list = document.querySelector(selector);
    list.replaceChildren();
    if (!runs.length) list.append(emptyRow(emptyMessage));
    runs.forEach(function (run) { list.append(historyRow(run)); });
  }

  async function loadHistory() {
    const results = await Promise.all([request("/api/runs?limit=20"), request("/api/capability-gaps?limit=20")]);
    renderHistory("[data-history-list]", results[0].runs, "No completed runs have been recorded yet.");
    renderHistory("[data-gap-list]", results[1].runs, "No explicit capability gaps have been recorded yet.");
  }

  async function loadDatasets() {
    const payload = await request("/api/datasets");
    datasetField.replaceChildren();
    if (!payload.datasets.length) {
      datasetField.add(new Option("No ready datasets — seed one with the CLI first", ""));
      formStatus.textContent = "No ready Atlas datasets were found. Seed a fixture, then refresh this page.";
      return;
    }
    payload.datasets.forEach(function (dataset) {
      datasetField.add(new Option(formatDataset(dataset), dataset.id));
    });
    datasetField.disabled = false;
    runButton.disabled = false;
  }

  async function loadHealth() {
    const health = await request("/api/health");
    setText("[data-atlas-status]", "Atlas " + health.atlas);
    setText("[data-langsmith-status]", "LangSmith " + health.langsmith);
  }

  navButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      setView(button.dataset.nav);
      if (button.dataset.nav === "history") {
        loadHistory().catch(function (error) { renderHistory("[data-history-list]", [], error.message); });
      }
    });
  });

  tabButtons.forEach(function (button) {
    button.addEventListener("click", function () { setTab(button.dataset.tab); });
    button.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      const visible = Array.from(tabButtons).filter(function (item) { return !item.hidden; });
      const nextIndex = (visible.indexOf(button) + (event.key === "ArrowRight" ? 1 : -1) + visible.length) % visible.length;
      visible[nextIndex].focus();
      setTab(visible[nextIndex].dataset.tab);
    });
  });

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (runButton.disabled) return;
    const label = runButton.textContent;
    runButton.disabled = true;
    runButton.setAttribute("aria-busy", "true");
    runButton.textContent = "Running agent…";
    formStatus.textContent = "The supervisor is running the bounded analyst and recording evidence.";
    try {
      const run = await request("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset_id: datasetField.value, question: questionField.value }) });
      renderRun(run);
    } catch (error) {
      formStatus.textContent = error.message;
    } finally {
      runButton.disabled = false;
      runButton.removeAttribute("aria-busy");
      runButton.textContent = label;
    }
  });

  copyButton.addEventListener("click", async function () {
    if (!state.run) return;
    const original = copyButton.textContent;
    try {
      await navigator.clipboard.writeText(state.run.run_id);
      copyButton.textContent = "Copied";
    } catch (error) {
      copyButton.textContent = "Copy unavailable";
    }
    window.setTimeout(function () { copyButton.textContent = original; }, 1400);
  });

  Promise.all([loadHealth(), loadDatasets()]).catch(function (error) {
    formStatus.textContent = error.message;
    setText("[data-atlas-status]", "Atlas unavailable");
    setText("[data-langsmith-status]", "LangSmith unavailable");
  });
})();
