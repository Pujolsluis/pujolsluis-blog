# MIG-04 renderer evidence

This document records a **partial foundation** for issue #4. It does not close the issue or prove source fidelity.

| Acceptance criterion | Evidence | Result / blocker |
| --- | --- | --- |
| Static fixture renderer | Astro 7.4.2; immutable MIG-01 contracts at `5a6c288`; `npm run build` renders 2 synthetic content records and the root archive | Implemented for fixtures |
| Preserved HTML/media | Tests cover Unicode, code indentation, caption/alt text, source calendar date, anchors, normalized gallery HTML, declared iframe identity, original media bytes/checksum | Implemented for represented fixture cases |
| Root and repository prefix | Full builds at `/` and `/pujolsluis-blog/` verify local links/fonts/styles/media exist; extra encoded `/caf%C3%A9/` route exercises filesystem behavior; content 1.1.0 portfolio route renders independently of the blog feed | Automated checks pass |
| Draft exclusion / staging | Tests exclude synthetic draft/future/private/pending records and future published records; full builds omit private title/path/media; every output page noindex, no CNAME/sitemap, disallow robots | Automated checks pass |
| Source layout observation | Public homepage HTML fetched 2026-10-24 and decoded from gzip; observed centered site identity, Home/Activities links, previews with category/date metadata, right sidebar, TheBlogger references, Karla/Coustard requests | Original structural foundation only; no proprietary theme files copied |
| Desktop/tablet/mobile visual equivalence | Source browser navigation attempted through CUA, returned `net::ERR_BLOCKED_BY_CLIENT` | **Not verified**. No baseline screenshots available; all viewport comparison gates remain open |
| Keyboard navigation | Semantic anchors/nav/main, skip link, current-page marker, visible focus styles; no custom interactive controls | Markup implemented; browser keyboard walkthrough still required |
| Theme/widgets/behavior fidelity | Owner-provided TheBlogger 2.3.3 theme backup inspected read-only; exact observed settings and required source features documented in `theme-observations.md` | In progress. Search, likes, forms, commerce, lightbox and other plugin functionality are not claimed |
| Documentation | `site/README.md`, `public/theme/LICENSES.md`, pinned package lock, this report | Inputs/outputs/errors/commands documented |

Local validation: Node 26.0.0, npm 11.12.1, macOS, 2026-10-24. `npm run test:rendering` passes 11 tests; the suite performs two complete temporary static builds. `npm run build` passes, producing three fixture HTML routes. `npm install --ignore-scripts` reports zero known vulnerabilities at collection time. Tests are structural and integrity evidence, not screenshot/behavior parity evidence.

The final checkpoint also consumes the isolated approved content 1.1.0 extension from importer commit `e5c7fcd`, preserving portfolio kinds and source types. Full temporary builds exercise that version while committed legacy fixtures remain content 1.0.0. Original/runtime route spellings and decoded output collisions, encoded control characters, physical output-directory protection and private media exclusion are checked. Python 3.12.14 Ruff and all 18 Python safety/contract tests pass locally. The Node 24 GitHub CI run for prior checkpoint `0ad167b` passed `check-build` and skipped deployment; the final hardening checkpoint must also pass its own run before review acceptance.

The workflow now installs Node 24 through latest stable `actions/setup-node` v7.1.0 at `949feb2413d6458794dcd2491c4babbbce0c15c1`, installs the lockfile with lifecycle scripts disabled, lints/type-checks, tests and builds synthetic fixtures into `${runner.temp}/renderer-fixture-dist`. The Python placeholder builds last into `dist` and remains the only deployed artifact. Full MIG-07 fidelity gates are still incomplete. Existing checkout/setup-python/upload-artifact/deploy-pages release tags and full SHAs were reverified against the official GitHub release/tag APIs on 2026-10-24 and retained.

`npm run lint` uses ESLint 10.13.0 and `astro check` 0.9.12 with TypeScript 6.0.3, the latest TypeScript major supported by that checker's declared peer range. It reports zero errors, warnings or hints. TypeScript 7.0.2 was rejected by normal dependency resolution rather than forcing an unsupported peer combination. Latest stable setup-node release/source: https://github.com/actions/setup-node/releases/tag/v7.1.0 .

Do not deploy this artifact as a completed migration, approve domain cutover, merge a fidelity-complete claim or close #4 based on this evidence. PR merging requires the owner's explicit approval.
