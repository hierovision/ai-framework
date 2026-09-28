# Configuration & supply chain review

Where A02 (misconfiguration) and A03 (supply chain) findings actually live:
Dockerfiles, Kubernetes manifests, Terraform, framework settings, security
headers, lockfiles, install scripts, and CI workflow definitions. These files
are small, high-signal, and frequently unreviewed — list them before reading
application code.

Boundary: this file is a **review surface**. It tells a security review what
to look for in config/deps/CI. Hardening the pipeline itself (OIDC vs PATs,
environment scoping, least-privilege `permissions:`, branch protection,
SHA-pinning as a remediation pass) is `securing-ci`'s job — findings there
route to that skill.

Same reporting bar as code: a permissive setting in a file that never reaches
production, or one already constrained by a layer above it, is
defense-in-depth — report it as such. Run every candidate through the Step-6
triage rubric.

## Contents

- Where to look first
- Containers (A02)
- Kubernetes (A02)
- Cloud & Terraform (A02)
- Application & web server config (A02)
- Security headers (A02)
- Dependency manifests & lockfiles (A03)
- Dependency confusion & typosquatting (A03)
- Install scripts (A03)
- CI workflow patterns (A03)
- Provenance, signing & SBOM (A03)

## Where to look first

| Surface | Files |
|---|---|
| Containers | `Dockerfile*`, `docker-compose*.yml`, `.dockerignore` |
| Orchestration | `k8s/**/*.yaml`, `helm/**/values.yaml`, `*.deployment.yaml` |
| Infrastructure | `*.tf`, `*.tfvars`, `cdk/**`, `template.yaml` (SAM), `serverless.yml` |
| App config | `settings.py`, `application*.yml`, `appsettings*.json`, `next.config.js`, `.env*` |
| Web server | `nginx.conf`, `httpd.conf`, ingress annotations |
| Dependencies | `package.json` + lockfile, `requirements.txt`, `pyproject.toml`, `go.mod`, `pom.xml`, `Gemfile`, `Cargo.toml` |
| Registry config | `.npmrc`, `pip.conf`, `settings.xml`, `.yarnrc.yml` |
| Pipelines | `.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`, `azure-pipelines.yml` |

Two questions cut through most of it: **what runs as root or with wildcard
permissions**, and **what executes code someone outside the repo controls**.

## Containers (A02)

```dockerfile
# UNSAFE
FROM node:latest                    # unpinned — changes under you
COPY . .                            # no .dockerignore: .env, .git, keys land in the layer
RUN npm install                     # install can rewrite the lockfile
ARG NPM_TOKEN                       # build args are visible in image history
ENV API_KEY="sk-live-EXAMPLE"       # baked into the image, readable by anyone who pulls
USER root                           # default when USER is absent
CMD ["npm", "start"]
```

```dockerfile
# SAFE
FROM node:22.11.0-alpine@sha256:...  # pinned by digest
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev                # honors the lockfile exactly
COPY --chown=node:node . .           # with .dockerignore covering .git/.env/secrets
USER node                            # non-root
CMD ["node", "server.js"]
```

Candidates: `USER` absent (the common case), secrets in `ENV`/`ARG`/`RUN`
(`docker history` shows every layer; deleting in a later layer does not remove
it), `COPY . .` without `.dockerignore`, `curl … | sh` build steps, `latest`
or floating tags, `--privileged`, `network_mode: host`, docker-socket mounts
(`/var/run/docker.sock` is host root in practice), `apt-get` without pinned
versions, writable filesystems where read-only would do.

## Kubernetes (A02)

Candidates: `privileged: true`, `hostNetwork`/`hostPID`/`hostPath`,
`allowPrivilegeEscalation` not false, capabilities not dropped, secrets as
literal `value:` in a manifest (base64 in a `Secret` is encoding, not
encryption), `automountServiceAccountToken` left on where the pod never calls
the API server, missing resource limits (node-wide DoS), no NetworkPolicy
(every pod reaches every pod by default), RBAC granting `cluster-admin` or
`*` verbs, images by mutable tag, service accounts shared across workloads,
ingress without TLS, missing `seccompProfile`/`runAsNonRoot`.

## Cloud & Terraform (A02)

```hcl
# UNSAFE
resource "aws_s3_bucket_public_access_block" "b" {
  block_public_acls = false                      # public-ACL guard off
}
resource "aws_security_group_rule" "ssh" {
  type        = "ingress"
  from_port   = 22
  to_port     = 22
  cidr_blocks = ["0.0.0.0/0"]                    # SSH open to the internet
}
resource "aws_db_instance" "db" {
  publicly_accessible = true
  storage_encrypted   = false
}
data "aws_iam_policy_document" "p" {
  statement {
    actions   = ["*"]
    resources = ["*"]                            # wildcard on wildcard
  }
}
```

Candidates: storage public (S3 ACLs/policies, GCS `allUsers`, Azure blob
public access), `0.0.0.0/0` on anything but 80/443 (SSH, RDP, DB ports, admin
panels), encryption at rest disabled, TLS not enforced, IAM `"*"` actions or
resources or `"*"` principals, managed databases/caches publicly accessible,
audit logging (CloudTrail, flow logs) disabled or unretained, secrets in
`.tfvars` or committed state (state stores values in cleartext), IMDSv1 still
permitted on EC2 (`http_tokens = "optional"` — the SSRF-to-credentials path).

## Application & web server config (A02)

Candidates: debug/verbose error modes reachable in production (Django
`DEBUG = True`, Rails `consider_all_requests_local`, Node stack traces),
committed development secrets or the same key across environments, CORS `*`
combined with credentials or origin reflection or an unescaped-dot regex
matching `evil-myapp.com`, directory listing enabled, `.git/`/`.env`/backups/
`/actuator`/`/metrics`/GraphQL introspection served publicly, default admin
consoles mounted without auth (phpMyAdmin, Kibana, Grafana), TLS below 1.2 or
weak ciphers, client certificate verification disabled (`verify=False`,
`rejectUnauthorized: false`, `InsecureSkipVerify: true`), session cookie flags
missing, permissive `ALLOWED_HOSTS`.

## Security headers (A02)

| Header | Recommended value | Why it matters |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'` | Last line of defense for XSS. `unsafe-inline`/`unsafe-eval` largely negates it — prefer nonces or hashes. |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Prevents downgrade/stripping. |
| `X-Content-Type-Options` | `nosniff` | Stops MIME sniffing turning an upload into script. |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Keeps paths and tokens out of `Referer`. |
| `Cache-Control` | `no-store` on authenticated responses | Prevents shared-cache leakage. |
| Cookies | `HttpOnly; Secure; SameSite=Lax` | XSS theft + cross-site request defense. |

`frame-ancestors` supersedes `X-Frame-Options`; setting both is harmless.
Absence is only a finding when the target actually serves browser content —
an API returning JSON has different exposure than an HTML app.

## Dependency manifests & lockfiles (A03)

The recurring A03 finding is a lockfile that is missing, or one the build is
allowed to rewrite — what ships can then differ from what was reviewed.

| Ecosystem | Does not enforce the lock | Fails the build when the lock is missing/out of sync |
|---|---|---|
| npm | `npm install` (updates the lock on disagreement) | `npm ci` |
| Yarn 2+ | `yarn install` outside CI | `yarn install --immutable` (the CI default) |
| Yarn 1 | `yarn install`; `--frozen-lockfile` still succeeds with no lockfile | `yarn install --frozen-lockfile` **plus** an explicit lockfile-exists check |
| pnpm | `pnpm install` outside CI | `pnpm install --frozen-lockfile` (CI default when a lock exists) |
| pip | `pip install -r requirements.txt` without hashes | `pip install --require-hashes -r requirements.txt` |
| uv | `uv sync`, `uv sync --frozen` (uses the lock without checking it is current) | `uv sync --locked` |
| Poetry | `poetry install` | `poetry check --lock` before install |
| Go | `-mod=mod` (updates `go.mod`) | default `-mod=readonly` + committed `go.sum` |
| Rust | `cargo build` (may update `Cargo.lock`) | `cargo build --locked` |
| Gradle | dynamic versions; CI runs with `--write-locks`/`--update-locks` | committed `gradle.lockfile` with strict mode |
| Maven | version ranges in `pom.xml` | no native lockfile — pin exact versions, forbid ranges |

Candidates: lockfile missing or gitignored, a production build step that can
rewrite it, floating ranges (`^`, `~`, `*`, `latest`) with no enforced lock,
`requirements.txt` without `==`, lockfile `resolved` URLs pointing at an
unexpected registry, a vulnerable dependency whose code path is actually
reachable (check reachability before rating), a dependency bumped by a bot
with no review of the diff.

## Dependency confusion & typosquatting (A03)

An internal package name that is not registered publicly can be claimed by an
attacker; a higher public version then wins resolution when the build falls
back to the public registry.

Candidates: unscoped internal names or scopes not pinned to an internal
registry, a proxy/mirror falling through to the public registry for internal
names, `pip install --extra-index-url` (pip picks the highest version across
**all** indexes — use `--index-url` with one trusted mirror), names one edit
away from a popular package, very recent first-publish dates, a maintainer
change on a critical dependency, git/URL dependencies pinned to a branch
rather than a commit SHA.

## Install scripts (A03)

Package installation executes code: `npm install` runs `preinstall`/
`postinstall` from every package in the tree with the developer's or runner's
privileges; `pip` may execute `setup.py`.

```json
{ "scripts": { "postinstall": "node ./scripts/collect.js" } }
```

Candidates: install hooks that touch the network, read credentials, or write
outside the package; mitigations to recommend are `npm ci --ignore-scripts`
(then run only the builds you need), `pip install --only-binary :all:`, and
installing in a container with no credentials and no network beyond the
registry.

## CI workflow patterns (A03)

The pipeline holds repository write access and production credentials — a
higher-value target than the application. Review the dangerous patterns; route
the hardening pass to `securing-ci`.

```yaml
# UNSAFE — GitHub Actions
on: pull_request_target            # writable token AND secrets...
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}  # ...on fork code. RCE.
      - uses: some-org/some-action@main                   # mutable ref
      - run: echo "Title: ${{ github.event.pull_request.title }}"  # script injection
```

```yaml
# SAFE
on: pull_request                   # read-only token, no secrets for forks
permissions:
  contents: read
jobs:
  build:
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # pinned SHA
      - env:
          TITLE: ${{ github.event.pull_request.title }}
        run: echo "Title: $TITLE"  # data via env, never interpolated into the shell
```

Candidates: `pull_request_target`/`workflow_run` that checks out untrusted
code (fork code + secrets = critical), `${{ }}` interpolation of
attacker-controllable fields (PR title, branch name, issue body, commit
message) directly into `run:`, third-party actions referenced by tag/branch,
`permissions:` unrestricted, secrets echoed or passed to untrusted steps,
self-hosted runners on public repos, no required checks/branch protection on
the deploying branch.

## Provenance, signing & SBOM (A03)

- SBOM (CycloneDX/SPDX) generated as a build artifact, not a one-off report.
- Signatures verified before deploy (`cosign verify`, `npm audit signatures`,
  Sigstore attestations) — a failed verification blocks the deploy.
- Publishing with provenance (`npm publish --provenance`, SLSA attestations)
  so consumers can see which workflow/commit produced an artifact.
- Container images pinned by digest.
- Continuous dependency monitoring matters more than a point-in-time audit —
  a dependency was clean on the day it was reviewed, not forever.
