(function () {
  "use strict";

  const form = document.getElementById("analysis-form");
  const runDetails = document.getElementById("run-details");
  const exampleQuestionField = document.getElementById("example-question");
  const questionField = document.getElementById("question");
  const runButton = document.querySelector("[data-run-button]");
  const copyButton = document.querySelector("[data-copy-run-id]");
  const state = { run: null };
  const exampleQuestions = [
    "How many available units are in the East warehouse?",
    "How many available units are in the West warehouse?",
    "What are the available units in each warehouse?"
  ];

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
    return dataset.id + " · " + Number(dataset.row_count).toLocaleString() + " rows";
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
    const dataset = run.dataset || {};
    setText("[data-run-id]", run.run_id);
    setText("[data-run-question]", run.question || questionField.value.trim());
    setText("[data-run-dataset]", dataset.id ? (Number.isFinite(Number(dataset.row_count)) ? formatDataset(dataset) : dataset.id) : "Dataset selected automatically");
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

    document.getElementById("gap-panel").hidden = run.outcome !== "unsupported";
    setText("[data-gap-kind]", run.limitation_kind || "capability_gap");
    setText("[data-gap-reason]", run.limitation_reason || "The question could not be represented by the current task contract.");
    copyButton.disabled = !run.run_id;
    runDetails.hidden = false;
    runDetails.scrollIntoView({ behavior: "smooth", block: "start" });
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
        questionField.setCustomValidity(error.message);
        questionField.reportValidity();
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

  function loadExampleQuestions() {
    if (!exampleQuestionField) return;
    exampleQuestionField.replaceChildren(new Option("Custom question", ""));
    exampleQuestions.forEach(function (question) {
      exampleQuestionField.add(new Option(question, question));
    });
  }

  async function loadHealth() {
    await request("/api/health");
    runButton.disabled = false;
  }

  if (exampleQuestionField) {
    exampleQuestionField.addEventListener("change", function () {
      if (!exampleQuestionField.value) return;
      questionField.value = exampleQuestionField.value;
      questionField.setCustomValidity("");
      questionField.focus();
    });

    questionField.addEventListener("input", function () {
      questionField.setCustomValidity("");
      if (exampleQuestionField.value && questionField.value !== exampleQuestionField.value) {
        exampleQuestionField.value = "";
      }
    });
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (runButton.disabled) return;
    questionField.setCustomValidity("");
    const label = runButton.textContent;
    runButton.disabled = true;
    runButton.setAttribute("aria-busy", "true");
    runButton.textContent = "Running agent…";
    try {
      const run = await request("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: questionField.value }) });
      renderRun(run);
      loadHistory().catch(function (error) { renderHistory("[data-history-list]", [], error.message); });
    } catch (error) {
      questionField.setCustomValidity(error.message);
      questionField.reportValidity();
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

  loadExampleQuestions();
  loadHistory().catch(function (error) { renderHistory("[data-history-list]", [], error.message); });
  loadHealth().catch(function (error) {
    runButton.title = error.message;
  });
})();
