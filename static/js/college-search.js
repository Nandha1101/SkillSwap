(() => {
  const inputs = document.querySelectorAll("[data-college-search]");

  inputs.forEach((input) => {
    const results = document.getElementById(input.getAttribute("aria-controls"));
    if (!results) return;

    let debounceTimer;
    let activeController;
    let requestVersion = 0;

    const closeResults = () => {
      results.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    };

    const showStatus = (message) => {
      results.replaceChildren();
      const status = document.createElement("div");
      status.className = "college-status";
      status.textContent = message;
      results.append(status);
      results.hidden = false;
      input.setAttribute("aria-expanded", "true");
    };

    const showResults = (colleges) => {
      results.replaceChildren();
      colleges.filter((college) => college && typeof college.name === "string" && college.name.trim()).slice(0, 8).forEach((college, index) => {
        const option = document.createElement("button");
        option.type = "button";
        option.id = `college-option-${requestVersion}-${index}`;
        option.className = "college-option";
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");

        const name = document.createElement("span");
        name.className = "college-option-name";
        name.textContent = college.name;
        option.append(name);

        const metadata = [college.country, college.domains?.[0]].filter(Boolean).join(" · ");
        if (metadata) {
          const detail = document.createElement("span");
          detail.className = "college-option-meta";
          detail.textContent = metadata;
          option.append(detail);
        }

        option.addEventListener("mousedown", (event) => event.preventDefault());
        option.addEventListener("click", () => {
          input.value = college.name;
          closeResults();
          input.dispatchEvent(new Event("change", { bubbles: true }));
        });
        results.append(option);
      });

      if (!results.childElementCount) {
        showStatus("No matching colleges found. You can enter the name manually.");
        return;
      }

      results.hidden = false;
      input.setAttribute("aria-expanded", "true");
    };

    input.addEventListener("input", () => {
      window.clearTimeout(debounceTimer);
      if (activeController) activeController.abort();
      const query = input.value.trim();
      const version = ++requestVersion;

      if (query.length < 2) {
        closeResults();
        return;
      }

      debounceTimer = window.setTimeout(async () => {
        activeController = new AbortController();
        let timedOut = false;
        const timeoutId = window.setTimeout(() => {
          timedOut = true;
          activeController.abort();
        }, 15000);
        showStatus("Searching colleges...");
        try {
          const url = new URL("/api/colleges/", window.location.origin);
          url.searchParams.set("name", query);
          const response = await fetch(url, {
            signal: activeController.signal,
            headers: { Accept: "application/json" },
          });
          const payload = await response.json();
          if (version !== requestVersion || input.value.trim() !== query) return;
          if (!response.ok) {
            const message = typeof payload.error === "string"
              ? payload.error
              : "College search is temporarily unavailable. Please try again.";
            showStatus(message);
            return;
          }
          const colleges = payload;
          if (!Array.isArray(colleges)) throw new Error("College directory returned an unexpected response.");
          showResults(colleges);
        } catch (error) {
          if (version !== requestVersion) return;
          if (error.name === "AbortError" && !timedOut) return;
          showStatus(timedOut
            ? "College search is taking too long. Check your connection or enter the name manually."
            : "Could not load college suggestions. Check your connection or enter the name manually.");
          console.error("College directory search failed:", error);
        } finally {
          window.clearTimeout(timeoutId);
        }
      }, 450);
    });

    const focusOption = (direction, fromInput = false) => {
      const options = Array.from(results.querySelectorAll('[role="option"]'));
      if (!options.length) return;
      const currentIndex = options.indexOf(document.activeElement);
      const nextIndex = fromInput
        ? direction > 0 ? 0 : options.length - 1
        : (currentIndex + direction + options.length) % options.length;
      options[nextIndex].focus();
    };

    input.addEventListener("keydown", (event) => {
      if (results.hidden) return;
      if (event.key === "Escape") {
        closeResults();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        focusOption(event.key === "ArrowDown" ? 1 : -1, true);
      }
    });

    results.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        focusOption(event.key === "ArrowDown" ? 1 : -1);
      } else if (event.key === "Escape") {
        closeResults();
        input.focus();
      }
    });

    input.parentElement.addEventListener("focusout", () => {
      window.setTimeout(() => {
        if (!input.parentElement.contains(document.activeElement)) closeResults();
      }, 0);
    });
  });
})();
