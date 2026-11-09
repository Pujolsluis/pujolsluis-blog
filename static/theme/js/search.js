(function attachSearch(root, factory) {
  const search = factory();
  if (typeof module === "object" && module.exports) module.exports = search;
  if (root && root.document) {
    const initialize = () => search.initialize(root.document, search.createFetcher(root), root.location);
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", initialize, { once: true });
    } else {
      initialize();
    }
  }
})(typeof globalThis === "object" ? globalThis : this, function createSearch() {
  "use strict";

  const RESULTS_PER_PAGE = 10;

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

  function paginatePosts(posts, pageNumber, pageSize = RESULTS_PER_PAGE) {
    const pageCount = Math.ceil(posts.length / pageSize);
    const parsedPage = Number.parseInt(pageNumber, 10) || 1;
    const currentPage = pageCount
      ? Math.min(Math.max(parsedPage, 1), pageCount)
      : 1;
    const offset = (currentPage - 1) * pageSize;
    return {
      items: posts.slice(offset, offset + pageSize),
      pageNumber: currentPage,
      pageCount,
      firstResult: posts.length ? offset + 1 : 0,
      lastResult: Math.min(offset + pageSize, posts.length),
    };
  }

  function createPageHref(query, pageNumber) {
    const parameters = new URLSearchParams({ q: query });
    if (pageNumber > 1) parameters.set("page", String(pageNumber));
    return "?" + parameters.toString();
  }

  function createFetcher(root) {
    if (typeof root.fetch === "function") return root.fetch.bind(root);

    return (url, options) => new Promise((resolve, reject) => {
      if (typeof root.XMLHttpRequest !== "function") {
        reject(new Error("No browser request API is available"));
        return;
      }

      const request = new root.XMLHttpRequest();
      request.open("GET", url, true);
      Object.entries((options && options.headers) || {}).forEach(([name, value]) => {
        request.setRequestHeader(name, value);
      });
      request.onload = () => resolve({
        ok: request.status >= 200 && request.status < 300,
        json: () => Promise.resolve().then(() => JSON.parse(request.responseText)),
      });
      request.onerror = () => reject(new Error("Search index request failed"));
      request.onabort = () => reject(new Error("Search index request was aborted"));
      request.send();
    });
  }

  function initialize(document, fetcher, location) {
    const menu = document.querySelector(".site-search");
    const menuInput = menu && menu.querySelector("[data-search-menu-input]");
    if (menu && menuInput) {
      menu.addEventListener("toggle", () => {
        if (menu.open) menuInput.focus();
      });
    }

    const page = document.querySelector("[data-search-page]");
    if (!page) return;

    const input = page.querySelector("[data-search-query]");
    const status = page.querySelector("[data-search-status]");
    const results = page.querySelector("[data-search-results]");
    const pagination = page.querySelector("[data-search-pagination]");
    const previous = page.querySelector("[data-search-previous]");
    const next = page.querySelector("[data-search-next]");
    const pageStatus = page.querySelector("[data-search-page-number]");
    if (!input || !status || !results || !pagination || !previous || !next || !pageStatus) return;

    const parameters = new URLSearchParams(location.search || "");
    const query = (parameters.get("q") || "").trim();
    const requestedPage = Number.parseInt(parameters.get("page") || "1", 10);
    input.value = query;
    const loadIndex = () => fetcher(page.dataset.indexUrl, { headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) throw new Error("Search index request failed");
        return response.json();
      })
      .then((posts) => {
        if (!Array.isArray(posts)) throw new Error("Search index has an invalid format");
        return posts;
      });

    function renderResults(posts) {
      results.replaceChildren();
      const matches = searchPosts(posts, query);
      const page = paginatePosts(matches, requestedPage);
      page.items.forEach((post) => {
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
      if (!matches.length) {
        status.textContent = "No posts found for “" + query + "”.";
        pagination.hidden = true;
        return;
      }

      status.textContent = "Showing " + page.firstResult + "–" + page.lastResult
        + " of " + matches.length + " results for “" + query + "”.";
      pageStatus.textContent = "Page " + page.pageNumber + " of " + page.pageCount;
      previous.hidden = page.pageNumber <= 1;
      next.hidden = page.pageNumber >= page.pageCount;
      if (!previous.hidden) previous.href = createPageHref(query, page.pageNumber - 1);
      if (!next.hidden) next.href = createPageHref(query, page.pageNumber + 1);
      pagination.hidden = page.pageCount <= 1;
    }

    if (!query) {
      status.textContent = "Enter a search term to find posts.";
      results.replaceChildren();
      results.setAttribute("aria-busy", "false");
      pagination.hidden = true;
      return;
    }

    status.textContent = "Loading search results…";
    results.setAttribute("aria-busy", "true");
    loadIndex().then((posts) => renderResults(posts)).catch(() => {
      results.setAttribute("aria-busy", "false");
      status.textContent = "Search could not load. Refresh the page and try again.";
      pagination.hidden = true;
    });
  }

  return {
    searchPosts,
    createSnippet,
    createFetcher,
    paginatePosts,
    createPageHref,
    initialize,
  };
});
