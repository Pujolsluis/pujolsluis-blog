(function attachSearch(root, factory) {
  const search = factory();
  if (typeof module === "object" && module.exports) module.exports = search;
  if (root && root.document) {
    const initialize = () => search.initialize(root.document, root.fetch.bind(root), root.location);
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", initialize, { once: true });
    } else {
      initialize();
    }
  }
})(typeof globalThis === "object" ? globalThis : this, function createSearch() {
  "use strict";

  const RESULT_LIMIT = 10;

  function normalize(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase();
  }

  function searchPosts(posts, query) {
    const normalizedQuery = normalize(query).trim();
    const terms = normalizedQuery.split(/\s+/).filter(Boolean);
    if (!terms.length || !Array.isArray(posts)) return [];

    return posts
      .map((post) => {
        const title = normalize(post.title);
        const text = normalize(post.text || post.summary);
        if (!terms.every((term) => title.includes(term) || text.includes(term))) return null;

        const score = terms.reduce((total, term) => total + (title.includes(term) ? 5 : 0)
          + (text.includes(term) ? 1 : 0), title.includes(normalizedQuery) ? 2 : 0);
        return { post, score };
      })
      .filter(Boolean)
      .sort((left, right) => right.score - left.score
        || String(left.post.title).localeCompare(String(right.post.title)))
      .map((result) => result.post);
  }

  function createSnippet(post, query, limit = 180) {
    const text = String(post.text || post.summary || "").replace(/\s+/g, " ").trim();
    if (text.length <= limit) return text;

    const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
    const normalizedText = normalize(text);
    const matches = terms.map((term) => normalizedText.indexOf(term)).filter((index) => index >= 0);
    const firstMatch = matches.length ? Math.min(...matches) : 0;
    const start = Math.max(0, firstMatch - Math.floor(limit / 3));
    const end = Math.min(text.length, start + limit);
    return `${start ? "…" : ""}${text.slice(start, end).trim()}${end < text.length ? "…" : ""}`;
  }

  function initialize(document, fetcher, location) {
    const form = document.querySelector("[data-site-search]");
    if (!form) return;

    const details = form.closest("details");
    const input = form.querySelector("[data-search-input]");
    const status = form.querySelector("[data-search-status]");
    const results = form.querySelector("[data-search-results]");
    if (!input || !status || !results) return;

    let indexPromise;
    let requestVersion = 0;
    const loadIndex = () => {
      if (!indexPromise) {
        indexPromise = fetcher(form.dataset.indexUrl, { headers: { Accept: "application/json" } })
          .then((response) => {
            if (!response.ok) throw new Error("Search index request failed");
            return response.json();
          })
          .then((posts) => {
            if (!Array.isArray(posts)) throw new Error("Search index has an invalid format");
            return posts;
          });
      }
      return indexPromise;
    };

    function renderResults() {
      const query = input.value.trim();
      const version = ++requestVersion;
      results.replaceChildren();
      if (!query) {
        results.setAttribute("aria-busy", "false");
        status.textContent = "Search post titles and article text.";
        return;
      }

      status.textContent = "Searching…";
      results.setAttribute("aria-busy", "true");
      loadIndex().then((posts) => {
        if (version !== requestVersion) return;
        const matches = searchPosts(posts, query).slice(0, RESULT_LIMIT);
        matches.forEach((post) => {
          const item = document.createElement("li");
          const link = document.createElement("a");
          link.href = post.url;
          link.textContent = post.title;
          item.append(link);

          const snippet = createSnippet(post, query);
          if (snippet) {
            const description = document.createElement("p");
            description.textContent = snippet;
            item.append(description);
          }
          results.append(item);
        });
        results.setAttribute("aria-busy", "false");
        status.textContent = matches.length
          ? `${matches.length} result${matches.length === 1 ? "" : "s"}${matches.length === RESULT_LIMIT ? " (showing the top results)" : ""}.`
          : `No posts found for “${query}”.`;
      }).catch(() => {
        if (version !== requestVersion) return;
        results.setAttribute("aria-busy", "false");
        status.textContent = "Search could not load. Refresh the page and try again.";
      });
    }

    input.addEventListener("input", renderResults);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const firstResult = results.querySelector("a");
      if (firstResult) location.assign(firstResult.href);
    });
    if (details) details.addEventListener("toggle", () => {
      if (details.open) input.focus();
    });
  }

  return { searchPosts, createSnippet, initialize };
});
