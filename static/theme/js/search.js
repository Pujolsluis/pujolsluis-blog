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

  function createSnippet(post, query, limit = 200) {
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

  function appendPageControl(document, pageList, query, {
    label,
    ariaLabel,
    pageNumber,
    currentPage,
    disabled = false,
  }) {
    const item = document.createElement("li");
    const isCurrent = !disabled && pageNumber === currentPage;
    item.className = ["page-item", disabled ? "disabled" : "", isCurrent ? "active" : ""]
      .filter(Boolean)
      .join(" ");

    const link = document.createElement("a");
    link.className = "page-link";
    link.setAttribute("aria-label", ariaLabel);
    link.setAttribute("role", "button");

    if (disabled) {
      link.setAttribute("aria-disabled", "true");
      link.tabIndex = -1;
    } else if (isCurrent) {
      link.setAttribute("aria-current", "page");
    } else {
      link.href = createPageHref(query, pageNumber);
    }

    if (/^(First|Previous|Next|Last)$/.test(ariaLabel)) {
      const symbol = document.createElement("span");
      symbol.setAttribute("aria-hidden", "true");
      symbol.textContent = label;
      link.append(symbol);
    } else {
      link.textContent = label;
    }

    item.append(link);
    pageList.append(item);
  }

  function renderPagination(document, pageList, query, currentPage, pageCount) {
    pageList.replaceChildren();
    const visiblePages = Math.min(pageCount, 5);
    const firstVisiblePage = Math.min(
      Math.max(currentPage - Math.floor(visiblePages / 2), 1),
      pageCount - visiblePages + 1
    );

    appendPageControl(document, pageList, query, {
      label: "««",
      ariaLabel: "First",
      pageNumber: 1,
      currentPage,
      disabled: currentPage === 1,
    });
    appendPageControl(document, pageList, query, {
      label: "«",
      ariaLabel: "Previous",
      pageNumber: currentPage - 1,
      currentPage,
      disabled: currentPage === 1,
    });

    for (let pageNumber = firstVisiblePage; pageNumber < firstVisiblePage + visiblePages; pageNumber += 1) {
      appendPageControl(document, pageList, query, {
        label: String(pageNumber),
        ariaLabel: "Page " + pageNumber,
        pageNumber,
        currentPage,
      });
    }

    appendPageControl(document, pageList, query, {
      label: "»",
      ariaLabel: "Next",
      pageNumber: currentPage + 1,
      currentPage,
      disabled: currentPage === pageCount,
    });
    appendPageControl(document, pageList, query, {
      label: "»»",
      ariaLabel: "Last",
      pageNumber: pageCount,
      currentPage,
      disabled: currentPage === pageCount,
    });
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
    const pageList = page.querySelector("[data-search-page-links]");
    if (!input || !status || !results || !pagination || !pageList) return;

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
      const resultPage = paginatePosts(matches, requestedPage);
      resultPage.items.forEach((post) => {
        const item = document.createElement("li");
        item.className = "post-card";

        const heading = document.createElement("h2");
        const link = document.createElement("a");
        link.href = post.url;
        link.textContent = post.title;
        heading.append(link);
        item.append(heading);

        if (post.date) {
          const date = document.createElement("time");
          date.dateTime = post.date;
          date.textContent = post.displayDate || post.date;
          item.append(date);
        }

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

      status.textContent = "Showing " + resultPage.firstResult + "–" + resultPage.lastResult
        + " of " + matches.length + " results for “" + query + "”.";
      renderPagination(document, pageList, query, resultPage.pageNumber, resultPage.pageCount);
      pagination.hidden = resultPage.pageCount <= 1;
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
