# Project rules — miniframework fixture

## Model binding policy

- `reference/model-routing.md` is the single home of model IDs. Skills
  reference roles, never model IDs.
- `agents/*.md` bind the free default in `model:` frontmatter.
- Hard exclusions in model-routing.md are absolute.
- Catalogs: fetch the live endpoints in model-routing.md's update
  procedure, or use local snapshots under
  `reference/catalog-snapshot/` when offline.
