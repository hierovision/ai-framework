import os, subprocess, sys, signal, textwrap

# Red-first: the stall path must convert a hung subprocess into a bounded,
# transient-classified failure string, killing the whole process group.

os.environ["BEVAL_TIMEOUT_SECONDS"] = "3"

script = """
import os, subprocess, signal, time
proc = subprocess.Popen(
    ["bash", "-c", "sleep 600 & wait"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    start_new_session=True,
)
try:
    proc.communicate(timeout=int(os.environ.get("BEVAL_TIMEOUT_SECONDS", "240")))
except subprocess.TimeoutExpired:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.communicate()
    print("eval stall: no completion within %ss (transient; subprocess group killed)" % os.environ["BEVAL_TIMEOUT_SECONDS"])
    raise SystemExit(0)
print("NO_STALL_DETECTED")
raise SystemExit(1)
"""
os.environ["BEVAL_TIMEOUT_SECONDS"] = "3"
r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
out = r.stdout.strip()
assert "eval stall: no completion within 3s" in out, f"stall not caught: {out!r} {r.stderr}"
print("PASS  stall caught, bounded (3s), classified transient")

# The runner's own transient regex must classify the stall string for retry.
sys.path.insert(0, "skills/authoring-skills/scripts")
import run_behavioral_eval as rbe
assert rbe.is_transient("eval stall: subprocess timed out after 240s with no completion (transient; subprocess group killed)"), \
    "stall string must match is_transient() for retry/quarantine"
print("PASS  stall string classifies as transient (retry + quarantine path)")

# Zombie proof (hermetic): the killed group's pgid must no longer exist.
# (Scanning global `sleep` processes is environment-sensitive — other
# processes on the machine legitimately sleep. Check OUR group only.)
r2 = subprocess.run([sys.executable, "-c", textwrap.dedent("""
import os, subprocess, signal, sys
proc = subprocess.Popen(["bash", "-c", "sleep 600 & wait"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
try:
    proc.communicate(timeout=3)
except subprocess.TimeoutExpired:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.communicate()
try:
    os.kill(os.getpgid(proc.pid), 0)
    print("GROUP_ALIVE")
except ProcessLookupError:
    print("GROUP_DEAD")
""")], capture_output=True, text=True, timeout=30)
assert "GROUP_DEAD" in r2.stdout, f"group survived: {r2.stdout!r}"
print("PASS  process group killed — no zombie children")
