# MIG-02 fixture implementation evidence

Issue: [MIG-02 #2](https://github.com/Pujolsluis/pujolsluis-blog/issues/2). Depends on the MIG-01 v1 contracts from PR #11. This is fixture implementation evidence, not production migration acceptance.

Verified locally with Python 3.12.14, Ruff 0.14.2 and jsonschema 4.26.0:

```sh
python -m unittest discover -s tests/import_content -v
python -m unittest discover -s tests -v
ruff check --no-cache .
```

- Importer suite: 29 tests pass. Root suite: 44 tests pass, including importer discovery, contract/reconciliation and preview safety tests. Ruff passes. Existing pinned GitHub Actions/workflow/dependency files are unchanged by MIG-02.
- Synthetic complete WXR reconciles all 5 source IDs: 2 public content records, 1 attachment delegated to MIG-03, 1 excluded draft and 1 excluded password-protected page. Every ID receives a disposition in the private report. Both imported public records validate against the v1 content/assets/routes contracts.
- Exact body equality verifies Unicode, HTML ordering, heading IDs, local anchors, iframe markup and multiline code indentation. Original GUID, author/category/tag identities, excerpt and featured attachment are checked independently. Local/GMT pairs preserve their offsets and instants; no timezone name is invented.
- Repeat imports produce byte-identical serialized bundle/report for the same input. Reordering WXR items leaves the public bundle identical. Final full-export comparison reports changed/removed records, with an unchanged case; the new bundle equals a fresh complete import, preventing stale records from surviving.
- Failure coverage includes missing/stale/tampered/unresolved snapshots, unverified direct HTML, unknown blocks/shortcodes/XML structures/custom post types/taxonomies/meta, duplicate source IDs/canonical paths/singleton fields, invalid dates, traversal/query/credential paths, attachment identity gaps, comment parent cycles/nonpublic parents and unsafe comment markup. Structured failure diagnostics identify public source IDs and URLs; no partial public bundle is returned.
- Privacy coverage verifies draft/password source bodies, comment emails/IP/agent fields and unapproved comments are absent from public content. CLI tests verify modes 700/600, Git/symlink output guards, per-file atomic replacement, success-report bundle checksum and retaining the prior successful bundle after a failed import.

Remaining source gates: no owner WXR, original media bytes/archive or frozen rendered snapshots are available. Public inventories cannot supply raw source identity or prove completeness. Portfolio/custom content and behavior require explicit contract decisions; menu ordering, parent hierarchy, sticky state and plugin metadata are retained privately and flagged for downstream handling. Media/srcset/CSS mapping, route/archive completeness, visual/browser parity, accepted backend behavior, final owner reconciliation and launch approval belong to later gates. No production content, DNS, custom-domain, merge or deployment changes are included.
