"""Verifier tests for the MRP requirements planner task."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
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
SNAPSHOT_PATH = DATA / "inventory_snapshot_pre_rollout.json"
JOURNAL_PATH = DATA / "inventory_movement_journal.json"
POSITIONS_PATH = DATA / "inventory_positions.json"
SPEC_PATH = APP / "docs" / "report_spec.json"
LOG_PATH = APP / "incident" / "planning_governance_log.md"
EXPECTED_FIXTURE = Path("/tests/fixtures/expected_report.json")
ALT_INPUT = Path("/tests/fixtures/alt_positions.json")

FIXTURE = json.loads(EXPECTED_FIXTURE.read_text())
SPEC = json.loads(SPEC_PATH.read_text())

POSITION_KEYS = set(SPEC["reconciled_inputs"]["inventory_positions"]["record_fields"])
SUMMARY_KEYS = set(SPEC["outputs"]["summary"]["required_fields"])
PLAN_KEYS = set(SPEC["outputs"]["item_plan"]["element_fields"])
ORDER_KEYS = set(SPEC["outputs"]["item_plan"]["planned_order_fields"])
EXCEPTION_KEYS = set(SPEC["outputs"]["exception_queue"]["element_fields"])
EXCEPTION_KINDS = set(SPEC["outputs"]["exception_queue"]["kinds"])

# Budget published by the contract and stated in instruction.md. Held as a literal
# so it cannot be relaxed by editing the environment, and cross-checked below.
RUNTIME_BUDGET_SEC = 90.0
HARD_TIMEOUT_SEC = 240
_ELAPSED: dict[str, float] = {}

CANDIDATE_UID = 65534
_CWORK = Path("/candidate-work")
_SETPRIV = ["setpriv", f"--reuid={CANDIDATE_UID}", f"--regid={CANDIDATE_UID}",
            "--clear-groups", "--no-new-privs"]
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
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build(script_path: Path) -> str:
    """Compile the submitted single-file planner, cached per source path.

    Compilation runs as root: it is the trusted verifier's own action. The source
    is copied to a temp dir as main.go first so the frozen snapshot and any
    sibling files in /app/workflow never join the build.
    """
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
    d = _CWORK / f"run-{next(_run_ctr)}"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o777)
    return d


def _publish_inputs() -> None:
    """Open read access on the agent-produced inputs before privileges drop.

    Never follows a link out of the agent-owned tree: os.chmod resolves symlinks,
    so a link planted at /app/... -> /tests would otherwise open the sealed
    fixtures to the unprivileged candidate.
    """
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


def _run_agent(argv, cwd: Path):
    return subprocess.run(_SETPRIV + argv, cwd=str(cwd), capture_output=True, text=True,
                          env=dict(CHILD_ENV), timeout=HARD_TIMEOUT_SEC)


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
    started = time.monotonic()
    result = _run_agent([binary, "--input", str(staged), "--output-dir", str(out_dir)], cwd=work)
    _ELAPSED[str(input_path)] = time.monotonic() - started
    assert result.returncode == 0, f"planner failed:\n{result.stdout}\n{result.stderr}"
    return (out_dir,
            _load_json(out_dir / "summary.json"),
            _load_json(out_dir / "item_plan.json"),
            _load_jsonl(out_dir / "exception_queue.jsonl"))


@pytest.fixture(scope="session")
def primary_outputs():
    return _run_pipeline()


@pytest.fixture(scope="session")
def alternate_outputs():
    return _run_pipeline(input_path=ALT_INPUT)


# --------------------------------------------------------------------------
# Step one: the truncated positions must be rebuilt before anything is planned
# --------------------------------------------------------------------------
def test_recovery_sources_are_intact():
    """The snapshot, journal and every other rule source are read, not rewritten."""
    live = {
        "snapshot": hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest(),
        "journal": hashlib.sha256(JOURNAL_PATH.read_bytes()).hexdigest(),
        "item_master": hashlib.sha256((DATA / "item_master.json").read_bytes()).hexdigest(),
        "bom": hashlib.sha256((DATA / "bill_of_materials.json").read_bytes()).hexdigest(),
        "demand": hashlib.sha256((DATA / "independent_demand.json").read_bytes()).hexdigest(),
        "calendar": hashlib.sha256((DATA / "planning_calendar.json").read_bytes()).hexdigest(),
        "log": hashlib.sha256(LOG_PATH.read_bytes()).hexdigest(),
    }
    assert _digest(live) == FIXTURE["rule_sources_digest"]


def test_positions_were_recovered():
    """The rebuilt positions match the governed replay exactly."""
    recovered = _load_json(POSITIONS_PATH)
    assert len(recovered) == FIXTURE["recovered_position_count"]
    assert _digest(recovered) == FIXTURE["recovered_positions_digest"]


def test_recovered_records_carry_only_the_declared_fields():
    """Journal bookkeeping never survives the replay."""
    for row in _load_json(POSITIONS_PATH):
        assert set(row) == POSITION_KEYS
        for receipt in row["scheduled_receipts"]:
            assert set(receipt) == {"receipt_id", "qty", "due_day"}


def test_recovered_file_is_sorted():
    """Positions ascend by item_id and receipts by receipt_id within a record."""
    rows = _load_json(POSITIONS_PATH)
    assert [r["item_id"] for r in rows] == sorted(r["item_id"] for r in rows)
    for row in rows:
        ids = [r["receipt_id"] for r in row["scheduled_receipts"]]
        assert ids == sorted(ids)


def test_shipped_and_naive_recoveries_differ_from_the_governed_one():
    """The truncated file and three plausible misreadings all differ from the answer.

    Concatenating the sources, replaying first-seen instead of by sequence, and
    treating a retraction as reversible each produce a different position set, so
    matching the sealed digest is evidence the governed rule was applied.
    """
    expected = FIXTURE["recovered_positions_digest"]
    assert FIXTURE["shipped_truncated_digest"] != expected

    snapshot = {r["item_id"]: json.loads(json.dumps(r)) for r in _load_json(SNAPSHOT_PATH)}
    journal = _load_json(JOURNAL_PATH)

    def replay(by_seq: bool, retract_permanent: bool):
        live = {k: json.loads(json.dumps(v)) for k, v in snapshot.items()}
        gone = set()
        entries = sorted(journal, key=lambda m: m["seq"]) if by_seq else journal
        for m in entries:
            iid = m["item_id"]
            if retract_permanent and iid in gone:
                continue
            if iid not in live:
                continue
            if m["kind"] == "adjust":
                live[iid]["on_hand"] = m["on_hand"]
            elif m["kind"] == "retract":
                gone.add(iid)
                live.pop(iid, None)
        return _digest(sorted(live.values(), key=lambda r: r["item_id"]))

    # each variant drops the receipt handling too, so all three differ regardless
    assert replay(True, True) != expected
    assert replay(False, True) != expected
    assert replay(True, False) != expected


# --------------------------------------------------------------------------
# Step two: the plan itself
# --------------------------------------------------------------------------
def test_primary_summary_matches_fixture(primary_outputs):
    """Every summary field matches the sealed reference run."""
    _, summary, _, _ = primary_outputs
    assert summary == FIXTURE["primary"]["summary"]


def test_primary_plan_and_exceptions_match_fixture(primary_outputs):
    """The item plan and exception queue match the sealed digests byte for byte."""
    _, _, plan, exceptions = primary_outputs
    assert _digest(plan) == FIXTURE["primary"]["item_plan_digest"]
    assert _digest(exceptions) == FIXTURE["primary"]["exception_digest"]


def test_alternate_positions_match_fixture(alternate_outputs):
    """A held-out positions file the agent never sees produces the sealed result."""
    _, summary, plan, exceptions = alternate_outputs
    assert summary == FIXTURE["alternate"]["summary"]
    assert _digest(plan) == FIXTURE["alternate"]["item_plan_digest"]
    assert _digest(exceptions) == FIXTURE["alternate"]["exception_digest"]


def test_output_dir_contains_exactly_three_files(primary_outputs):
    """A run writes the three contracted artifacts and nothing else."""
    out_dir, _, _, _ = primary_outputs
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "exception_queue.jsonl", "item_plan.json", "summary.json"]


def test_summary_schema_and_types(primary_outputs):
    """The summary carries exactly the contracted fields at the contracted types."""
    _, summary, _, _ = primary_outputs
    assert set(summary) == SUMMARY_KEYS
    for field, kind in SPEC["outputs"]["summary"]["field_types"].items():
        value = summary[field]
        if kind == "integer":
            assert isinstance(value, int) and not isinstance(value, bool), field
        else:
            assert isinstance(value, str), field


def test_plan_schema_and_sorting(primary_outputs):
    """Plan rows carry the contracted fields and ascend by item_id."""
    _, _, plan, _ = primary_outputs
    assert [r["item_id"] for r in plan] == sorted(r["item_id"] for r in plan)
    for row in plan:
        assert set(row) == PLAN_KEYS
        days = [o["receipt_day"] for o in row["planned_orders"]]
        assert days == sorted(days)
        for order in row["planned_orders"]:
            assert set(order) == ORDER_KEYS
            assert order["item_id"] == row["item_id"]
            assert order["qty"] > 0


def test_exception_schema_and_sorting(primary_outputs):
    """Exception rows carry the contracted fields and the contracted order."""
    _, _, _, exceptions = primary_outputs
    keys = [(e["release_day"], e["item_id"], e["receipt_day"]) for e in exceptions]
    assert keys == sorted(keys)
    for row in exceptions:
        assert set(row) == EXCEPTION_KEYS
        assert row["kind"] in EXCEPTION_KINDS


def test_summary_counts_track_the_artifacts(primary_outputs):
    """The summary's own totals agree with the artifacts it was emitted beside."""
    _, summary, plan, exceptions = primary_outputs
    orders = [o for row in plan for o in row["planned_orders"]]
    assert summary["item_count"] == len(plan)
    assert summary["planned_order_count"] == len(orders)
    assert summary["total_planned_qty"] == sum(o["qty"] for o in orders)
    assert summary["exception_count"] == len(exceptions)
    assert summary["max_low_level_code"] == max(r["low_level_code"] for r in plan)
    assert summary["position_count"] == len(_load_json(POSITIONS_PATH))


def test_exceptions_only_carry_material_orders(primary_outputs):
    """A past-due order is queued only when material; a pushed one always is."""
    _, summary, _, exceptions = primary_outputs
    floor = summary["effective_exception_min_qty"]
    past_due = [r for r in exceptions if r["kind"] != "inside_fence"]
    assert past_due
    for row in past_due:
        assert row["qty"] >= floor
        assert row["release_day"] < -summary["effective_grace_days"]
    fenced = [r for r in exceptions if r["kind"] == "inside_fence"]
    assert fenced, "the graded run exercises no firm fence"
    assert any(r["qty"] < floor for r in fenced), "the fence rule is only met by material orders"
    for row in fenced:
        assert row["release_day"] >= 0


def test_all_three_exception_kinds_occur(primary_outputs):
    """The graded run exercises every documented exception kind."""
    _, _, _, exceptions = primary_outputs
    assert {r["kind"] for r in exceptions} == set(SPEC["outputs"]["exception_queue"]["kinds"])


def test_phantoms_and_pushed_orders_are_load_bearing(primary_outputs):
    """The graded run carries real phantoms and real fence pushes."""
    _, summary, plan, exceptions = primary_outputs
    items = {i["item_id"]: i for i in _load_json(DATA / "item_master.json")}
    phantoms = [r for r in plan if items[r["item_id"]]["lot_policy"] == "phantom"]
    assert len(phantoms) == summary["phantom_item_count"] > 0
    for row in phantoms:
        assert row["planned_orders"] == [], row["item_id"]
    assert any(row["gross_requirement_total"] > 0 for row in phantoms)
    pushed = [o for r in plan for o in r["planned_orders"] if o["pushed"]]
    assert len(pushed) == summary["pushed_order_count"] > 0
    assert {r["item_id"] for r in exceptions if r["kind"] == "inside_fence"} == \
        {o["item_id"] for o in pushed}


def test_yield_over_releases_across_the_graded_run(primary_outputs):
    """Released and arriving quantities diverge exactly where the yield is short."""
    _, summary, plan, _ = primary_outputs
    items = {i["item_id"]: i for i in _load_json(DATA / "item_master.json")}
    orders = [o for r in plan for o in r["planned_orders"]]
    inflated = 0
    for o in orders:
        y = items[o["item_id"]]["yield_pct"]
        expected = o["receipt_qty"] if y >= 100 else -(-o["receipt_qty"] * 100 // y)
        assert o["qty"] == expected, o
        if o["qty"] != o["receipt_qty"]:
            inflated += 1
    assert inflated > 0, "no order in the graded run is inflated for yield"
    assert summary["total_receipt_qty"] == sum(o["receipt_qty"] for o in orders)
    assert summary["total_planned_qty"] > summary["total_receipt_qty"]


# --------------------------------------------------------------------------
# Each reversed rule, pinned on an instance where the drafts disagree
# --------------------------------------------------------------------------
FIXED_INPUTS = ("item_master.json", "bill_of_materials.json", "independent_demand.json",
                "planning_calendar.json", "planning_policy.json", "inventory_positions.json")


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
            "yield_pct": 100, "firm_fence_days": 0}
    base.update(kw)
    return base


def _bom(parent, component, qty_per=1, *, scrap_pct=0, effective_from=0, effective_to=9999):
    return {"parent_item": parent, "component_item": component, "qty_per": qty_per,
            "scrap_pct": scrap_pct, "effective_from": effective_from,
            "effective_to": effective_to}


BASE_POLICY = {"default": {"past_due_grace_days": 2, "exception_min_qty": 40,
                           "max_release_backlog_days": 14, "period_of_supply_cap_days": 20}}


def _probe_full(world_extra):
    """As _probe, but hands back the summary and the exception queue as well."""
    world = {"planning_policy.json": BASE_POLICY,
             "planning_calendar.json": {"horizon_days": 30, "non_working_days": []},
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


def test_low_level_code_is_the_deepest_level_not_the_first():
    """ITM-B is reached at level 1 through ITM-A and again at level 2 through ITM-C.

    The governed code is the deeper of the two; the reversed draft would stop at
    the first level the explosion reaches it on.
    """
    row = _probe({
        "item_master.json": [_item("ITM-A"), _item("ITM-B"), _item("ITM-C")],
        "bill_of_materials.json": [
            _bom("ITM-A", "ITM-B"), _bom("ITM-A", "ITM-C"), _bom("ITM-C", "ITM-B")],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 5}],
    }, "ITM-B")
    assert row["low_level_code"] == 2


def test_release_day_counts_working_days_only():
    """Lead time steps back over working days, skipping the calendar's closures.

    With days 7 and 8 closed, three working days back from day 10 lands on day 5;
    a raw calendar offset would land on day 7.
    """
    row = _probe({
        "item_master.json": [_item("ITM-A", lead_time_days=3)],
        "planning_calendar.json": {"horizon_days": 30, "non_working_days": [7, 8]},
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 10}],
    }, "ITM-A")
    assert [o["release_day"] for o in row["planned_orders"]] == [5]


def test_shortfall_is_measured_from_the_safety_stock():
    """The order covers the buffer rather than eating into it.

    Opening stock sits exactly on the safety stock of 100, so day 0 raises
    nothing. Demand of 150 on day 1 drives the balance to -50, and the shortfall
    is the distance back up to the buffer -- 150, not the 50 a draft measuring
    from zero would order.
    """
    row = _probe({
        "item_master.json": [_item("ITM-A", safety_stock=100)],
        "inventory_positions.json": [
            {"item_id": "ITM-A", "on_hand": 100, "scheduled_receipts": []}],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 150, "due_day": 1}],
    }, "ITM-A")
    assert [o["qty"] for o in row["planned_orders"]] == [150]


def test_dependent_demand_lands_on_the_release_day():
    """A parent's requirement reaches its component when the parent order is released.

    The parent's two-day lead time puts its release on day 3, so the component is
    required on day 3 and not on the parent's receipt day 5.
    """
    row = _probe({
        "item_master.json": [_item("ITM-A", lead_time_days=2), _item("ITM-B")],
        "bill_of_materials.json": [_bom("ITM-A", "ITM-B", 2)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 5}],
    }, "ITM-B")
    assert [(o["receipt_day"], o["qty"]) for o in row["planned_orders"]] == [(3, 20)]


def test_each_lot_policy_sizes_its_own_way():
    """The three policies give three different answers on the same shortfall."""
    plan = _probe({
        "item_master.json": [
            _item("ITM-A"),
            _item("ITM-B", lot_policy="fixed_quantity", lot_size=250),
            _item("ITM-C", lot_policy="period_of_supply", period_days=10),
        ],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 90, "due_day": 2},
            {"demand_id": "D2", "item_id": "ITM-B", "qty": 90, "due_day": 2},
            {"demand_id": "D3", "item_id": "ITM-C", "qty": 90, "due_day": 2},
            {"demand_id": "D4", "item_id": "ITM-C", "qty": 40, "due_day": 6},
        ],
    })
    by_id = {r["item_id"]: r for r in plan}
    assert [o["qty"] for o in by_id["ITM-A"]["planned_orders"]] == [90]
    assert [o["qty"] for o in by_id["ITM-B"]["planned_orders"]] == [250]
    # period of supply covers day 2 plus the demand inside the following nine days
    assert [o["qty"] for o in by_id["ITM-C"]["planned_orders"]] == [130]



def test_yield_over_releases_and_credits_only_the_arrival():
    """A yield of 80 releases 125 to land the 100 the requirement needs.

    The draft that treats yield as a shop-floor matter would release 100. The
    projected balance is credited with the arriving 100, so no second order
    follows.
    """
    row = _probe({
        "item_master.json": [_item("ITM-A", yield_pct=80)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 100, "due_day": 2}],
    }, "ITM-A")
    assert [(o["qty"], o["receipt_qty"]) for o in row["planned_orders"]] == [(125, 100)]


def test_yield_is_applied_after_the_lot_policy_not_before():
    """The lot sizes the arrival, then yield inflates it.

    A shortfall of 90 sizes up to one 250 lot, and a yield of 80 releases 313 to
    land it. Inflating the shortfall first would give 113, still one lot, and
    release 250.
    """
    row = _probe({
        "item_master.json": [
            _item("ITM-B", lot_policy="fixed_quantity", lot_size=250, yield_pct=80)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-B", "qty": 90, "due_day": 2}],
    }, "ITM-B")
    assert [(o["qty"], o["receipt_qty"]) for o in row["planned_orders"]] == [(313, 250)]


def test_scrap_inflates_what_the_line_must_issue():
    """Two per parent at 20 per cent scrap issues 25 for a released 10, not 20."""
    row = _probe({
        "item_master.json": [_item("ITM-A"), _item("ITM-B")],
        "bill_of_materials.json": [_bom("ITM-A", "ITM-B", 2, scrap_pct=20)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 3}],
    }, "ITM-B")
    assert [(o["receipt_day"], o["qty"]) for o in row["planned_orders"]] == [(3, 25)]


def test_the_explosion_is_driven_by_the_released_quantity():
    """ITM-B yields 50, so it releases 20 to land 10 -- and ITM-C is issued 20.

    Components are issued for everything an order starts, so the parent's
    released quantity drives the explosion rather than the quantity arriving.
    """
    row = _probe({
        "item_master.json": [_item("ITM-A"), _item("ITM-B", yield_pct=50), _item("ITM-C")],
        "bill_of_materials.json": [_bom("ITM-A", "ITM-B"), _bom("ITM-B", "ITM-C")],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 3}],
    }, "ITM-C")
    assert [(o["receipt_day"], o["qty"], o["receipt_qty"]) for o in row["planned_orders"]] == [
        (3, 20, 20)]


def test_yield_and_scrap_compound_down_the_structure():
    """Each allowance is applied once at its own level, so they multiply.

    ITM-A releases 10. The A-to-B line scraps 50 per cent, so B must land 20; B
    yields 50 per cent, so B releases 40; the B-to-C line scraps 50 per cent, so
    C must land 80.
    """
    plan = _probe({
        "item_master.json": [_item("ITM-A"), _item("ITM-B", yield_pct=50), _item("ITM-C")],
        "bill_of_materials.json": [
            _bom("ITM-A", "ITM-B", 1, scrap_pct=50), _bom("ITM-B", "ITM-C", 1, scrap_pct=50)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 3}],
    })
    by_id = {r["item_id"]: r for r in plan}
    assert [(o["qty"], o["receipt_qty"]) for o in by_id["ITM-B"]["planned_orders"]] == [(40, 20)]
    assert [(o["qty"], o["receipt_qty"]) for o in by_id["ITM-C"]["planned_orders"]] == [(80, 80)]


def test_a_phantom_raises_no_order_and_passes_through_on_the_same_day():
    """The phantom's own seven-day lead time is ignored entirely.

    ITM-A releases on day 3, so the phantom's requirement arises on day 3 and
    reaches ITM-B on day 3. A draft planning the phantom normally would offset
    its lead time to day -4, off the horizon, and ITM-B would be ordered nothing.
    """
    plan = _probe({
        "item_master.json": [
            _item("ITM-A", lead_time_days=2),
            _item("ITM-P", lot_policy="phantom", lead_time_days=7, lot_size=500),
            _item("ITM-B")],
        "bill_of_materials.json": [_bom("ITM-A", "ITM-P"), _bom("ITM-P", "ITM-B")],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 5}],
    })
    by_id = {r["item_id"]: r for r in plan}
    assert by_id["ITM-P"]["planned_orders"] == []
    assert by_id["ITM-P"]["gross_requirement_total"] == 10
    assert [(o["receipt_day"], o["qty"]) for o in by_id["ITM-B"]["planned_orders"]] == [(3, 10)]


def test_a_phantom_is_netted_against_its_own_stock_before_passing_through():
    """Stock held on the phantom is consumed first and only the remainder passes."""
    plan = _probe({
        "item_master.json": [
            _item("ITM-A"), _item("ITM-P", lot_policy="phantom"), _item("ITM-B")],
        "bill_of_materials.json": [_bom("ITM-A", "ITM-P"), _bom("ITM-P", "ITM-B")],
        "inventory_positions.json": [
            {"item_id": "ITM-P", "on_hand": 30, "scheduled_receipts": []}],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 100, "due_day": 4}],
    })
    by_id = {r["item_id"]: r for r in plan}
    assert by_id["ITM-P"]["planned_orders"] == []
    assert [(o["receipt_day"], o["qty"]) for o in by_id["ITM-B"]["planned_orders"]] == [(4, 70)]


def test_a_phantom_still_inflates_the_pass_through_for_its_own_yield():
    """A phantom yielding 50 passes 20 down for a requirement of 10."""
    row = _probe({
        "item_master.json": [
            _item("ITM-A"), _item("ITM-P", lot_policy="phantom", yield_pct=50), _item("ITM-B")],
        "bill_of_materials.json": [_bom("ITM-A", "ITM-P"), _bom("ITM-P", "ITM-B")],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 3}],
    }, "ITM-B")
    assert [(o["receipt_day"], o["qty"]) for o in row["planned_orders"]] == [(3, 20)]


def test_component_effectivity_is_judged_on_the_release_day():
    """The parent releases on day 7, so the line effective through day 8 applies.

    The interim keyed on the receipt day would reach day 10 and pick ITM-C
    instead.
    """
    plan = _probe({
        "item_master.json": [
            _item("ITM-A", lead_time_days=3), _item("ITM-B"), _item("ITM-C")],
        "bill_of_materials.json": [
            _bom("ITM-A", "ITM-B", 1, effective_from=0, effective_to=8),
            _bom("ITM-A", "ITM-C", 1, effective_from=9, effective_to=9999)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 10}],
    })
    by_id = {r["item_id"]: r for r in plan}
    assert [(o["receipt_day"], o["qty"]) for o in by_id["ITM-B"]["planned_orders"]] == [(7, 10)]
    assert by_id["ITM-C"]["planned_orders"] == []


def test_a_component_with_no_effective_line_takes_no_demand():
    """A line dormant across the whole release window contributes nothing."""
    row = _probe({
        "item_master.json": [_item("ITM-A"), _item("ITM-B")],
        "bill_of_materials.json": [
            _bom("ITM-A", "ITM-B", 1, effective_from=50, effective_to=60)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 3}],
    }, "ITM-B")
    assert row["planned_orders"] == []
    assert row["gross_requirement_total"] == 0


def test_a_release_inside_the_firm_fence_is_pushed_out_to_it():
    """A ten-day lead on a day-2 requirement releases at -8; the fence holds it to day 5.

    The receipt day does not move, so the order stands knowingly late. The draft
    that treats the fence as advisory would leave the release at -8.
    """
    summary, by_id, exceptions = _probe_full({
        "item_master.json": [_item("ITM-A", lead_time_days=10, firm_fence_days=5)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 2}],
    })
    orders = by_id["ITM-A"]["planned_orders"]
    assert [(o["receipt_day"], o["release_day"], o["pushed"]) for o in orders] == [(2, 5, True)]
    assert summary["pushed_order_count"] == 1
    assert [(r["kind"], r["release_day"]) for r in exceptions] == [("inside_fence", 5)]


def test_the_fence_day_counts_working_days_too():
    """With days 1 and 2 closed, a two-day fence sits on day 4, not day 2."""
    _, by_id, _ = _probe_full({
        "item_master.json": [_item("ITM-A", lead_time_days=10, firm_fence_days=2)],
        "planning_calendar.json": {"horizon_days": 30, "non_working_days": [1, 2]},
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 8}],
    })
    assert [o["release_day"] for o in by_id["ITM-A"]["planned_orders"]] == [4]


def test_a_pushed_order_is_not_also_reported_past_due():
    """The fence supersedes the past-due report for the same order.

    At a quantity of 100 the draft would report this release of -8 as
    past_due_release; the governed rule reports it once, as inside_fence.
    """
    _, _, exceptions = _probe_full({
        "item_master.json": [_item("ITM-A", lead_time_days=10, firm_fence_days=5)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 100, "due_day": 2}],
    })
    assert [r["kind"] for r in exceptions] == ["inside_fence"]


def test_an_item_without_a_fence_still_releases_past_due():
    """A firm_fence_days of zero means no fence, so the release stays where it falls."""
    summary, by_id, exceptions = _probe_full({
        "item_master.json": [_item("ITM-A", lead_time_days=10, firm_fence_days=0)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 100, "due_day": 2}],
    })
    assert [(o["release_day"], o["pushed"]) for o in by_id["ITM-A"]["planned_orders"]] == [
        (-8, False)]
    assert summary["pushed_order_count"] == 0
    assert [r["kind"] for r in exceptions] == ["past_due_release"]


def test_the_fence_moves_which_component_line_is_effective():
    """Pushing the release across a cutover changes the part that is issued.

    The unfenced release lands on day -8 and no line reaches it, so nothing is
    issued. The fence pushes it to day 5, where the ITM-B line is effective.
    """
    plan_no_fence = _probe({
        "item_master.json": [
            _item("ITM-A", lead_time_days=10, firm_fence_days=0), _item("ITM-B")],
        "bill_of_materials.json": [_bom("ITM-A", "ITM-B", 1, effective_from=4, effective_to=20)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 2}],
    })
    plan_fenced = _probe({
        "item_master.json": [
            _item("ITM-A", lead_time_days=10, firm_fence_days=5), _item("ITM-B")],
        "bill_of_materials.json": [_bom("ITM-A", "ITM-B", 1, effective_from=4, effective_to=20)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 2}],
    })
    assert {r["item_id"]: r for r in plan_no_fence}["ITM-B"]["planned_orders"] == []
    assert [(o["receipt_day"], o["qty"]) for o in
            {r["item_id"]: r for r in plan_fenced}["ITM-B"]["planned_orders"]] == [(5, 10)]


# --------------------------------------------------------------------------
# Contract, budget, determinism and isolation
# --------------------------------------------------------------------------
def test_policy_path_actually_influences_the_output():
    """The policy is resolved from its fixed path, not inlined as constants."""
    saved = {"planning_policy.json": (DATA / "planning_policy.json").read_text()}
    try:
        _write_json(DATA / "planning_policy.json", {
            "default": {"past_due_grace_days": 5, "exception_min_qty": 111,
                        "max_release_backlog_days": 9, "period_of_supply_cap_days": 3}})
        _, summary, _, _ = _run_pipeline()
        assert summary["effective_grace_days"] == 5
        assert summary["effective_exception_min_qty"] == 111
        assert summary["effective_max_backlog_days"] == 9
        assert summary["effective_pos_cap_days"] == 3
        assert summary != FIXTURE["primary"]["summary"]
    finally:
        _restore(saved)


def test_run_is_idempotent(primary_outputs):
    """Re-running over the same inputs reproduces the same artifacts."""
    _, summary, plan, exceptions = primary_outputs
    _, again_summary, again_plan, again_exceptions = _run_pipeline()
    assert again_summary == summary
    assert _digest(again_plan) == _digest(plan)
    assert _digest(again_exceptions) == _digest(exceptions)


def test_cli_defaults_match_an_explicit_run(primary_outputs):
    """Omitting --input uses the documented default positions file."""
    binary = _build(WORKFLOW_PATH)
    _publish_inputs()
    work = _candidate_dir()
    out_dir = work / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o777)
    result = _run_agent([binary, "--output-dir", str(out_dir)], cwd=work)
    assert result.returncode == 0, result.stderr
    _, summary, _, _ = primary_outputs
    assert _load_json(out_dir / "summary.json") == summary


def test_graded_run_meets_documented_runtime_budget(primary_outputs):
    """The graded run finishes inside the budget the contract publishes."""
    elapsed = _ELAPSED[str(POSITIONS_PATH)]
    assert elapsed <= RUNTIME_BUDGET_SEC, f"took {elapsed:.1f}s, budget {RUNTIME_BUDGET_SEC}s"


def test_runtime_budget_is_stated_in_the_contract():
    """The budget enforced above is the one the contract publishes."""
    assert int(SPEC["runtime_budget_seconds"]) == int(RUNTIME_BUDGET_SEC)


def test_planner_uses_only_the_standard_library():
    """The planner is standard-library Go; no planning or solver package is imported."""
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    imports = set(re.findall(r'"([a-z0-9_./-]+)"', source))
    for name in imports:
        if "." in name.split("/")[0]:
            pytest.fail(f"third-party import: {name}")


def test_submitted_program_runs_unprivileged_and_cannot_write_reward(tmp_path):
    """The graded program runs as nobody and cannot touch the reward path."""
    probe = tmp_path / "main.go"
    probe.write_text(
        'package main\n\nimport ("fmt"; "os")\n\n'
        'func main() {\n'
        '\tfmt.Println(os.Getuid())\n'
        '\terr := os.WriteFile("/logs/verifier/reward.txt", []byte("1"), 0o644)\n'
        '\tfmt.Println(err != nil)\n}\n', encoding="utf-8")
    binary = _build(probe)
    work = _candidate_dir()
    result = _run_agent([binary], cwd=work)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.split()
    assert lines[0] == str(CANDIDATE_UID)
    assert lines[1] == "true"


def test_frozen_snapshot_preserved():
    """The rollout's planner must still be on disk, unmodified."""
    assert ORIGINAL_WORKFLOW_PATH.exists()
    digest = hashlib.sha256(ORIGINAL_WORKFLOW_PATH.read_bytes()).hexdigest()
    assert digest == FIXTURE["broken_planner_sha256"]


def test_frozen_snapshot_is_wrong(primary_outputs):
    """The shipped planner does not already produce the governed plan."""
    _, summary, _, _ = primary_outputs
    _, broken_summary, _, _ = _run_pipeline(script_path=ORIGINAL_WORKFLOW_PATH)
    assert broken_summary != summary


def test_governance_log_present():
    """The minute book the rules are reconstructed from is in the environment."""
    assert LOG_PATH.exists() and LOG_PATH.stat().st_size > 0


def test_planner_does_not_reference_test_artifacts():
    """The planner derives its answer rather than reading anything verifier-side."""
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    for token in ("/tests", "expected_report.json", "alt_positions.json"):
        assert token not in source
