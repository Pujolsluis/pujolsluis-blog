# Content publication boundary

Production content has not been imported. MIG-02's importer writes the normalized v1 `content.json` and its private source report to an owner-controlled directory **outside Git checkouts**. Never put raw WXR, drafts, password-protected posts, private metadata reports or owner media archives here.

The renderer can consume a separately reviewed public content bundle. MIG-08 will reconcile that bundle with the owner export, full original media archive, frozen rendered snapshots and route inventory before promoting publication artifacts into the repository. Synthetic fixture development uses `fixtures/v1/content.json`; it is not production content or source-completeness evidence.
