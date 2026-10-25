"""Capture bounded, unauthenticated WordPress evidence, without source bodies.

Run: python -m scripts.inventory.capture --output migration/inventory/public
Only explicitly public published post/page and taxonomy metadata is retained.
Response hashes identify observations; they do not constitute a backup.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

USER_AGENT = "Mozilla/5.0 (compatible; PujolsluisMigrationInventory/1.0)"
MAX_BYTES = 8 * 1024 * 1024
ASSET_EXTENSIONS = re.compile(r"\.(?:pdf|zip|mp3|mp4|webm|ogg|wav|jpg|jpeg|png|gif|webp|svg|ico|woff2?|ttf)(?:$|\?)", re.I)


def plain(value):
    return unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


class PageParser(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.links = set()
        self.assets = set()
        self.embeds = set()
        self.canonical = None
        self.signals = set()
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "title":
            self.in_title = True
        href = attrs.get("href", "")
        if tag == "a" and href:
            url = urljoin(self.base, href).split("#")[0]
            if urlsplit(url).scheme in ("http", "https"):
                self.links.add(url)
                if ASSET_EXTENSIONS.search(url):
                    self.assets.add(url)
        if tag == "link" and "canonical" in attrs.get("rel", "").split():
            self.canonical = urljoin(self.base, href)
        for name in ("src", "poster", "data-src", "data-original"):
            value = attrs.get(name)
            if value and urlsplit(urljoin(self.base, value)).scheme in ("http", "https"):
                target = urljoin(self.base, value)
                self.assets.add(target)
                if tag in ("iframe", "embed"):
                    self.embeds.add(target)
        if tag == "object" and attrs.get("data"):
            self.embeds.add(urljoin(self.base, attrs["data"]))
        for name in ("srcset", "data-srcset"):
            for item in attrs.get(name, "").split(","):
                value = item.strip().split()
                if value:
                    self.assets.add(urljoin(self.base, value[0]))
        if tag == "link" and any(x in attrs.get("rel", "").split() for x in ("stylesheet", "icon")) and href:
            self.assets.add(urljoin(self.base, href))
        for value in re.findall(r"url\(['\"]?([^)'\"]+)", attrs.get("style", "")):
            self.assets.add(urljoin(self.base, value))
        attributes_text = " ".join(str(x) for x in attrs.values()).lower()
        for name, present in {
            "search": tag == "form" and ("search" in attributes_text or attrs.get("role") == "search"),
            "comments": "comment" in attrs.get("id", "").lower(),
            "gallery": "gallery" in attributes_text,
            "audio": tag == "audio",
            "video": tag == "video",
            "form": tag == "form",
            "subscription": any(x in attributes_text for x in ("subscribe", "subscription", "jetpack-subscribe")),
            "code": tag in ("pre", "code"),
        }.items():
            if present:
                self.signals.add(name)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def parse_markup(body, base):
    parser = PageParser(base)
    parser.feed(body)
    return parser


def sitemap_urls(body):
    root = ET.fromstring(body)
    kind = root.tag.rsplit("}", 1)[-1]
    values = [element.text.strip() for entry in root for element in entry
              if element.tag.rsplit("}", 1)[-1] == "loc" and element.text]
    return kind, values


def sitemap_images(body):
    root = ET.fromstring(body)
    return [element.text.strip() for element in root.iter()
            if element.tag == "{http://www.google.com/schemas/sitemap-image/1.1}loc" and element.text]


def asset_record(url, source):
    parsed, origin = urlsplit(url), None
    source_host = urlsplit(source).netloc
    if parsed.netloc == source_host and "/wp-content/uploads/" in parsed.path:
        origin = url
    elif re.fullmatch(r"i[0-3]\.wp\.com", parsed.netloc) and parsed.path.startswith("/" + source_host + "/wp-content/uploads/"):
        origin = "https://" + parsed.path.lstrip("/")
    return {"url": url, "ownedHost": parsed.netloc == source_host,
            "wordpressUpload": origin is not None, "uploadOriginCandidate": origin}


def public_record(item, kind):
    return {
        "sourceId": f"wp:{item['id']}",
        "wordpressId": item["id"], "type": kind, "url": item["link"],
        "title": plain(item.get("title", {}).get("rendered", "")),
        "slug": item.get("slug"), "publishedLocal": item.get("date"),
        "publishedGmt": item.get("date_gmt"), "modifiedGmt": item.get("modified_gmt"),
        "authorId": item.get("author"), "categoryIds": item.get("categories", []),
        "tagIds": item.get("tags", []), "featuredMediaId": item.get("featured_media", 0),
        "commentStatus": item.get("comment_status"), "pingStatus": item.get("ping_status"),
        "guid": item.get("guid", {}).get("rendered"),
        "contentFields": sorted(item.get("content", {}).keys()),
        "contentSha256": hashlib.sha256(item.get("content", {}).get("rendered", "").encode()).hexdigest(),
        "evidence": ["public-wordpress-rest-publish"],
    }


class Capture:
    def __init__(self, source, delay=0.15, max_pages=250, max_assets=0):
        self.source = source.rstrip("/") + "/"
        self.host = urlsplit(self.source).netloc
        self.delay, self.max_pages, self.max_assets = delay, max_pages, max_assets
        self.responses, self.errors, self.sitemaps, self.feed_items = [], [], [], []
        self.records, self.taxonomies, self.pages = [], [], []
        self.api_totals, self.assets, self.embeds = {}, set(), set()
        self.robots = RobotFileParser()
        self.robots_ready = False
        self.api = None
        self.namespaces = []
        self.timezone = None
        self.gmt_offset = None

    def owned(self, url):
        return urlsplit(url).netloc == self.host

    def fetch(self, url, method="GET"):
        if not self.owned(url):
            raise ValueError("Inventory only fetches the configured source host")
        if self.robots_ready and not self.robots.can_fetch(USER_AGENT, url):
            self.errors.append({"url": url, "error": "robots-disallowed"})
            return None, {}
        time.sleep(self.delay)
        observation = {"url": url, "method": method}
        try:
            request = Request(url, method=method, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urlopen(request, timeout=30) as response:
                # urllib can follow redirects; do not continue discovery on a different host.
                if not self.owned(response.url):
                    raise ValueError("Cross-host redirect")
                headers = dict(response.headers.items())
                data = response.read(MAX_BYTES + 1) if method == "GET" else b""
                if len(data) > MAX_BYTES:
                    raise ValueError("Response exceeded byte limit")
                observation.update(status=response.status, finalUrl=response.url,
                                   contentType=response.headers.get("Content-Type"),
                                   contentLength=response.headers.get("Content-Length"))
                if method == "GET":
                    observation.update(bytesRead=len(data), sha256=hashlib.sha256(data).hexdigest())
                self.responses.append(observation)
                return data, {key.lower(): value for key, value in headers.items()}
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            observation.update(status=getattr(error, "code", None), error=str(error))
            self.responses.append(observation)
            self.errors.append(observation)
            return None, {}

    def collection(self, name, fields):
        rows, page = [], 1
        while page <= 100:
            query = {"per_page": 100, "page": page, "_fields": fields}
            if name in ("posts", "pages"):
                query.update(status="publish", orderby="id", order="asc", context="view")
            url = self.api + "wp/v2/" + name + "?" + urlencode(query)
            body, headers = self.fetch(url)
            if body is None:
                break
            batch = json.loads(body)
            if not isinstance(batch, list):
                self.errors.append({"url": url, "error": "Expected collection array"})
                break
            rows.extend(batch)
            total = int(headers["x-wp-total"]) if "x-wp-total" in headers else None
            total_pages = int(headers["x-wp-totalpages"]) if "x-wp-totalpages" in headers else None
            self.api_totals[name] = {"reportedTotal": total, "reportedPages": total_pages, "captured": len(rows)}
            if (total_pages is not None and page >= total_pages) or (total_pages is None and len(batch) < 100):
                break
            page += 1
        return rows

    def sitemap(self, url, seen):
        if url in seen or len(seen) >= 30 or not self.owned(url):
            return
        seen.add(url)
        body, _ = self.fetch(url)
        if body is None:
            return
        try:
            kind, urls = sitemap_urls(body)
        except ET.ParseError as error:
            self.errors.append({"url": url, "error": f"Invalid sitemap: {error}"})
            return
        images = sitemap_images(body)
        self.sitemaps.append({"url": url, "type": kind, "urls": urls, "images": images})
        self.assets.update(images)
        if kind == "sitemapindex":
            for child in urls:
                self.sitemap(child, seen)

    def capture(self):
        body, _ = self.fetch(urljoin(self.source, "robots.txt"))
        robot_text = body.decode("utf-8", "replace") if body else ""
        if body:
            self.robots.parse(robot_text.splitlines())
            self.robots_ready = True
        body, _ = self.fetch(urljoin(self.source, "wp-json/"))
        if body:
            root = json.loads(body)
            self.api = urljoin(self.source, "wp-json/")
            self.namespaces = root.get("namespaces", [])
            self.timezone, self.gmt_offset = root.get("timezone_string"), root.get("gmt_offset")
        if not self.api:
            raise RuntimeError("Public REST index unavailable; no empty success inventory produced")
        types_body, _ = self.fetch(self.api + "wp/v2/types")
        types = json.loads(types_body) if types_body else {}
        fields = "id,date,date_gmt,modified_gmt,slug,link,title,content,guid,author,categories,tags,featured_media,comment_status,ping_status"
        content = []
        for name, kind in (("posts", "post"), ("pages", "page")):
            for item in self.collection(name, fields):
                self.records.append(public_record(item, kind))
                content.append(item)
                parsed = parse_markup(item.get("content", {}).get("rendered", ""), item["link"])
                self.assets.update(parsed.assets)
                self.embeds.update(parsed.embeds)
        for name in ("categories", "tags"):
            for term in self.collection(name, "id,count,link,name,slug,parent,taxonomy"):
                self.taxonomies.append({"sourceId": f"{'wp-category' if name == 'categories' else 'wp-tag'}:{term['id']}", **term})
        sitemap_seeds = [line.split(":", 1)[1].strip() for line in robot_text.splitlines() if line.lower().startswith("sitemap:")]
        seen = set()
        for url in sitemap_seeds + [urljoin(self.source, "wp-sitemap.xml"), urljoin(self.source, "sitemap_index.xml")]:
            self.sitemap(url, seen)
        body, _ = self.fetch(urljoin(self.source, "feed/"))
        if body:
            for item in ET.fromstring(body).findall("./channel/item"):
                self.feed_items.append({"url": item.findtext("link"), "guid": item.findtext("guid"), "published": item.findtext("pubDate")})
        urls = {self.source} | {row["url"] for row in self.records} | {row["link"] for row in self.taxonomies}
        urls.update(url for sitemap in self.sitemaps if sitemap["type"] == "urlset" for url in sitemap["urls"])
        priority = [self.source] + sorted(row["url"] for row in self.records)
        queue = priority + sorted(url for url in urls if self.owned(url) and url not in priority)
        crawled = set()
        while queue and len(crawled) < self.max_pages:
            url = queue.pop(0)
            if url in crawled:
                continue
            crawled.add(url)
            body, headers = self.fetch(url)
            if body is None or "html" not in headers.get("content-type", ""):
                continue
            parsed = parse_markup(body.decode("utf-8", "replace"), url)
            self.assets.update(parsed.assets)
            self.embeds.update(parsed.embeds)
            text = body.decode("utf-8", "replace").lower()
            signals = sorted(parsed.signals | {name for name, marker in (("theblogger-theme", "/themes/theblogger/"), ("pixelwars-assets", "pixelwars"), ("jetpack-assets", "jetpack")) if marker in text})
            self.pages.append({"url": url, "title": parsed.title.strip(), "canonical": parsed.canonical,
                               "features": signals, "assets": sorted(parsed.assets), "embeds": sorted(parsed.embeds),
                               "internalLinks": sorted(link for link in parsed.links if self.owned(link)),
                               "externalLinks": sorted(link for link in parsed.links if not self.owned(link))})
            # Discover finite standard pagination/author/archive routes, not unbounded query space.
            for link in sorted(parsed.links):
                path = urlsplit(link).path
                if self.owned(link) and not urlsplit(link).query and re.search(r"/(?:page/\d+|author/[^/]+|\d{4}/\d{2})/?$", path) and link not in crawled and link not in queue:
                    queue.append(link)
        assets = []
        for url in sorted(self.assets):
            entry = asset_record(url, self.source)
            if entry["wordpressUpload"] and sum(x.get("headAttempted", False) for x in assets) < self.max_assets:
                _, headers = self.fetch(entry["uploadOriginCandidate"], "HEAD")
                entry.update(headAttempted=True, contentType=headers.get("content-type"))
                length = headers.get("content-length", "")
                entry["bytes"] = int(length) if length.isdigit() else None
            assets.append(entry)
        rest_urls = {row["url"] for row in self.records}
        sitemap_set = {url for sitemap in self.sitemaps if sitemap["type"] == "urlset" for url in sitemap["urls"]}
        upload_assets = [row for row in assets if row["wordpressUpload"]]
        measured = [row for row in upload_assets if row.get("bytes") is not None]
        features = Counter(feature for page in self.pages for feature in page["features"])
        return {
            "schemaVersion": "1.0.0", "capturedAt": datetime.now(timezone.utc).isoformat(),
            "source": self.source, "completeness": "unverified", "timezone": self.timezone, "gmtOffset": self.gmt_offset,
            "policy": {"authentication": "none", "userAgent": USER_AGENT, "concurrency": 1, "requestDelaySeconds": self.delay,
                       "maxPages": self.max_pages, "maxUploadHeads": self.max_assets, "maxResponseBytes": MAX_BYTES,
                       "contentBodiesRetained": False, "commentsFetched": False},
            "records": self.records, "taxonomies": self.taxonomies, "restAdvertisedTypes": sorted(types),
            "restNamespaces": self.namespaces, "robots": robot_text, "sitemaps": self.sitemaps,
            "feedItems": self.feed_items, "pages": self.pages, "assets": assets, "embeds": sorted(self.embeds),
            "counts": {"records": len(self.records), "byType": dict(Counter(row["type"] for row in self.records)),
                       "taxonomyRoutes": len(self.taxonomies), "crawledHtmlPages": len(self.pages),
                       "discoveredAssets": len(assets), "uploadUrls": len(upload_assets), "measuredUploadUrls": len(measured),
                       "measuredUploadBytes": sum({row["uploadOriginCandidate"]: row["bytes"] for row in measured}.values()),
                       "uploadOriginCandidates": len({row["uploadOriginCandidate"] for row in upload_assets}),
                       "unknownUploadOriginBytes": len({row["uploadOriginCandidate"] for row in upload_assets} - {row["uploadOriginCandidate"] for row in measured}), "uniqueEmbedUrls": len(self.embeds),
                       "featuresByPage": dict(features)},
            "reconciliation": {"apiCollections": self.api_totals, "restMissingFromSitemaps": sorted(rest_urls - sitemap_set),
                               "sitemapNonRestUrls": sorted(sitemap_set - rest_urls),
                               "feedNotInRest": sorted(row["url"] for row in self.feed_items if row["url"] not in rest_urls),
                               "uncrawledQueue": queue, "crawlLimitReached": bool(queue)},
            "responses": self.responses, "errors": self.errors,
            "limitations": [
                "Public REST publish records and crawl cannot prove all published records; reconcile private WXR before acceptance.",
                "No uploads archive or credentials supplied. HEAD totals cover distinct origin candidates mapped from direct and Jetpack CDN upload URLs, including resized filename variants, not all owned originals.",
                "HTML/style attributes and REST rendered content inspected; external CSS dependencies and JavaScript-generated requests are not exhaustively traversed.",
                "Feature markers and embed URLs prove presence only; interactive behavior, playback, forms, and screenshots remain unverified.",
                "REST context=view provides rendered HTML without raw editor source, shortcode definitions, complete settings, or plugin/theme configuration.",
                "Response bodies are not retained. This inventory is metadata evidence, not an import archive or frozen source backup.",
            ],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="https://www.pujolsluis.com/")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-pages", type=int, default=250)
    parser.add_argument("--max-assets", type=int, default=0)
    args = parser.parse_args()
    if args.max_pages < 1 or args.max_assets < 0:
        parser.error("max-pages must be positive and max-assets nonnegative")
    report = Capture(args.source, max_pages=args.max_pages, max_assets=args.max_assets).capture()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "observations.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"], indent=2))


if __name__ == "__main__":
    main()
