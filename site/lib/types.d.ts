export interface TaxonomyTerm { sourceId: string; slug: string; name: string }
export interface Comment { sourceId: string; parentId: string | null; authorName: string; publishedAt: string; html: string; status: 'approved' }
export interface ContentItem {
  sourceId: string;
  kind: string;
  status: string;
  path: string;
  canonicalUrl: string;
  title: string;
  language: string;
  publishedAt: string;
  modifiedAt: string;
  author: { sourceId: string; name: string };
  categories: TaxonomyTerm[];
  tags: TaxonomyTerm[];
  content: { format: string; original: string; html: string; provenance: Record<string, string> };
  sourceMetadata: { guid: string; excerptHtml: string; commentStatus: string; pingStatus: string; featuredAssetId: string | null; sourceType?: string };
  assetIds: string[];
  embeds: { provider: string; url: string; html: string }[];
  comments: Comment[];
}
export interface Route { path: string; kind: string; contentId?: string; target?: string; query: string; fragments: string[] }
export interface Asset { assetId: string; sourceUrl: string; localPath: string; sha256: string; bytes: number; mimeType: string; width: number | null; height: number | null; owned: boolean }
export interface Bundle {
  config: { base: string; siteUrl: string; buildTime: Date; inputDir: string; outDir: string };
  items: ContentItem[];
  routes: Route[];
  assets: Asset[];
  origins: Set<string>;
  allRoutes: Route[];
}
