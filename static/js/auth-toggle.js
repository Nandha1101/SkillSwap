(() => {
  const card = document.querySelector("[data-auth-card]");
  if (!card) return;

  const panels = Array.from(card.querySelectorAll("[data-auth-form]"));
  const switches = Array.from(card.querySelectorAll("[data-auth-toggle]"));
  const loginUrl = card.dataset.loginUrl;
  const signupUrl = card.dataset.signupUrl;

  const setMode = (mode, { updateHistory = false, focus = false } = {}) => {
    if (mode !== "login" && mode !== "signup") return;
    card.dataset.activePanel = mode;
    card.classList.toggle("is-signup", mode === "signup");

    panels.forEach((panel) => {
      const isActive = panel.dataset.authForm === mode;
      panel.setAttribute("aria-hidden", String(!isActive));
      panel.inert = !isActive;
    });

    switches.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.authToggle === mode));
    });

    if (updateHistory) {
      window.history.pushState({ authMode: mode }, "", mode === "signup" ? signupUrl : loginUrl);
    }

    if (focus) {
      card.querySelector(`[data-auth-form="${mode}"] input`)?.focus();
    }
  };

  switches.forEach((button) => {
    button.addEventListener("click", () => {
      setMode(button.dataset.authToggle, { updateHistory: true, focus: true });
    });
  });

  window.addEventListener("popstate", () => {
    const mode = window.location.pathname.replace(/\/+$/, "").endsWith("/signup") ? "signup" : "login";
    setMode(mode);
  });

  setMode(card.dataset.activePanel);
  document.documentElement.classList.add("auth-ready");
})();
