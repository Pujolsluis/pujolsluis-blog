const assert = require("node:assert/strict");
const { test } = require("node:test");
const { createSnippet, searchPosts } = require("../static/theme/js/search.js");

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
  const post = { text: `${"opening words ".repeat(20)}important phrase${" closing words".repeat(20)}` };
  const snippet = createSnippet(post, "important phrase", 60);
  assert.match(snippet, /important phrase/);
  assert.ok(snippet.length <= 62);
});
