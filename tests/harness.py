"""Shared machinery for the MRP requirements-planning verifier."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

APP = Path("/app")
DATA = APP / "data"
WORKFLOW_PATH = APP / "workflow" / "plan_requirements.go"
ORIGINAL_WORKFLOW_PATH = APP / "workflow" / ".plan_requirements.original.go"
# The replay the instruction requires be left runnable beside the planner.
RECOVERY_PATH = APP / "workflow" / "recover_positions.go"
SNAPSHOT_PATH = DATA / "inventory_snapshot_pre_rollout.json"
JOURNAL_PATH = DATA / "inventory_movement_journal.json"
POSITIONS_PATH = DATA / "inventory_positions.json"
SPEC_PATH = APP / "docs" / "report_spec.json"
# The contract is golden metadata: the verifier reads it from its own image,
# never from the agent-writable copy under /app.
GOLDEN_CONTRACT_PATH = Path("/tests/fixtures/contract_golden.json")
LOG_PATH = APP / "incident" / "planning_governance_log.md"
EXPECTED_FIXTURE = Path("/tests/fixtures/expected_report.json")
ALT_INPUT = Path("/tests/fixtures/alt_positions.json")

FIXTURE = json.loads(EXPECTED_FIXTURE.read_text())
SPEC = json.loads(GOLDEN_CONTRACT_PATH.read_text())

POSITION_KEYS = set(SPEC["reconciled_inputs"]["inventory_positions"]["record_fields"])
SUMMARY_KEYS = set(SPEC["outputs"]["summary"]["required_fields"])
PLAN_KEYS = set(SPEC["outputs"]["item_plan"]["element_fields"])
ORDER_KEYS = set(SPEC["outputs"]["item_plan"]["planned_order_fields"])
EXCEPTION_KEYS = set(SPEC["outputs"]["exception_queue"]["element_fields"])
EXCEPTION_KINDS = set(SPEC["outputs"]["exception_queue"]["kinds"])

# Budget published by the contract and stated in instruction.md. Held as a literal
# so it cannot be relaxed by editing the environment, and cross-checked below.
RUNTIME_BUDGET_SEC = 90.0
# The contract's published budget IS the candidate timeout: an overrunning run
# is killed and the suite fails. No wall-clock measurement is graded, so the
# result does not depend on how fast the grading machine happens to be.
HARD_TIMEOUT_SEC = int(RUNTIME_BUDGET_SEC)

CANDIDATE_UID = 65534
_CWORK = Path("/candidate-work")
def _setpriv_prefix() -> list:
    """The strictest setpriv invocation this image actually supports.

    Dropping the uid is not the whole of it: a candidate that kept inheritable
    or bounding-set capabilities could regain privilege across an exec. Those
    two flags are probed rather than assumed, because a util-linux without them
    would make every run fail on the flag rather than on the task.
    """
    base = ["setpriv", f"--reuid={CANDIDATE_UID}", f"--regid={CANDIDATE_UID}",
            "--clear-groups", "--no-new-privs"]
    strict = base + ["--inh-caps=-all", "--bounding-set=-all"]
    try:
        probe = subprocess.run(strict + ["/bin/true"], capture_output=True, timeout=30)
        if probe.returncode == 0:
            return strict
    except (OSError, subprocess.SubprocessError):
        pass
    return base

_SETPRIV = _setpriv_prefix()

# Resource ceilings for anything run as the candidate. Deliberately not
# RLIMIT_AS or RLIMIT_DATA: the Go runtime reserves a large virtual arena at
# start-up and capping address space kills a correct program rather than a
# runaway one. These bound the failure modes that actually escape a process
# group -- forking without end, filling the disk, dumping core.
_CANDIDATE_NPROC = 512
_CANDIDATE_FSIZE = 512 * 1024 * 1024
_CANDIDATE_NOFILE = 1024

def _apply_rlimits() -> None:
    """Run in the child between fork and exec."""
    import resource

    cpu = int(HARD_TIMEOUT_SEC) + 60
    for what, limit in (
        (resource.RLIMIT_NPROC, _CANDIDATE_NPROC),
        (resource.RLIMIT_FSIZE, _CANDIDATE_FSIZE),
        (resource.RLIMIT_NOFILE, _CANDIDATE_NOFILE),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_CPU, cpu),
    ):
        try:
            soft, hard = resource.getrlimit(what)
            ceiling = limit if hard in (resource.RLIM_INFINITY,) else min(limit, hard)
            resource.setrlimit(what, (ceiling, ceiling))
        except (ValueError, OSError):
            continue
    os.setsid()
CHILD_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/candidate-work",
             "LANG": "C.UTF-8", "GOCACHE": "/candidate-work/gocache",
             "GO111MODULE": "off", "GOPATH": "/candidate-work/gopath"}
_BIN_CACHE: dict[str, str] = {}
_run_ctr = iter(range(1, 10_000))

def _digest(value) -> str:
    """Content digest of a decoded artifact, insensitive to free whitespace."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def _load_jsonl(path):
    """Read a contracted JSONL artifact, taking every line as written."""
    text = Path(path).read_text(encoding="utf-8")
    if not text:
        return []
    assert text.endswith("\n"), f"{Path(path).name} has no trailing newline"
    lines = text.split("\n")[:-1]
    for number, line in enumerate(lines, start=1):
        assert line.strip(), f"{Path(path).name} line {number} is blank"
    return [json.loads(line) for line in lines]

def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def _build(script_path: Path) -> str:
    """Compile the submitted single-file planner, cached per source path."""
    key = str(script_path)
    if key in _BIN_CACHE:
        return _BIN_CACHE[key]
    build_dir = tempfile.mkdtemp(prefix="gobuild_")
    os.chmod(build_dir, 0o755)
    src = Path(build_dir) / "main.go"
    shutil.copyfile(script_path, src)
    binary = Path(build_dir) / "planner"
    result = subprocess.run(
        ["go", "build", "-o", str(binary), str(src)],
        capture_output=True, text=True,
        env={**os.environ, "GOCACHE": "/tmp/gocache", "GO111MODULE": "off", "GOPATH": "/tmp/gopath"},
    )
    assert result.returncode == 0, f"go build failed:\n{result.stderr}"
    os.chmod(binary, 0o755)
    _BIN_CACHE[key] = str(binary)
    return str(binary)

def _candidate_dir() -> Path:
    """A fresh work area for one run, created where nothing can pre-empt it."""
    d = Path(tempfile.mkdtemp(prefix=f"run-{next(_run_ctr)}-", dir=str(_CWORK)))
    assert not d.is_symlink(), d
    os.chmod(d, 0o777)
    return d

def _publish_inputs() -> None:
    """Open read access on the agent-produced inputs before privileges drop."""
    app_root = APP.resolve()
    for path in sorted(APP.rglob("*")):
        if path.is_symlink():
            continue
        try:
            if not path.resolve().is_relative_to(app_root):
                continue
        except OSError:
            continue
        try:
            os.chmod(path, 0o755 if path.is_dir() else 0o644)
        except OSError:
            pass

def _reap_group(pgid: int) -> None:
    """Kill and reap everything left in the candidate's process group."""
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        return
    # give the kernel a moment to tear the group down, then reap what we can
    for _ in range(50):
        try:
            os.killpg(pgid, 0)
        except (ProcessLookupError, PermissionError, OSError):
            return
        time.sleep(0.02)

def _pids_owned_by(uid: int) -> list:
    """Every live pid whose real uid is `uid`, read from /proc."""
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            if os.stat(f"/proc/{entry}").st_uid == uid:
                pids.append(int(entry))
        except OSError:
            continue
    return pids

def reap_candidate_uid(uid: int = CANDIDATE_UID) -> None:
    """Kill everything still running as the candidate, whatever group it is in.

    Killing the process group is not enough on its own: a submitted program can
    call setsid and leave its own group, and would then survive into later tests
    -- holding the staged inputs of the next run, or still writing into an
    output directory being read. Ownership is the property that cannot be
    escaped, so the sweep is by uid.
    """
    for _ in range(50):
        pids = _pids_owned_by(uid)
        if not pids:
            return
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                continue
        for pid in pids:
            try:
                os.waitpid(pid, os.WNOHANG)
            except (ChildProcessError, OSError):
                continue
        time.sleep(0.02)

def _run_agent(argv, cwd: Path):
    """Run the submitted program unprivileged and in its own process group."""
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as out, \
            tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(
            _SETPRIV + argv, cwd=str(cwd), env=dict(CHILD_ENV),
            stdout=out, stderr=err,
            # the child's own session, plus the ceilings above, applied before
            # the exec so the candidate never runs without them
            preexec_fn=_apply_rlimits,
        )
        pgid = proc.pid      # session leader: pgid == pid, captured before the wait
        try:
            proc.wait(timeout=HARD_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            _reap_group(pgid)
            proc.wait()
            raise
        finally:
            # even on a clean exit, anything the program left running is stopped
            # before its outputs are read -- by group first, then by owner, so a
            # child that called setsid does not outlive the run
            _reap_group(pgid)
            reap_candidate_uid()
        out.seek(0)
        err.seek(0)
        return subprocess.CompletedProcess(argv, proc.returncode, out.read(), err.read())

def _run_pipeline(script_path: Path = WORKFLOW_PATH, input_path: Path = POSITIONS_PATH):
    """Build and run the submitted planner as an unprivileged subprocess."""
    binary = _build(script_path)
    _publish_inputs()
    work = _candidate_dir()
    out_dir = work / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o777)
    staged = work / "positions.json"
    shutil.copyfile(str(input_path), str(staged))
    os.chmod(staged, 0o644)
    result = _run_agent([binary, "--input", str(staged), "--output-dir", str(out_dir)], cwd=work)
    assert result.returncode == 0, f"planner failed:\n{result.stdout}\n{result.stderr}"
    return (out_dir,
            _load_json(out_dir / "summary.json"),
            _load_json(out_dir / "item_plan.json"),
            _load_jsonl(out_dir / "exception_queue.jsonl"))

# --------------------------------------------------------------------------
# Crafted-world builders and source readers the suite runs its probes through.
# They live here rather than beside the tests so test_outputs.py carries the
# assertions and nothing else.
# --------------------------------------------------------------------------
_GO_IDENT = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")

def _go_strings(source: str) -> list[str]:
    """Every string literal in a Go file, interpreted and raw alike.

    Comments are skipped so a remark that happens to name a verifier path is not
    read as a reference to one. Raw backtick literals are NOT skipped: they hold
    a path just as well as an interpreted one does, and skipping them left
    `os.ReadFile(`/tests/fixtures/expected_report.json`)` invisible to the scan
    that is supposed to catch exactly that. See _go_source_payload for the
    companion check that closes the concatenation route.
    """
    out: list[str] = []
    i, n = 0, len(source)
    while i < n:
        if source.startswith("//", i):
            k = source.find("\n", i)
            i = n if k < 0 else k + 1
            continue
        if source.startswith("/*", i):
            k = source.find("*/", i + 2)
            i = n if k < 0 else k + 2
            continue
        c = source[i]
        if c == "`":
            k = source.find("`", i + 1)
            out.append(source[i + 1:n if k < 0 else k])
            i = n if k < 0 else k + 1
            continue
        if c == '"':
            i += 1
            buf = []
            while i < n and source[i] != '"':
                if source[i] == "\\":
                    i += 2
                    continue
                buf.append(source[i])
                i += 1
            out.append("".join(buf))
            i += 1
            continue
        i += 1
    return out


def _go_source_payload(source: str) -> str:
    """The source with its comments gone and its literal seams closed up.

    Scanning whole literals catches a path written as one. It does not catch a
    path assembled out of pieces -- `"/te" + "sts/fixtures"` is two literals,
    neither of which contains the token -- and a program that reads a sealed
    fixture is not going to write the path in one piece if that is what the
    check looks for. Dropping the quotes, the concatenating plus and the
    whitespace joins the pieces back together so the token is found either way.
    The punctuation between unrelated calls survives, so `f("/te"); g("sts")`
    does not become a match.
    """
    out, i, n = [], 0, len(source)
    while i < n:
        if source.startswith("//", i):
            k = source.find("\n", i)
            i = n if k < 0 else k + 1
            continue
        if source.startswith("/*", i):
            k = source.find("*/", i + 2)
            i = n if k < 0 else k + 2
            continue
        if source[i] not in '"`+ \t\r\n':
            out.append(source[i])
        i += 1
    return "".join(out)


def _go_imports(source: str) -> list[str]:
    """Import paths declared by a Go file, read from its import declarations."""
    out: list[str] = []
    i, n = 0, len(source)

    def skip_gap(j: int) -> int:
        while j < n:
            if source[j] in " \t\r\n":
                j += 1
            elif source.startswith("//", j):
                k = source.find("\n", j)
                j = n if k < 0 else k + 1
            elif source.startswith("/*", j):
                k = source.find("*/", j + 2)
                j = n if k < 0 else k + 2
            else:
                break
        return j

    def read_string(j: int) -> tuple[str, int]:
        j += 1
        buf = []
        while j < n and source[j] != '"':
            if source[j] == "\\":
                j += 2
                continue
            buf.append(source[j])
            j += 1
        return "".join(buf), j + 1

    while i < n:
        if source.startswith("//", i):
            k = source.find("\n", i)
            i = n if k < 0 else k + 1
            continue
        if source.startswith("/*", i):
            k = source.find("*/", i + 2)
            i = n if k < 0 else k + 2
            continue
        c = source[i]
        if c == '"':
            _, i = read_string(i)
            continue
        if c == "`":
            k = source.find("`", i + 1)
            i = n if k < 0 else k + 1
            continue
        if c == "'":
            j = i + 1
            while j < n and source[j] != "'":
                j += 2 if source[j] == "\\" else 1
            i = j + 1
            continue
        if source.startswith("import", i) and (i == 0 or source[i - 1] not in _GO_IDENT) \
                and (i + 6 >= n or source[i + 6] not in _GO_IDENT):
            j = skip_gap(i + 6)
            if j < n and source[j] == "(":
                j += 1
                while True:
                    j = skip_gap(j)
                    if j >= n or source[j] == ")":
                        j += 1
                        break
                    if source[j] == '"':
                        value, j = read_string(j)
                        out.append(value)
                    else:
                        j += 1          # an alias, a dot import or an underscore
                i = j
                continue
            while j < n and source[j] not in '"\n':
                j += 1                  # an alias ahead of a single-clause path
            if j < n and source[j] == '"':
                value, j = read_string(j)
                out.append(value)
            i = j
            continue
        i += 1
    return out

# --------------------------------------------------------------------------
# The replay itself, run over snapshots and journals the submission never saw
# --------------------------------------------------------------------------
def _run_recovery(snapshot: list, journal: list) -> list:
    """Build the submitted replay and run it over a world of the verifier's making."""
    binary = _build(RECOVERY_PATH)
    work = _candidate_dir()
    snapshot_path, journal_path = work / "snapshot.json", work / "journal.json"
    out_path = work / "positions.json"
    _write_json(snapshot_path, snapshot)
    _write_json(journal_path, journal)
    os.chmod(snapshot_path, 0o644)
    os.chmod(journal_path, 0o644)
    result = _run_agent(
        [binary, "--snapshot", str(snapshot_path), "--journal", str(journal_path),
         "--out", str(out_path)],
        cwd=work)
    assert result.returncode == 0, f"the replay failed:\n{result.stdout}\n{result.stderr}"
    return _load_json(out_path)

def _pos(item_id, on_hand, receipts=()):
    return {"item_id": item_id, "on_hand": on_hand,
            "scheduled_receipts": [dict(r) for r in receipts]}

def _rct(receipt_id, qty=100, due_day=5):
    return {"receipt_id": receipt_id, "qty": qty, "due_day": due_day}

def _crafted_world() -> tuple:
    """A snapshot and journal the fixtures do not cover, built deterministically.

    Derived from the shipped sources by a fixed rule so the world is the same on
    every run, which is what lets its answer be sealed rather than recomputed
    here. The added movements cover replay order, retraction, a movement posted
    to a retracted item, an added receipt, a cancellation naming a receipt that
    is not there, and a movement naming an item the snapshot never had.
    """
    snapshot = [dict(row, on_hand=row["on_hand"] + 7) for row in _load_json(SNAPSHOT_PATH)[::3]]
    journal = [m for m in _load_json(JOURNAL_PATH) if m["seq"] % 2 == 0]
    top = max(m["seq"] for m in journal) + 1
    targets = [row["item_id"] for row in snapshot[:4]]
    journal += [
        {"seq": top + 3, "item_id": targets[0], "kind": "adjust", "on_hand": 4242},
        {"seq": top + 1, "item_id": targets[0], "kind": "adjust", "on_hand": 11},
        {"seq": top + 2, "item_id": targets[1], "kind": "retract"},
        {"seq": top + 5, "item_id": targets[1], "kind": "adjust", "on_hand": 999},
        {"seq": top + 4, "item_id": targets[2], "kind": "receipt_add",
         "receipt_id": "PO-ZZZ-1", "qty": 250, "due_day": 12},
        {"seq": top + 6, "item_id": targets[3], "kind": "receipt_cancel",
         "receipt_id": "PO-NOT-HERE"},
        {"seq": top + 7, "item_id": "ITM-99999", "kind": "adjust", "on_hand": 5},
    ]
    return snapshot, journal

def _as_contract_layout(raw: str) -> str:
    """The text with encoder-specific escaping normalised away.

    The contract fixes the LAYOUT -- two-space indent, trailing newline, one
    compact object per queue line -- not the escape style, and the two encoders
    disagree: Go's json.Marshal writes `<`, `>` and `&` as \\u003c, \\u003e and
    \\u0026 and emits non-ASCII as literal UTF-8, while Python's json.dumps does
    the opposite on both counts. Comparing raw bytes against Python's rendering
    would fail a correct Go planner the moment any of those characters reached an
    item description, a family name or an exception note. Normalising both sides
    leaves the indent, the newline and the compactness pinned exactly, which is
    what the contract states.
    """
    for escaped, literal in (("\\u003c", "<"), ("\\u003e", ">"), ("\\u0026", "&")):
        raw = raw.replace(escaped, literal)
    return raw

# --------------------------------------------------------------------------
# Each reversed rule, pinned on an instance where the drafts disagree
# --------------------------------------------------------------------------
FIXED_INPUTS = ("item_master.json", "bill_of_materials.json", "independent_demand.json",
                "planning_calendar.json", "planning_policy.json", "work_centre_capacity.json",
                "inventory_positions.json")

def _with_world(world: dict):
    """Stage a crafted world at the fixed paths, returning the saved originals."""
    saved = {name: (DATA / name).read_text(encoding="utf-8") for name in FIXED_INPUTS}
    for name, value in world.items():
        _write_json(DATA / name, value)
    return saved

def _restore(saved):
    for name, text in saved.items():
        (DATA / name).write_text(text, encoding="utf-8")

def _item(iid, **kw):
    base = {"item_id": iid, "lead_time_days": 0, "lot_policy": "lot_for_lot", "lot_size": 0,
            "period_days": 0, "safety_stock": 0, "unit_cost_cents": 100,
            "yield_pct": 100, "firm_fence_days": 0, "work_centre": "WC-1", "run_hours": 1,
            "family": "FAM-A"}
    base.update(kw)
    return base

def _bom(parent, component, qty_per=1, *, scrap_pct=0, effective_from=0, effective_to=9999):
    return {"parent_item": parent, "component_item": component, "qty_per": qty_per,
            "scrap_pct": scrap_pct, "effective_from": effective_from,
            "effective_to": effective_to}

BASE_POLICY = {"default": {"past_due_grace_days": 2, "exception_min_qty": 40,
                           "max_release_backlog_days": 14, "period_of_supply_cap_days": 20}}

# The crafted worlds below are about the other rules, so their centre has room
# for anything; the capacity probes pass a tighter file of their own.
OPEN_CAPACITY = {"work_centres": [{"work_centre": "WC-1", "daily_hours": 10_000,
                                   "max_pull_days": 5, "setup_hours": 0}]}

def _probe_full(world_extra):
    """As _probe, but hands back the summary and the exception queue as well."""
    world = {"planning_policy.json": BASE_POLICY,
             "planning_calendar.json": {"horizon_days": 30, "non_working_days": []},
             "work_centre_capacity.json": OPEN_CAPACITY,
             "bill_of_materials.json": [], "inventory_positions.json": []}
    world.update(world_extra)
    saved = _with_world(world)
    try:
        _, summary, plan, exceptions = _run_pipeline(input_path=DATA / "inventory_positions.json")
    finally:
        _restore(saved)
    return summary, {r["item_id"]: r for r in plan}, exceptions

def _probe(world_extra, item_id=None):
    """Run the submitted planner over a crafted world and return its plan rows."""
    world = {"planning_policy.json": BASE_POLICY,
             "planning_calendar.json": {"horizon_days": 30, "non_working_days": []},
             "work_centre_capacity.json": OPEN_CAPACITY,
             "bill_of_materials.json": [], "inventory_positions.json": []}
    world.update(world_extra)
    saved = _with_world(world)
    try:
        _, _, plan, _ = _run_pipeline(input_path=DATA / "inventory_positions.json")
    finally:
        _restore(saved)
    if item_id is None:
        return plan
    return next(r for r in plan if r["item_id"] == item_id)

# --------------------------------------------------------------------------
# Contract, budget, determinism and isolation
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# #MRP-4256: the work centres are loaded to capacity, exactly
# --------------------------------------------------------------------------
CAPACITY_PATH = DATA / "work_centre_capacity.json"

def _capacity(**rows):
    """A capacity file naming one row per centre."""
    return {"work_centres": [
        {"work_centre": name, "daily_hours": row[0], "max_pull_days": row[1],
         "setup_hours": row[2] if len(row) > 2 else 0}
        for name, row in sorted(rows.items())]}

def _best_run(cands: list, setup: int, start: int, room: int, paid: frozenset) -> int:
    """The largest RUN total reachable from cands[start:] inside the room left."""
    if start >= len(cands) or room <= 0:
        return 0
    key = (start, room, paid)
    memo = _best_run.memo
    if key in memo:
        return memo[key]
    best = _best_run(cands, setup, start + 1, room, paid)
    hours, family = cands[start]
    cost = hours + (0 if family in paid else setup)
    if cost <= room:
        taken = hours + _best_run(cands, setup, start + 1, room - cost, paid | {family})
        best = max(best, taken)
    memo[key] = best
    return best

_best_run.memo = {}

def _best_fitting(hours: list, room: int) -> int:
    """The largest total of these hours that does not go over the room left."""
    reach = {0}
    for value in hours:
        reach |= {total + value for total in reach if total + value <= room}
    return max(reach)

def _governed_loading(orders: list, items: dict, centres: dict, non_working: set) -> dict:
    """#MRP-4256, worked out here independently of the submission."""
    def working_between(low, high):
        return sum(1 for day in range(low + 1, high + 1) if day not in non_working)

    placed = {}
    by_centre = {}
    for order in orders:
        centre = items[order["item_id"]]["work_centre"]
        by_centre.setdefault(centre, []).append(order)

    for centre, group in sorted(by_centre.items()):
        room_per_day = centres[centre]["daily_hours"]
        max_pull = centres[centre]["max_pull_days"]
        setup = centres[centre]["setup_hours"]
        released = {}
        for order in group:
            released.setdefault(order["release_day"], []).append(order)
        low, high = min(released), max(released)
        stepped = 0
        while stepped < max_pull:
            low -= 1
            if low not in non_working:
                stepped += 1
        carried = []
        for day in range(high, low - 1, -1):
            cands = sorted(released.get(day, []) + carried,
                           key=lambda o: (o["item_id"], o["receipt_day"]))
            carried = []
            if not cands:
                continue
            room = 0 if day in non_working else room_per_day
            shape = [(items[o["item_id"]]["run_hours"], items[o["item_id"]]["family"])
                     for o in cands]
            _best_run.memo = {}
            target = _best_run(shape, setup, 0, room, frozenset())
            keep, left, need, paid = set(), room, target, frozenset()
            for index, (hours, family) in enumerate(shape):
                cost = hours + (0 if family in paid else setup)
                if cost > left:
                    continue
                if hours + _best_run(shape, setup, index + 1, left - cost,
                                     paid | {family}) == need:
                    keep.add(index)
                    left -= cost
                    need -= hours
                    paid = paid | {family}
            for index, order in enumerate(cands):
                key = (order["item_id"], order["receipt_day"])
                if index in keep:
                    placed[key] = (day, working_between(day, order["release_day"]), True)
                    continue
                previous = day - 1
                while previous >= low and previous in non_working:
                    previous -= 1
                moved = working_between(previous, order["release_day"]) if previous >= low else None
                if moved is None or moved > max_pull:
                    placed[key] = (order["release_day"], 0, False)
                else:
                    carried.append(order)
    return placed

def _graded_world():
    """The item master and capacity file the graded run was planned against."""
    items = {i["item_id"]: i for i in _load_json(DATA / "item_master.json")}
    centres = {c["work_centre"]: c
               for c in _load_json(CAPACITY_PATH)["work_centres"]}
    non_working = set(_load_json(DATA / "planning_calendar.json")["non_working_days"])
    return items, centres, non_working

def _changeover_world(room, setup, rows, *, pull=0):
    """A one-centre day holding `rows` of (item_id, family, run_hours)."""
    return {
        "item_master.json": [_item(iid, family=family, run_hours=hours)
                             for iid, family, hours in rows],
        "independent_demand.json": [
            {"demand_id": f"D-{index}", "item_id": iid, "qty": 100, "due_day": 5}
            for index, (iid, _family, _hours) in enumerate(rows)],
        "work_centre_capacity.json": _capacity(**{"WC-1": (room, pull, setup)}),
    }

def _loaded_on(exceptions, plan_rows):
    """Split the crafted day's orders into the ones that started and the ones that did not."""
    shed = {row["item_id"] for row in exceptions if row["kind"] == "capacity_exceeded"}
    return {iid for iid in plan_rows if iid not in shed}, shed

def _policy(**overrides):
    """The baseline policy with the named fields amended."""
    values = dict(BASE_POLICY["default"])
    values.update(overrides)
    return {"default": values}

# A single lot-for-lot order of 100 released on day -8: material, past due, and
# not yet beyond the backlog limit. Each policy field below moves it somewhere
# different, so a planner carrying the baselines as constants cannot follow.
_PAST_DUE_WORLD = {
    "item_master.json": [_item("ITM-A", lead_time_days=10)],
    "independent_demand.json": [
        {"demand_id": "D1", "item_id": "ITM-A", "qty": 100, "due_day": 2}],
}

__all__ = [
    "BASE_POLICY",
    "CAPACITY_PATH",
    "FIXED_INPUTS",
    "OPEN_CAPACITY",
    "_GO_IDENT",
    "_PAST_DUE_WORLD",
    "_as_contract_layout",
    "_best_fitting",
    "_best_run",
    "_bom",
    "_capacity",
    "_changeover_world",
    "_crafted_world",
    "_go_imports",
    "_go_source_payload",
    "_go_strings",
    "_governed_loading",
    "_graded_world",
    "_item",
    "_loaded_on",
    "_policy",
    "_pos",
    "_probe",
    "_probe_full",
    "_rct",
    "_restore",
    "_run_recovery",
    "_with_world",
    "GOLDEN_CONTRACT_PATH",
    "annotations",
    "hashlib",
    "json",
    "os",
    "re",
    "shutil",
    "signal",
    "subprocess",
    "sys",
    "tempfile",
    "time",
    "Path",
    "pytest",
    "APP",
    "DATA",
    "WORKFLOW_PATH",
    "ORIGINAL_WORKFLOW_PATH",
    "RECOVERY_PATH",
    "SNAPSHOT_PATH",
    "JOURNAL_PATH",
    "POSITIONS_PATH",
    "SPEC_PATH",
    "LOG_PATH",
    "EXPECTED_FIXTURE",
    "ALT_INPUT",
    "FIXTURE",
    "SPEC",
    "POSITION_KEYS",
    "SUMMARY_KEYS",
    "PLAN_KEYS",
    "ORDER_KEYS",
    "EXCEPTION_KEYS",
    "EXCEPTION_KINDS",
    "RUNTIME_BUDGET_SEC",
    "HARD_TIMEOUT_SEC",
    "CANDIDATE_UID",
    "_CWORK",
    "_SETPRIV",
    "CHILD_ENV",
    "_BIN_CACHE",
    "_run_ctr",
    "_digest",
    "_load_json",
    "_load_jsonl",
    "_write_json",
    "_build",
    "_candidate_dir",
    "_publish_inputs",
    "_run_agent",
    "_run_pipeline",
]
