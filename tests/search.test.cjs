const assert = require("node:assert/strict");
const { test } = require("node:test");
const {
  createFetcher,
  createPageHref,
  createSnippet,
  paginatePosts,
  searchPosts,
} = require("../static/theme/js/search.js");

const posts = [
  { title: "Xamarin Forms workshop", text: "Reactive programming with Rx.NET." },
  { title: "Azure basics", text: "A guide to cloud services." },
  { title: "Andrés at .NET Dominicana", text: "Community workshop notes." },
];

test("search matches all query terms in titles or full article text", () => {
  assert.deepEqual(searchPosts(posts, "reactive Rx.NET").map((post) => post.title), [
    "Xamarin Forms workshop",
  ]);
  assert.deepEqual(searchPosts(posts, "azure missing"), []);
});

test("search is case and accent insensitive and ranks title matches first", () => {
  const results = searchPosts([
    { title: "Article", text: "Xamarin Forms workshop notes." },
    { title: "Xamarin Forms workshop", text: "A community event." },
  ], "XAMARÍN forms");
  assert.equal(results[0].title, "Xamarin Forms workshop");
  assert.equal(searchPosts(posts, "andres")[0].title, "Andrés at .NET Dominicana");
});

test("empty queries do not return every post", () => {
  assert.deepEqual(searchPosts(posts, "  "), []);
});

test("result snippets center around the matching text", () => {
  const post = { text: "opening words ".repeat(20) + "important phrase" + " closing words".repeat(20) };
  const snippet = createSnippet(post, "important phrase", 60);
  assert.match(snippet, /important phrase/);
  assert.ok(snippet.length <= 62);
});

test("pagination includes all matches and clamps invalid page numbers", () => {
  const matches = Array.from({ length: 23 }, (_, index) => ({ title: "Post " + (index + 1) }));
  const first = paginatePosts(matches, 1);
  const middle = paginatePosts(matches, 2);
  const last = paginatePosts(matches, 99);

  assert.equal(first.pageCount, 3);
  assert.equal(first.firstResult, 1);
  assert.equal(first.lastResult, 10);
  assert.deepEqual(first.items, matches.slice(0, 10));
  assert.equal(middle.firstResult, 11);
  assert.equal(middle.lastResult, 20);
  assert.deepEqual(middle.items, matches.slice(10, 20));
  assert.equal(last.pageNumber, 3);
  assert.deepEqual(last.items, matches.slice(20));
  assert.equal(paginatePosts([], 1).pageCount, 0);
});

test("pagination links preserve the query and omit page one", () => {
  assert.equal(createPageHref("xamarin forms", 1), "?q=xamarin+forms");
  assert.equal(createPageHref("xamarin forms", 2), "?q=xamarin+forms&page=2");
});

test("search index can load through XMLHttpRequest when fetch is unavailable", async () => {
  let request;
  class FakeXMLHttpRequest {
    constructor() {
      request = this;
    }

    open(method, url, asynchronous) {
      this.request = { method, url, asynchronous };
    }

    setRequestHeader(name, value) {
      this.header = { name, value };
    }

    send() {
      this.status = 200;
      this.responseText = JSON.stringify([{ title: "Indexed post" }]);
      this.onload();
    }
  }

  const fetcher = createFetcher({ XMLHttpRequest: FakeXMLHttpRequest });
  const response = await fetcher("/search-index.json", {
    headers: { Accept: "application/json" },
  });
  assert.deepEqual(request.request, {
    method: "GET",
    url: "/search-index.json",
    asynchronous: true,
  });
  assert.deepEqual(request.header, { name: "Accept", value: "application/json" });
  assert.deepEqual(await response.json(), [{ title: "Indexed post" }]);
});
