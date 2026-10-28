#!/usr/bin/env python3
"""Shared OpenCode V2 adapter — the ONE home for version-specific facts.

Every framework script that talks to OpenCode (dispatcher, completion observer,
watchdog, session guard, eval runner, operational scripts) imports this module
instead of re-deriving V1 facts. Contracts kept above this layer: dispatch CLI,
heartbeat lines, run-log shape, exit codes, eval predicates.

Facts encoded here (validated live against opencode 2.1.4, 2026-10-27):

  * binary/version probe — `opencode --version` prints `opencode v2.1.4`.
  * service discovery — `opencode service status|start` prints the URL; the
    service itself requires the `service.json` password, so typed calls go
    through `opencode api <method> <path>` (which authenticates) and fall back
    to direct HTTP only when a caller supplies an authenticated URL.
  * typed API — `GET /api/session/{id}`, `GET /api/session/active`,
    `POST /api/session/{id}/agent {agent}`, `POST /api/session/{id}/prompt
    {text}`, `POST /api/session/{id}/interrupt`, `GET /api/session/{id}/log`.
  * storage — V2 reads/writes `session_v2`, `session_message`, `session_inbox`,
    `event`; V1 `session`/`message`/`part` are migration sources.
  * permissions — ordered `{action, resource, effect}` rules; last matching
    rule wins; `external_directory` defaults to allow, so a deny-first rule
    followed by explicit `<abs>/**` allows is the grant mechanism.
  * stream — newline JSON with top-level `type` in {step_start, text, tool_use,
    step_finish, error} and `part.type` in {step-start, text, tool,
    step-finish, reasoning}; tool names are `shell`, `read`, `edit`, `glob`,
    `grep`, `subagent`, not V1 `bash`/`write`/`patch`/`task`.

DB access is read-only (`file:...?mode=ro`). The only mutating calls are
`session.interrupt`, `session.agent`, and `session.prompt` (wake), never a
delete and never a direct DB write.

`OPENCODE_DB_PATH` is the highest-precedence test override, then
`OPENCODE_DB`, then the vendor location (`opencode debug paths db`).
"""
import json
import os
import re
import sqlite3
import subprocess
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_DB = os.path.expanduser("~/.local/share/opencode/opencode.db")
VERSION_PIN = "2.1.4"

# Tool vocabulary (V1 -> V2). Consumer evals may still emit V1 names; callers
# that accept aliases log them (see run_behavioral_eval).
TOOL_ALIASES = {
    "bash": "shell",
    "write": "edit",
    "patch": "edit",
    "task": "subagent",
}

DENIAL_RE = re.compile(
    r"cannot ask the user for permission|auto-reject|permission requested|"
    r"permission denied|external_directory",
    re.IGNORECASE,
)


def binary():
    """The opencode executable (test seam: OPENCODE_BIN)."""
    return os.environ.get("OPENCODE_BIN") or "opencode"


def now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


# --- DB resolution -----------------------------------------------------------

def db_path():
    """OPENCODE_DB_PATH > OPENCODE_DB > vendor location."""
    explicit = os.environ.get("OPENCODE_DB_PATH")
    if explicit:
        return os.path.expanduser(explicit)
    env_db = os.environ.get("OPENCODE_DB")
    if env_db:
        return os.path.expanduser(env_db)
    return DEFAULT_DB


def connect(path=None):
    """Read-only connection, or None when the DB is absent/unreadable."""
    path = path or db_path()
    if not path or not os.path.isfile(path):
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        return con
    except sqlite3.Error:
        return None


def table_exists(con, name):
    cur = con.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def columns(con, name):
    try:
        cur = con.cursor()
        cur.execute(f"PRAGMA table_info({name})")
        return [r[1] for r in cur.fetchall()]
    except sqlite3.Error:
        return []


# --- service discovery / typed API ------------------------------------------

_service_cache = {"url": None, "checked": False}


def service_url(explicit=None):
    """An authenticated service URL: explicit > env > `service status`."""
    if explicit:
        return explicit.rstrip("/")
    if os.environ.get("OPENCODE_V2_NO_SERVICE") == "1":
        return None
    for key in ("OPENCODE_V2_SERVICE_URL", "OPENCODE_WAKE_URL"):
        value = os.environ.get(key)
        if value:
            return value.rstrip("/")
    if _service_cache["checked"]:
        return _service_cache["url"]
    _service_cache["checked"] = True
    url = None
    try:
        proc = subprocess.run([binary(), "service", "status"],
                              capture_output=True, text=True, timeout=15)
        out = (proc.stdout or "").strip()
        if out.startswith("{"):
            data = json.loads(out)
            urls = data.get("urls") or []
            if urls:
                url = urls[0].rstrip("/")
        elif out.startswith("http"):
            url = out.splitlines()[0].strip().rstrip("/")
    except (OSError, ValueError, subprocess.SubprocessError):
        url = None
    _service_cache["url"] = url
    return url


def reset_service_cache():
    _service_cache["url"] = None
    _service_cache["checked"] = False


def _http(method, url, body=None, timeout=10):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, _loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, _loads(raw)
    except OSError:
        return None, None


def _loads(raw):
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return raw


def api_call(method, path, body=None, server=None, timeout=30):
    """Typed API call. Returns `(status, payload)`; `(None, None)` on failure.

    Uses `opencode api` (authenticated service gateway) by default, which
    prints the response body and appends `HTTP <code>` for non-2xx. A
    caller-supplied authenticated URL (or env) uses direct HTTP.
    """
    method = method.upper()
    url = None if os.environ.get("OPENCODE_V2_API_VIA_CLI") == "1" \
        else service_url(server)
    if url:
        return _http(method, url + path, body, timeout=timeout)
    argv = [binary(), "api", method, path]
    if body is not None:
        argv += ["--data", json.dumps(body)]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None, None
    out = (proc.stdout or "").strip()
    payload = _loads(out) if out else None
    m = re.search(r"HTTP\s+(\d{3})", out)
    if m:
        status = int(m.group(1))
    elif proc.returncode == 0:
        status = 200
    else:
        status = None
    return status, payload


def session_get(sid, server=None):
    """(exists, payload). Unknown session -> (False, payload) on 404."""
    status, payload = api_call("GET", f"/api/session/{sid}", server=server)
    if status == 200:
        return True, payload
    if status == 404:
        return False, payload
    return None, payload  # service unreachable / unknown


def session_active(server=None):
    status, payload = api_call("GET", "/api/session/active", server=server)
    if status != 200 or not isinstance(payload, dict):
        return None
    data = payload.get("data")
    return data if isinstance(data, dict) else None


def session_switch_agent(sid, agent, server=None):
    return api_call("POST", f"/api/session/{sid}/agent",
                    {"agent": agent}, server=server)


def session_prompt(sid, text, server=None):
    return api_call("POST", f"/api/session/{sid}/prompt",
                    {"text": text}, server=server)


def session_interrupt(sid, server=None):
    return api_call("POST", f"/api/session/{sid}/interrupt", server=server)


def session_log(sid, server=None):
    return api_call("GET", f"/api/session/{sid}/log", server=server)


def list_agents(directory=None, server=None):
    """Agent IDs from the running service (config + project layout)."""
    path = "/api/agent"
    if directory:
        path += "?directory=" + urllib.parse.quote(os.path.abspath(directory))
    status, payload = api_call("GET", path, server=server)
    if status != 200 or not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, list):
        return None
    return [a.get("id") for a in data if isinstance(a, dict) and a.get("id")]


def version():
    try:
        proc = subprocess.run([binary(), "--version"], capture_output=True,
                              text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (proc.stdout or "").strip()
    m = re.search(r"(\d+\.\d+\.\d+)", text)
    return m.group(1) if m else None


# --- V2 storage readers ------------------------------------------------------

def find_session(con, sid=None, title=None, parent=None, cwd=None):
    """Newest matching `session_v2` row (V2 storage)."""
    if con is None:
        return None
    cur = con.cursor()
    if sid:
        cur.execute("SELECT * FROM session_v2 WHERE id=?", (sid,))
        return cur.fetchone()
    where, args = [], []
    if title:
        where.append("title LIKE ?")
        args.append(f"%{title}%")
    if parent:
        where.append("parent_id=?")
        args.append(parent)
    if cwd:
        where.append("directory=?")
        args.append(os.path.abspath(cwd))
    sql = "SELECT * FROM session_v2"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY time_updated DESC LIMIT 1"
    cur.execute(sql, args)
    return cur.fetchone()


def session_model(sess):
    """Resolve the `model` JSON blob to `<providerID>/<id>`; never crash."""
    try:
        raw = sess["model"]
    except (KeyError, IndexError, TypeError):
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    provider, model_id = data.get("providerID"), data.get("id")
    if not provider or not model_id:
        return None
    return f"{provider}/{model_id}"


def idle_state(sess):
    """(idle, outcome) from `time_idle`/`idle_outcome`, defensively."""
    if sess is None:
        return None, None
    keys = sess.keys()
    idle = sess["time_idle"] if "time_idle" in keys else None
    outcome = sess["idle_outcome"] if "idle_outcome" in keys else None
    return idle, outcome


def load_parts(con, sid):
    """Flat `[(time_created_ms, data_dict), ...]` view of V2 messages.

    `session_message.data` carries the message payload; assistant `content`
    blocks (reasoning/text/tool) are flattened into the V1-analogue part
    shape the watchdog/guard analyses already understand. Message-level
    `finish` becomes a `step-finish` marker. A message without `finish` is
    only open when it is the LAST assistant message; earlier messages are
    implicitly complete (V2 writes them before the next message starts).
    """
    if con is None:
        return []
    cur = con.cursor()
    cols = columns(con, "session_message")
    updated_expr = "time_updated" if "time_updated" in cols else "NULL AS time_updated"
    try:
        cur.execute(
            f"SELECT id, type, seq, time_created, {updated_expr}, data"
            " FROM session_message WHERE session_id=? ORDER BY seq",
            (sid,))
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        return []
    parsed = []
    for row in rows:
        try:
            data = json.loads(row["data"]) if row["data"] else {}
        except (TypeError, ValueError):
            data = {}
        parsed.append((row, data if isinstance(data, dict) else {}))
    last_assistant = None
    for i, (row, _data) in enumerate(parsed):
        if row["type"] == "assistant":
            last_assistant = i
    out = []
    for i, (row, data) in enumerate(parsed):
        ms = row["time_created"]
        updated = row["time_updated"]
        mtype = row["type"]
        if mtype == "assistant":
            content = data.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = (block.get("type") or "").replace("_", "-")
                    if btype == "tool":
                        part = {
                            "type": "tool",
                            "tool": block.get("name") or block.get("tool") or "?",
                            "state": block.get("state") or {},
                        }
                    elif btype == "text":
                        part = {"type": "text", "text": block.get("text") or ""}
                    elif btype in ("reasoning", "thinking"):
                        part = {"type": "reasoning",
                                "text": block.get("text") or ""}
                    else:
                        part = {"type": btype or "unknown"}
                    if updated is not None:
                        part["_time_updated"] = updated
                    out.append((ms, part))
            finished = bool(data.get("finish")) or i != last_assistant
            marker = {"type": "step-finish" if finished else "step-start"}
            if updated is not None:
                marker["_time_updated"] = updated
            out.append((updated or ms, marker))
        elif mtype in ("user", "system", "synthetic"):
            part = {"type": "message", "role": mtype,
                    "text": data.get("text") or ""}
            if updated is not None:
                part["_time_updated"] = updated
            out.append((ms, part))
        elif mtype == "idle":
            out.append((ms, {"type": "idle",
                             "outcome": data.get("outcome")}))
        elif mtype == "compaction":
            out.append((ms, {"type": "compaction"}))
    return out


def message_count(con, sid):
    if con is None:
        return 0
    try:
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM session_message WHERE session_id=?",
                    (sid,))
        return cur.fetchone()[0]
    except sqlite3.Error:
        return 0


def result_text(con, sid):
    """Final assistant text (concatenated text blocks of the last assistant
    message), or "" when there is none."""
    if con is None:
        return ""
    cur = con.cursor()
    try:
        cur.execute(
            "SELECT data FROM session_message WHERE session_id=?"
            " AND type='assistant' ORDER BY seq", (sid,))
    except sqlite3.Error:
        return ""
    texts = []
    for (raw,) in cur.fetchall():
        try:
            data = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            continue
        content = data.get("content") if isinstance(data, dict) else None
        if not isinstance(content, list):
            continue
        texts = [b.get("text") or "" for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
    return "\n".join(t for t in texts if t.strip())


def enumerate_tree(con, root_id, max_depth=2):
    """Root + descendants from `session_v2`, depth-capped."""
    if con is None:
        return []
    cur = con.cursor()
    cur.execute("SELECT * FROM session_v2 WHERE id=?", (root_id,))
    row = cur.fetchone()
    if row is None:
        return []
    nodes = []
    frontier = [(dict(row), 0)]
    seen = {root_id}
    while frontier:
        node, depth = frontier.pop(0)
        nodes.append({
            "id": node["id"], "parent_id": node.get("parent_id"), "depth": depth,
            "agent": node.get("agent"), "title": node.get("title"),
            "time_created": node.get("time_created"),
        })
        if depth >= max_depth:
            continue
        cur.execute("SELECT * FROM session_v2 WHERE parent_id=?", (node["id"],))
        for child in cur.fetchall():
            if child["id"] in seen:
                continue
            seen.add(child["id"])
            frontier.append((dict(child), depth + 1))
    nodes.sort(key=lambda n: (n["depth"], n["time_created"] or 0))
    return nodes


# --- stream normalization ----------------------------------------------------

def parse_stream(raw):
    """Return (events, parse_errors) for a newline-delimited JSON stream."""
    events, errors = [], []
    for i, line in enumerate((raw or "").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {i}: {exc.msg}")
            continue
        if isinstance(obj, dict):
            events.append(obj)
        else:
            errors.append(f"line {i}: event is not a JSON object")
    return events, errors


def _parts(events):
    for ev in events:
        part = ev.get("part") if isinstance(ev.get("part"), dict) else ev
        if isinstance(part, dict):
            yield part


def session_id_of(events):
    for ev in events:
        if ev.get("sessionID"):
            return ev["sessionID"]
        part = ev.get("part")
        if isinstance(part, dict) and part.get("sessionID"):
            return part["sessionID"]
    return None


def final_text(events):
    chunks = [p["text"] for p in _parts(events)
              if p.get("type") == "text" and isinstance(p.get("text"), str)]
    return "\n".join(chunks).strip()


def token_totals(events):
    """Sum tokens/cost across step-finish events (V2 puts them on the part)."""
    tokens_in = tokens_out = cost = None
    for part in _parts(events):
        if part.get("type") not in ("step-finish", "step_finish"):
            continue
        tk = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}
        for key in ("input", "output"):
            value = tk.get(key)
            if isinstance(value, (int, float)):
                if key == "input":
                    tokens_in = (tokens_in or 0) + int(value)
                else:
                    tokens_out = (tokens_out or 0) + int(value)
        c = part.get("cost")
        if isinstance(c, (int, float)):
            cost = (cost or 0.0) + float(c)
    return tokens_in, tokens_out, (round(cost, 6) if cost else None)


def normalized_tool_events(events):
    """Yield `{tool, status, input, target}` for every tool part.

    V1 aliases are normalized to V2 names; `filePath` -> `path`.
    """
    out = []
    for part in _parts(events):
        if part.get("type") != "tool":
            continue
        name = part.get("tool") or part.get("name") or "?"
        name = TOOL_ALIASES.get(name, name)
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        inp = state.get("input") if isinstance(state.get("input"), dict) else {}
        target = (inp.get("command") or inp.get("path") or inp.get("filePath")
                  or inp.get("pattern") or inp.get("agent") or "")
        out.append({"tool": name, "status": state.get("status"),
                    "input": inp, "target": str(target)})
    return out


def tool_name(name):
    return TOOL_ALIASES.get(name, name)


# --- permissions -------------------------------------------------------------

def grant_pattern(path):
    return os.path.join(os.path.abspath(path), "**")


def permission_rules(grants, deny_execute=True):
    """Ordered V2 rules: catch-all deny first, explicit allow roots after.

    Last matching rule wins (proved live 2026-10-27: deny `*` then allow
    `<abs>/**` permits the read). Caller grants are validated by the caller.
    """
    rules = [{"action": "external_directory", "resource": "*", "effect": "deny"}]
    for grant in grants or []:
        rules.append({"action": "external_directory",
                      "resource": grant_pattern(grant), "effect": "allow"})
    if deny_execute:
        rules.append({"action": "execute", "resource": "*", "effect": "deny"})
    return rules


def config_with_permissions(base=None, grants=None):
    """A V2 config document carrying the dispatcher's ordered rules."""
    config = dict(base) if isinstance(base, dict) else {}
    config["permissions"] = permission_rules(grants)
    return config


def write_temp_config(root, config, agents_dir=None, skills_dir=None):
    """Write `<root>/opencode/opencode.jsonc` (+ agent/skill links).

    V2 does not honor `OPENCODE_CONFIG_CONTENT`/`OPENCODE_CONFIG` for agent
    discovery (C7); the accepted injection is an XDG_CONFIG_HOME root. The
    agent corpus is linked so personas resolve in the same root.
    """
    cdir = os.path.join(root, "opencode")
    os.makedirs(cdir, exist_ok=True)
    path = os.path.join(cdir, "opencode.jsonc")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
        fh.write("\n")
    for name, src in (("agents", agents_dir), ("skills", skills_dir)):
        if src and os.path.isdir(src):
            dest = os.path.join(cdir, name)
            if not os.path.exists(dest):
                try:
                    os.symlink(os.path.abspath(src), dest)
                except OSError:
                    pass
    return cdir


# --- denial classification ---------------------------------------------------

def _tool_target(tool, state):
    inp = state.get("input") if isinstance(state.get("input"), dict) else {}
    target = (inp.get("command") or inp.get("path") or inp.get("filePath")
              or inp.get("pattern") or inp.get("agent") or "")
    return str(target).splitlines()[0].strip()[:120] if target else ""


def classify_denial(events, stderr_text):
    """Name a V2 permission auto-reject as `permission denied: <tool> <target>`.

    V2 noninteractive auto-reject shape (live probe 2026-10-27): the tool part
    is `state.status=error` with `state.error = "This non-interactive run
    cannot ask the user for permission, so the request was rejected..."`, and
    stderr carries `permission requested: <action> (<target>); auto-rejecting`.
    """
    for part in _parts(events):
        if part.get("type") != "tool":
            continue
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        if state.get("status") != "error":
            continue
        blob = json.dumps(state)
        if not DENIAL_RE.search(blob):
            continue
        name = tool_name(part.get("tool") or part.get("name") or "?")
        target = _tool_target(name, state)
        return f"permission denied: {name}" + (f" {target}" if target else "")
    ansi = re.compile(
        r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])")
    cleaned = ansi.sub("", stderr_text or "")
    if DENIAL_RE.search(cleaned):
        m = re.search(r"permission requested:\s*(\S+)\s*\(([^)]+)\)",
                      cleaned, re.IGNORECASE)
        if m:
            action = tool_name(m.group(1))
            return f"permission denied: {action} {m.group(2).strip()}"
        m = re.search(r"external_directory\s*\(([^)]+)\)", cleaned,
                      re.IGNORECASE)
        if m:
            return f"permission denied: external_directory {m.group(1).strip()}"
        line = next((l.strip() for l in cleaned.splitlines()
                     if DENIAL_RE.search(l)), "")
        return "permission denied: " + (line[:200] or "external_directory")
    return None


# --- scratch isolation -------------------------------------------------------

def is_under(path, root):
    try:
        return os.path.commonpath([os.path.realpath(path),
                                   os.path.realpath(root)]) == \
            os.path.realpath(root)
    except ValueError:
        return False


def assert_scratch_db(path, scratch_root):
    """Fail closed when a canary/cutover DB path escapes the scratch root."""
    real = os.path.realpath(path)
    if not is_under(real, scratch_root):
        raise ValueError(
            f"refusing non-scratch DB path: {path} (scratch root {scratch_root})")
    if real == os.path.realpath(DEFAULT_DB):
        raise ValueError(f"refusing the real session DB: {path}")
    return real


def scratch_env(root):
    """An env dict isolating every V2 path under `root`."""
    paths = {}
    for name, sub in (("XDG_CONFIG_HOME", "config"),
                      ("XDG_STATE_HOME", "state"),
                      ("XDG_CACHE_HOME", "cache"),
                      ("XDG_RUNTIME_DIR", "runtime"),
                      ("TMPDIR", "tmp")):
        target = os.path.join(root, sub)
        os.makedirs(target, exist_ok=True)
        paths[name] = target
    return paths


def apply_env(env, updates):
    out = dict(env or os.environ)
    out.update(updates)
    return out
