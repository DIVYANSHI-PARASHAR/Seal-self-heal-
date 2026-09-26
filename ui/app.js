(function () {
  "use strict";

  const viewElements = document.querySelectorAll("[data-view]");
  const navButtons = document.querySelectorAll("[data-nav]");
  const tabButtons = document.querySelectorAll('[role="tab"]');
  const tabTriggers = document.querySelectorAll("[data-tab]");
  const panels = document.querySelectorAll("[data-panel]");
  const form = document.getElementById("analysis-form");
  const questionField = document.getElementById("question");
  const runQuestion = document.getElementById("run-question");
  const copyButton = document.querySelector("[data-copy-run-id]");

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

  navButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      setView(button.dataset.nav);
      if (button.dataset.tab) {
        setTab(button.dataset.tab);
      }
    });
  });

  tabTriggers.forEach(function (button) {
    button.addEventListener("click", function () {
      setTab(button.dataset.tab);
    });
  });

  tabButtons.forEach(function (button) {
    button.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") {
        return;
      }

      const buttons = Array.from(tabButtons);
      const currentIndex = buttons.indexOf(button);
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const nextIndex = (currentIndex + direction + buttons.length) % buttons.length;
      const nextButton = buttons[nextIndex];
      nextButton.focus();
      setTab(nextButton.dataset.tab);
    });
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    const question = questionField.value.trim();
    runQuestion.textContent = question || "What are the available units in each warehouse?";
    setView("run");
    setTab("failure");
  });

  copyButton.addEventListener("click", async function () {
    const runId = "run_bulk_01H8K7";
    const originalLabel = copyButton.textContent;

    try {
      await navigator.clipboard.writeText(runId);
      copyButton.textContent = "Copied";
    } catch (error) {
      copyButton.textContent = "Copy unavailable";
    }

    window.setTimeout(function () {
      copyButton.textContent = originalLabel;
    }, 1400);
  });
})();
