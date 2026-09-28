# Security review checklist

The Step-5 sweep: OWASP Top 10:2025 classes, ASVS 5.0 mapped where useful,
plus the LLM Top 10 (2026) and Agentic (2026) families. Walk the sections the
target touches — skip the rest, and say which sections you walked in the
report's evidence section. Every item is phrased as **what to look for**, not
a blacklist: on its own a match is a candidate, not a finding. Send every
candidate through the Step-6 triage rubric before it reaches the report.

Standards note: ASVS 5.0 renumbered every chapter — 4.0 requirement IDs do
not carry over (`V2.1.1` did not mean in 4.0 what it means in 5.0). Cite 5.0
IDs only, and verify the current edition when a review's output cites one.
This mapping was last checked against the editions named in
[provenance.md](provenance.md).

## Contents

- Input handling (A05)
- Authentication & sessions (A07)
- Access control & authorization (A01)
- Server-side request forgery (A01)
- File handling (A01)
- Insecure design & business logic (A06)
- Cryptography & data protection (A04)
- Configuration & hardening (A02)
- Dependencies & supply chain (A03)
- Integrity & deserialization (A08)
- Logging, error handling & exceptional conditions (A09/A10)
- LLM features (LLM Top 10 2026)
- Agentic features (Agentic Top 10 2026)

## Input handling (A05)

- Where does untrusted input enter, and is validation done **server-side at a
  trusted layer** (not in the client, not in a disabled feature flag)?
- Are data-access queries parameterized, or built by string interpolation /
  concatenation (SQL, NoSQL, GraphQL, LDAP, ORM raw fragments)? Raw-fragment
  APIs (`$queryRawUnsafe`, `.raw()`, `createNativeQuery`) are candidates even
  when the ORM is otherwise used.
- Are OS commands invoked with an argv array (no shell string), and are any
  arguments still attacker-controlled?
- Is input length/size bounded before expensive parsing (regex, XML, JSON,
  archives)?
- Is validation allowlist-based where the domain permits it? A denylist that
  filters known-bad tokens is a candidate whenever an encoding variant slips
  through.
- Is output encoded for its actual context — HTML body, attribute, URL, JS,
  CSS, SQL, shell are different rules? A sanitizer used in the wrong context
  is a candidate.
- Are raw-HTML sinks fed by user data (`innerHTML`, `dangerouslySetInnerHTML`,
  `v-html`, `|safe`, `document.write`)?
- Are templates built from user input (SSTI), including email/report
  templates and `format`-style APIs where the user controls the template?
- Are XML parsers configured with external entity resolution disabled (XXE,
  now filed under misconfiguration) and DTDs limited?
- Are headers, cookies, and query strings treated as untrusted input (CRLF /
  log / header injection)?

## Authentication & sessions (A07)

- How are passwords hashed? Argon2id/bcrypt/scrypt are acceptable; MD5/SHA-1/
  SHA-256 alone with no work factor is a candidate. Is the salt per-user and
  managed by the KDF?
- Is login rate-limited / anti-automated against credential stuffing, and is
  account lockout safe from denial-of-service abuse?
- Are session tokens from a CSPRNG with 128+ bits entropy, rotated on login,
  and revoked on logout, password change, and account disable?
- Are cookies `HttpOnly`, `Secure`, and `SameSite=Lax` or stricter? Is the
  session cookie scoped narrowly?
- On JWTs: is the algorithm pinned server-side, the signature actually
  verified (not `decode`), and `exp`/`aud`/`iss` checked? `alg: none`,
  algorithm confusion, and trusting unverified claims are candidates.
- Are password-reset / magic-link / OTP tokens single-use, short-lived, bound
  to the account, and invalidated after use?
- Is MFA available/enforced for sensitive operations, and are recovery paths
  not weaker than the factor they recover?
- Do error messages or timing allow user/account enumeration?

## Access control & authorization (A01)

- Is authorization enforced server-side on **every** request that touches
  protected data or actions — and at a layer the client cannot influence?
- Locate the centralized enforcement first (middleware, base controller,
  policy layer, RLS). A route that inherits it is not a finding; a route that
  bypasses or opts out is.
- Are object-level checks verifying **ownership/tenancy** (this user may touch
  this row), not merely "is authenticated"? IDOR/BOLA lives here: sequential
  ids, predictable references, `findById` with no owner predicate.
- Are function-level checks verifying **role/permission** (admin actions,
  privileged endpoints, background tasks, GraphQL mutations), with deny by
  default?
- Can a user change a value they should not (role, tenant, price, quantity,
  state transition, `is_admin` on a profile update) — mass assignment?
- Is CORS intentional? Reflect-any-origin, `*` with credentials, or a regex
  whose dot is unescaped are candidates.
- Are state-changing requests protected against CSRF (token or SameSite +
  origin check) — including cookie-authenticated APIs?
- Are redirect targets validated against an allowlist (open redirect), and
  are post-login `return` parameters safe?
- Do cached/shared responses leak per-user data (missing `Cache-Control:
  no-store` on authenticated responses)?

## Server-side request forgery (A01)

- Can a user-supplied URL reach a server-side fetch, webhook, import,
  preview, or image proxy?
- Is the destination validated against an allowlist of hosts/schemes, and
  re-validated after DNS resolution (blocking private, loopback, link-local,
  and metadata ranges — `169.254.169.254`, `fd00::/8`)?
- Are redirects followed blindly to a new host, and are each hop's
  destination re-validated?
- Is the cloud metadata service reachable from the application (IMDSv1
  permitted, no egress policy)?

## File handling (A01)

- Is upload type validated by content (magic bytes) rather than extension or
  client `Content-Type` alone?
- Are uploads stored outside the web root and served with a non-executable
  content type / `Content-Disposition`?
- Are size limits and quotas enforced before writing?
- Are paths built from user input canonicalized and confined to a base
  directory (no `..`, no absolute-path override, no symlink escape)?
- Does archive extraction guard against path traversal and zip bombs?
- Are file names used in responses/headers sanitized (header injection,
  reflected download names)?

## Insecure design & business logic (A06)

- Are prices, quantities, roles, and state transitions decided server-side
  from authoritative data, never accepted from the client?
- Are rate limits present on login, password reset, OTP, signup, search, and
  expensive operations?
- Can multi-step flows be skipped, reordered, or replayed (missing one-time
  token, missing idempotency key, missing state check)?
- Are balance/inventory/coupon/seat updates atomic (no check-then-write
  race)? Look for read-modify-write across requests/tasks.
- Is there a fail-open default anywhere (error → allow, missing config →
  permissive)? The safe default denies.
- Are quotas/limits enforced per user/tenant, not only globally?
- Does a discount/referral/refund path let the caller choose the amount or
  the beneficiary?

## Cryptography & data protection (A04)

- Is sensitive data encrypted in transit (TLS 1.2+, certificate verification
  on) and at rest where required?
- Is authenticated encryption used (AES-GCM / ChaCha20-Poly1305), with unique
  IVs/nonces per encryption and keys from a KMS/secret store — no ECB, no
  static IV, no unauthenticated CBC?
- Is randomness from a CSPRNG, never `Math.random`/`rand()`/`uuid` for
  tokens?
- Are secrets and tokens compared in constant time where timing is
  observable?
- Are password hashes, keys, and secrets absent from code, git history,
  container layers, build args, client bundles, and logs? Cite the variable
  name, never the value.
- Is sensitive data absent from URLs, query strings, referrers, and error
  reports?
- Are key-rotation and secret-scoping paths sane (one key per environment,
  scoped per service)?

## Configuration & hardening (A02)

Detail lives in [config-and-supply-chain.md](config-and-supply-chain.md);
the candidates to notice:

- Debug/verbose errors, profiler routes, or dev tooling reachable in
  production; stack traces or config dumps shown to users.
- Default credentials, sample/admin accounts, or default keys left in place.
- Unused features, ports, endpoints, HTTP methods, or admin consoles exposed.
- Missing or permissive security headers: CSP with `unsafe-inline`/
  `unsafe-eval` or absent, missing HSTS, missing `nosniff`, weak
  `Referrer-Policy`, no `frame-ancestors`/`X-Frame-Options`.
- Buckets/objects publicly readable or writable; databases/caches publicly
  accessible; broad firewall rules.
- Containers running as root, privileged mode, host mounts, secrets in image
  layers, unpinned base images.
- TLS downgrades disabled correctly; client verification not globally
  disabled (`verify=False`, `rejectUnauthorized: false`,
  `InsecureSkipVerify: true`).

## Dependencies & supply chain (A03)

Detail in [config-and-supply-chain.md](config-and-supply-chain.md):

- Lockfile committed and enforced by the build (a lockfile the install can
  silently rewrite is not a control); floating ranges in production builds.
- Dependencies with known vulnerabilities where the vulnerable path is
  actually reachable in this code (check reachability before rating).
- Package-name lookalikes / internal names claimable publicly / registry
  config that falls through to a public registry for internal scopes.
- Install scripts (`postinstall`, `setup.py`) executing untrusted code with
  build credentials.
- Third-party scripts loaded without SRI; remote assets unpinned.
- CI workflows: `pull_request_target`/`workflow_run` checking out untrusted
  code, expression interpolation into `run:`, unpinned third-party actions.
  (Harden-the-pipeline findings route to `securing-ci`.)
- Artifact/release signing and verification; provenance (SLSA/Sigstore)
  claims that are never verified before deploy.

## Integrity & deserialization (A08)

- Is untrusted data deserialized with a native format (`pickle`, `Marshal`,
  `ObjectInputStream`, `BinaryFormatter`, `yaml.load`)? JSON with a type
  allowlist is the baseline; schema validation where the payload is complex.
- Are serialized objects carrying type/class metadata (type-name handling,
  polymorphic deserializers) reachable from untrusted input?
- Do auto-update / plugin pipelines verify signatures before executing?
- Are integrity tokens (JWT, SAML, webhooks, cookies) verified — signature,
  issuer, audience — before their claims are trusted?

## Logging, error handling & exceptional conditions (A09/A10)

- Are authentication events, authorization failures, and security-control
  failures logged — and do the logs carry when/where/who/what?
- Are logs free of credentials, tokens, PII, and secret values; is user input
  encoded to prevent log injection?
- Are logs protected from tampering and shipped off-box (or at least
  append-only), with retention?
- Do errors fail closed (deny, not allow)?
- Do users get generic errors while detail stays in logs?
- Are empty `catch` blocks / swallowed errors / bare `except` reviewed — a
  silent failure can hide an attack in progress?
- Are exceptional conditions (timeout, partial write, overflow, malformed
  input) handled without corrupting state or skipping authorization?

## LLM features (LLM Top 10 2026)

For applications that call a model (chatbots, RAG, copilots, tool callers).
Cite the risk ID **with its name** — editions reuse numbers:

- **LLM01 Prompt injection**: can untrusted text (user input, web pages,
  email, RAG chunks, uploaded images/audio, tool output) steer a model that
  holds privileges? No complete fix exists — fence untrusted content,
  keep privileges out of reach, monitor.
- **LLM02 Sensitive information disclosure**: is PII/training/RAG data
  limited to what this caller may see, filtered from context, and stripped
  from logs?
- **LLM03 Excessive agency**: are tools minimal and scoped; are destructive
  actions gated on human approval; are credentials scoped per task rather
  than broad?
- **LLM04 Supply chain**: are models, adapters, and MCP servers pinned and
  from verified sources, with signatures checked?
- **LLM05 Data/model poisoning**: are fine-tune and ingestion sources
  validated, with integrity tests before deployment?
- **LLM06 Unbounded consumption**: per-user/key rate limits and per-request
  caps on tokens, tool calls, and cost; hard timeouts; runaway-loop guards.
- **LLM07 Misinformation**: grounding/citations for high-stakes answers,
  confidence surfaced, AI provenance disclosed?
- **LLM08 Hidden context exposure**: assume the system prompt, tool schemas,
  and other hidden context are extractable — are secrets and authorization
  decisions kept out of them?
- **LLM09 Vector/embedding weaknesses**: are vector stores tenant-isolated
  and retrieval access-controlled per caller, with chunk integrity checks?
- **LLM10 Improper output handling**: is **all** model output — including
  generated code and tool arguments — validated, escaped, or sandboxed
  before any sink (SQL, shell, HTML, code execution, another tool)?

## Agentic features (Agentic Top 10 2026)

For systems that plan, call tools, or keep memory. Cite ASI IDs with names:

- **ASI01 Agent goal hijack**: can retrieved/tool content rewrite the
  agent's objectives? Goal boundaries and behavior monitoring?
- **ASI02 Tool misuse**: least privilege per tool, validated I/O, no
  general-purpose shell/HTTP tool unless required.
- **ASI03 Identity & privilege abuse**: delegated credentials are
  short-lived and scoped to the task, never an admin token or the user's
  full session; role chains verified.
- **ASI04 Agentic supply chain**: plugins/MCP servers verified, sandboxed,
  allowlisted.
- **ASI05 Unexpected code execution**: generated code runs sandboxed, with
  static analysis and approval before anything touches the host.
- **ASI06 Memory/context poisoning**: writes to memory/vector stores pass
  validation, and stored content cannot persist instructions across trust
  levels.
- **ASI07 Insecure inter-agent communication**: messages authenticated and
  integrity-checked; the receiver does not trust the sender's identity
  claims.
- **ASI08 Cascading failures**: step/retry/fan-out limits and circuit
  breakers between components; one bad output cannot take down the chain.
- **ASI09 Human-agent trust exploitation**: AI content labelled; approval
  prompts show the real action so the agent cannot talk the user into
  approving something else.
- **ASI10 Rogue agents**: tool calls logged, behavior monitored, a kill
  switch exists.

Standards are maps, not verdicts: a match still needs a completed
entry-point → boundary → sink path and a triage disposition.
