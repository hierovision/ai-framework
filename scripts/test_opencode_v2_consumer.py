#!/usr/bin/env python3
"""Hermetic tests for scripts/opencode_v2_consumer.py.

Proves a V1 config is rejected, a native V2 worktree is accepted, the primary
checkout is refused, the readiness artifact is commit-bound (SHA/PR), and the
isolated smoke path is wired (stubbed binary).

Run: python3 scripts/test_opencode_v2_consumer.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "opencode_v2_consumer.py")
sys.path.insert(0, HERE)

import scratch_cleanup  # noqa: E402

import opencode_v2_consumer as consumer  # noqa: E402

WRAPPER = """---
description: Wrapper {name}
model: opencode-go/deepseek-v4.1-flash
mode: all
permissions:
  - action: shell
    resource: "*"
    effect: ask
  - action: shell
    resource: "ls *"
    effect: allow
  - action: edit
    resource: "*"
    effect: deny
  - action: subagent
    resource: "*"
    effect: deny
  - action: execute
    resource: "*"
    effect: deny
---
Body.
"""

NATIVE_CONFIG = {
    "model": "opencode-go/deepseek-v4.1-flash",
    "instructions": [".opencode/agents.md"],
    "agents": {
        "title": {"model": {"providerID": "opencode-go",
                            "model": "deepseek-v4.1-flash"}},
        **{f"agent-{i}": {"model": "opencode-go/deepseek-v4.1-flash"}
           for i in range(10)},
    },
}

LEGACY_CONFIG = {
    "small_model": "opencode-go/deepseek-v4.1-flash",
    "agent": {"planner": {"model": "opencode-go/deepseek-v4.1-flash"}},
}


def _tmp(prefix):
    base = os.path.join(REPO, ".scratch", "test-tmp")
    os.makedirs(base, exist_ok=True)
    scratch_cleanup.prune_test_scratch(base)
    return tempfile.mkdtemp(prefix=prefix, dir=base)


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), check=True,
                   capture_output=True, text=True)


def _make_worktree(root, config=NATIVE_CONFIG):
    primary = os.path.join(root, "primary")
    os.makedirs(primary)
    _git(primary, "init", "-q")
    _git(primary, "config", "user.email", "t@example.com")
    _git(primary, "config", "user.name", "T")
    with open(os.path.join(primary, "README.md"), "w") as fh:
        fh.write("x\n")
    _git(primary, "add", ".")
    _git(primary, "commit", "-qm", "init")
    work = os.path.join(root, "work")
    _git(primary, "worktree", "add", "-q", "-b", "feat/x", work)
    os.makedirs(os.path.join(work, ".opencode", "agents"), exist_ok=True)
    for i in range(10):
        with open(os.path.join(work, ".opencode", "agents", f"agent-{i}.md"),
                  "w") as fh:
            fh.write(WRAPPER.format(name=i))
    with open(os.path.join(work, "opencode.json"), "w") as fh:
        json.dump(config, fh)
    with open(os.path.join(work, ".opencode", "package.json"), "w") as fh:
        json.dump({"dependencies": {"zod": "^3.0.0"}}, fh)
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "v2")
    return primary, work


def _env():
    env = dict(os.environ)
    env["OPENCODE_CONSUMER_SKIP_BINDINGS"] = "1"
    return env


def _run(args, env=None):
    return subprocess.run([sys.executable, SCRIPT] + args, capture_output=True,
                          text=True, env=env or _env())


def test_v1_rejected():
    root = _tmp("consumer-v1-")
    try:
        _, work = _make_worktree(root, config=LEGACY_CONFIG)
        r = _run(["check", work])
        assert r.returncode == 1, (r.returncode, r.stdout, r.stderr)
        assert "legacy `agent`" in r.stdout, r.stdout
        assert "small_model" in r.stdout, r.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_native_v2_accepted():
    root = _tmp("consumer-v2-")
    try:
        _, work = _make_worktree(root)
        r = _run(["check", work])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        assert "OK:" in r.stdout, r.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_primary_checkout_refused():
    root = _tmp("consumer-primary-")
    try:
        primary, _ = _make_worktree(root)
        r = _run(["check", primary])
        assert r.returncode == 1, (r.returncode, r.stdout)
        assert "not an isolated worktree" in r.stdout, r.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_readiness_is_commit_bound():
    root = _tmp("consumer-ready-")
    try:
        _, work = _make_worktree(root)
        artifact = os.path.join(root, "ready.json")
        r = _run(["ready", work, "--skip-smoke",
                  "--framework", REPO,
                  "--framework-pr-url", "https://example.test/fw/pull/1",
                  "--consumer-pr-url", "https://example.test/cs/pull/2",
                  "--artifact", artifact])
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        data = json.load(open(artifact))
        assert data["consumer_sha"] == consumer.head_sha(work)
        assert data["framework_sha"] == consumer.head_sha(REPO)
        ok, detail = consumer.verify_artifact(
            artifact, data["framework_sha"], data["consumer_sha"])
        assert ok, detail
        # stale SHA is refused
        ok2, detail2 = consumer.verify_artifact(
            artifact, data["framework_sha"], "0" * 40)
        assert not ok2 and "mismatch" in detail2, detail2
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ready_requires_pr_urls():
    root = _tmp("consumer-pr-")
    try:
        _, work = _make_worktree(root)
        r = _run(["ready", work, "--skip-smoke", "--framework", REPO])
        assert r.returncode == 2, (r.returncode, r.stdout)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_isolated_smoke_stub():
    root = _tmp("consumer-smoke-")
    try:
        _, work = _make_worktree(root)
        bin_dir = os.path.join(root, "bin")
        os.makedirs(bin_dir)
        stub = os.path.join(bin_dir, "opencode")
        with open(stub, "w") as fh:
            fh.write("#!/usr/bin/env python3\n"
                     "import json,sys\n"
                     "print(json.dumps({'type':'text','sessionID':'ses_x',"
                     "'part':{'type':'text','sessionID':'ses_x',"
                     "'text':'OK'}}))\n")
        os.chmod(stub, 0o755)
        old = os.environ.get("OPENCODE_BIN")
        os.environ["OPENCODE_BIN"] = stub
        try:
            ok, detail = consumer.isolated_smoke(work, work)
        finally:
            if old is None:
                os.environ.pop("OPENCODE_BIN", None)
            else:
                os.environ["OPENCODE_BIN"] = old
        assert ok, detail
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
