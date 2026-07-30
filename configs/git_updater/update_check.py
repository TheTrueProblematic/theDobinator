"""
Shared update-availability check for theDobinator.

This used to live inside dobd.py as `UpdateWatcher`, which meant update
detection only ran while the bot itself was running — power the bot off and both
portals lost sight of a pending update. It now lives here and is driven by
srvr_api.py's always-on companion API instead, so update state is published
whether or not the bot is on.

Two consumers read the result:
  * theDobinator's portal, via srvr_api.py's GET /update-status
  * the Drive Label site, via label_api.py's GET /update-status

State is published to logs/update_state.json rather than into srvr/status.json,
deliberately: status.json is written by dobd.py from multiple threads under an
RLock, and that lock cannot guard against a *second process* writing the same
file. Keeping this in its own file means no cross-process race.

stdlib only, and no logging config of its own — callers pass in a logger.
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request

GITHUB_REPO = "TheTrueProblematic/theDobinator"
GITHUB_BRANCH = "main"
# Fetch a window of recent commits, not just the newest one: an update can span
# several commits, and we need every message in the range being applied to decide
# whether a restart is needed.
GITHUB_COMMIT_WINDOW = 30
GITHUB_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPO}/commits"
    f"?sha={GITHUB_BRANCH}&per_page={GITHUB_COMMIT_WINDOW}"
)

GITHUB_PAT_LABEL = "GITHUB_PAT"

# ---------------------------------------------------------------------------
# "Does this update need a PC restart?"
# ---------------------------------------------------------------------------
# ⚠️ Decided PER COMMIT, from the COMMIT MESSAGE. Default is NO restart.
#
# This used to read a committed file, configs/reboot_required.flag, from the
# remote. That was broken by design: a committed file persists until another
# commit changes it, and the updater's clear_reboot_flag() only ever wrote to the
# LOCAL copy, which never reaches GitHub. So the first commit that set it to 1
# made every later commit claim "restart required" forever — which is exactly
# what happened, and what this replaces.
#
# A commit message is per-commit by construction. There is no state to reset, and
# nothing to remember to turn back off: say nothing and no restart is required.
#
# To require one, put [reboot] (or [restart]) anywhere in the commit message.
REBOOT_MARKER_RE = re.compile(r"\[(?:reboot|restart)\]", re.IGNORECASE)

EMPTY_STATE = {"available": False, "reboot": False, "remote_sha": None, "local_sha": None}


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

def get_github_pat(configs_dir: str) -> str:
    """Read the fine-grained PAT out of the gitignored configs/keys.json."""
    keys_file = os.path.join(configs_dir, "keys.json")
    try:
        with open(keys_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get(GITHUB_PAT_LABEL, "")).strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Local commit SHA
# ---------------------------------------------------------------------------

def get_local_head_sha(project_root: str) -> str | None:
    """
    Return the local checked-out commit SHA (lowercase hex), or None.

    Reads git's plumbing files directly (.git/HEAD -> loose ref -> packed-refs)
    rather than shelling out to git.exe, because this runs inside a
    logon-spawned process where git is frequently not on PATH (the same reason
    git_update.py has find_git_executable).

    Comparing this to the remote HEAD is what lets a pending update survive a
    power cycle: we notice "local is behind origin/main", not merely "a push
    happened while we were watching".
    """
    git_dir = os.path.join(project_root, ".git")
    try:
        with open(os.path.join(git_dir, "HEAD"), "r", encoding="utf-8") as f:
            head = f.read().strip()
    except Exception:
        return None

    # Detached HEAD: the file holds the SHA directly.
    if not head.startswith("ref:"):
        return head.lower() or None

    ref = head[4:].strip()  # e.g. "refs/heads/main"
    # 1) Loose ref file (.git/refs/heads/main).
    try:
        with open(os.path.join(git_dir, *ref.split("/")), "r", encoding="utf-8") as f:
            sha = f.read().strip()
        if sha:
            return sha.lower()
    except Exception:
        pass
    # 2) Packed refs (.git/packed-refs) — common right after a clone/reset.
    try:
        with open(os.path.join(git_dir, "packed-refs"), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("^"):
                    continue
                parts = line.split(" ", 1)
                if len(parts) == 2 and parts[1].strip() == ref:
                    return parts[0].strip().lower()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Published state (logs/update_state.json)
# ---------------------------------------------------------------------------

def state_path(logs_dir: str) -> str:
    return os.path.join(logs_dir, "update_state.json")


def read_update_state(logs_dir: str) -> dict:
    """Read the published update state. Missing/broken file -> nothing pending.

    Failing closed matters: if we can't tell, showing no update button beats
    showing one that might act on a wrong assumption.
    """
    try:
        with open(state_path(logs_dir), "r", encoding="utf-8") as f:
            text = f.read().strip()
        data = json.loads(text) if text else {}
        if not isinstance(data, dict):
            return dict(EMPTY_STATE)
        return {
            "available": bool(data.get("available")),
            "reboot": bool(data.get("reboot")),
            "remote_sha": data.get("remote_sha"),
            "local_sha": data.get("local_sha"),
        }
    except Exception:
        return dict(EMPTY_STATE)


def write_update_state(logs_dir: str, state: dict) -> None:
    """Publish update state atomically, so a reader never sees a half-written file."""
    os.makedirs(logs_dir, exist_ok=True)
    final = state_path(logs_dir)
    tmp = final + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, final)


# ---------------------------------------------------------------------------
# The checker
# ---------------------------------------------------------------------------

class UpdateChecker:
    """
    Polls GitHub for new commits using cheap conditional (ETag) requests so we
    can publish an "update available" flag without burning the API rate limit.

      * First request has no validator -> 200 + an ETag. We store that ETag as
        the baseline AND compare the remote HEAD SHA to our LOCAL checked-out
        SHA. If they differ, an update was already pending before we started
        (e.g. the box was rebooted without applying it), so we flag it at once.
      * Later requests send the ETag back in If-None-Match:
          - 304 Not Modified -> nothing changed, costs no rate limit.
          - 200 OK           -> a genuinely new push; refresh ETag and flag it.

    ⚠️ Availability is decided by LOCAL-vs-REMOTE SHA, not by "did we see a push
    while running". Do not regress this to ETag-only detection — that's what used
    to silently drop a still-pending update across a power cycle.
    """

    def __init__(self, project_root: str, logger, pat: str = ""):
        self.project_root = project_root
        self.configs_dir = os.path.join(project_root, "configs")
        self.logs_dir = os.path.join(project_root, "logs")
        self.log = logger
        self._pat = pat or get_github_pat(self.configs_dir)
        self.etag = None
        self._lock = threading.Lock()

    @property
    def has_pat(self) -> bool:
        return bool(self._pat)

    def _headers(self, req: urllib.request.Request) -> None:
        req.add_header("Authorization", f"Bearer {self._pat}")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "TheDobinator-UpdateWatcher")

    def check_once(self) -> dict:
        """Run one check and publish the result. Returns the published state."""
        with self._lock:
            return self._check()

    def _check(self) -> dict:
        local_sha = get_local_head_sha(self.project_root)
        previous = read_update_state(self.logs_dir)

        req = urllib.request.Request(GITHUB_API_URL)
        self._headers(req)
        req.add_header("Accept", "application/vnd.github+json")
        if self.etag:
            req.add_header("If-None-Match", self.etag)

        commits = None   # [(sha, message)], newest first; None => no fresh body
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                self.etag = resp.headers.get("ETag") or self.etag
                commits = self._parse_commits(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                # Nothing changed upstream — but still re-publish, because an
                # update we already knew about may have just been applied, and
                # that only shows up as a change on OUR side.
                self.log.debug("update check: 304 Not Modified")
            else:
                self.log.info("update check: GitHub HTTP %s %s", exc.code, exc.reason)
                return previous
        except Exception as exc:
            self.log.debug("update check: network error (non-fatal): %r", exc)
            return previous

        remote_sha = commits[0][0] if commits else previous.get("remote_sha")

        if not remote_sha or not local_sha:
            self.log.debug(
                "update check: inconclusive (remote=%s local=%s)", remote_sha, local_sha
            )
            return previous

        available = remote_sha.lower() != local_sha.lower()

        if not available:
            reboot = False
        elif commits:
            reboot = self._needs_restart(commits, local_sha)
            self.log.info(
                "update available: local=%s remote=%s reboot=%s",
                local_sha[:8], remote_sha[:8], reboot,
            )
        else:
            # 304, so we have no message list this round — keep what we decided
            # for this same remote commit last time.
            reboot = bool(previous.get("reboot")) if previous.get("remote_sha") == remote_sha else False

        state = {
            "available": available,
            "reboot": reboot,
            "remote_sha": remote_sha,
            "local_sha": local_sha,
        }
        try:
            write_update_state(self.logs_dir, state)
        except Exception as exc:
            self.log.info("could not publish update state: %r", exc)
        return state

    def _parse_commits(self, body: bytes) -> list[tuple[str, str]] | None:
        """Extract [(sha, message)] from the /commits response, newest first."""
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
            if not isinstance(data, list) or not data:
                return None
            out = []
            for item in data:
                sha = str(item.get("sha", "")).strip()
                msg = ""
                commit = item.get("commit")
                if isinstance(commit, dict):
                    msg = str(commit.get("message") or "")
                if sha:
                    out.append((sha, msg))
            return out or None
        except Exception as exc:
            self.log.debug("could not parse commits response: %r", exc)
            return None

    def _needs_restart(self, commits: list[tuple[str, str]], local_sha: str) -> bool:
        """
        True if any commit we're about to apply asks for a PC restart via
        [reboot] / [restart] in its message.

        Only the commits NEWER than what we have checked out count — walk the
        newest-first list until we reach our own SHA. If our SHA isn't in the
        window at all (more than GITHUB_COMMIT_WINDOW commits behind), consider
        every fetched message: being that far behind is exactly when a restart is
        likely warranted, so erring toward one is the safe direction.
        """
        pending = []
        for sha, msg in commits:
            if local_sha and sha.lower() == local_sha.lower():
                break
            pending.append(msg)
        if not pending:
            return False
        for msg in pending:
            if REBOOT_MARKER_RE.search(msg or ""):
                first = (msg or "").strip().splitlines()[0][:72]
                self.log.info("restart requested by commit message: %s", first)
                return True
        return False
