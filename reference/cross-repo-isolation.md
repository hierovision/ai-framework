# Cross-repo isolation (standing rule)

When you need anything from another repo on this machine — read, run, build,
install, copy — do not modify its primary checkout: no branch switch, stash,
pull, or writes. Its checked-out branch and unpushed commits belong to
whoever is working there.

1. Inspect read-only first: `git -C <repo> status -sb`, `git -C <repo> branch
   --show-current`, `git -C <repo> worktree list`, `git -C <repo> stash
   list`, and look for live sessions whose cwd is in that repo (e.g.
   `/proc/*/cwd` on Linux).
2. Create an isolated worktree at the exact ref you need:
   `git -C <repo> worktree add --detach /tmp/opencode/wt-<repo>-<purpose>
   <ref>`. For work you must keep, use a stable path:
   `~/repos/worktrees/<repo>/<purpose>`.
3. Do all reads and runs in the worktree. Remove a temporary worktree when
   done (`git -C <repo> worktree remove <path>`) and leave no uncommitted
   state behind.
4. To change that repo, make the change in the worktree and hand back a
   branch/PR. The primary checkout stays untouched without the owner's
   explicit instruction.

This rule is loaded globally through the machine's opencode `instructions`
(a path under the installed `reference/` symlink), so it applies in every
repository. `install.sh` keeps the linked content current; it never edits
global config.
