"""Verifier tests for the MRP requirements-planning task.

Every test below corresponds to something instruction.md states is graded.
Shared machinery lives in harness.py.
"""

# harness.py sets __all__ explicitly, so the underscored helpers come across too.
from harness import *  # noqa: F401,F403

@pytest.fixture(scope="session")
def primary_outputs():
    return _run_pipeline()


@pytest.fixture(scope="session")
def alternate_outputs():
    return _run_pipeline(input_path=ALT_INPUT)


# --------------------------------------------------------------------------
# Step one: the truncated positions must be rebuilt before anything is planned
# --------------------------------------------------------------------------

_GO_IDENT = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")



def _go_strings(source: str) -> list[str]:
    """Interpreted string literals in a Go file, skipping comments and raw strings.

    A raw substring scan over the whole source would reject a correct planner
    that merely names one of these in a comment.
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

def _go_imports(source: str) -> list[str]:
    """Import paths declared by a Go file, read from its import declarations.

    The scan tracks string, raw-string, rune and comment state, so a filename
    literal in the body -- "summary.json" handed to filepath.Join -- is never
    mistaken for an import path. Only `import` declarations are consulted.
    """
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

def test_recovery_sources_are_intact():
    """The snapshot, journal and every other rule source are read, not rewritten."""
    live = {
        "snapshot": hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest(),
        "journal": hashlib.sha256(JOURNAL_PATH.read_bytes()).hexdigest(),
        "item_master": hashlib.sha256((DATA / "item_master.json").read_bytes()).hexdigest(),
        "bom": hashlib.sha256((DATA / "bill_of_materials.json").read_bytes()).hexdigest(),
        "demand": hashlib.sha256((DATA / "independent_demand.json").read_bytes()).hexdigest(),
        "calendar": hashlib.sha256((DATA / "planning_calendar.json").read_bytes()).hexdigest(),
        "capacity": hashlib.sha256(
            (DATA / "work_centre_capacity.json").read_bytes()).hexdigest(),
        "log": hashlib.sha256(LOG_PATH.read_bytes()).hexdigest(),
    }
    assert _digest(live) == FIXTURE["rule_sources_digest"]


def test_positions_were_recovered():
    """The rebuilt positions match the governed replay: same count and digest,
    only the declared record fields, ascending by item id."""
    recovered = _load_json(POSITIONS_PATH)
    assert len(recovered) == FIXTURE["recovered_position_count"]
    assert _digest(recovered) == FIXTURE["recovered_positions_digest"]
    for row in recovered:
        assert set(row) == POSITION_KEYS
    ids = [r["item_id"] for r in recovered]
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
# The replay itself, run over snapshots and journals the submission never saw
# --------------------------------------------------------------------------
def _governed_replay(snapshot: list, journal: list) -> list:
    """#MRP-4170 and #MRP-4174, written here independently of the submission.

    Used as the expected answer for worlds the sealed digests say nothing about,
    so the replay is graded as behaviour rather than as one delivered file.
    """
    live = {}
    for row in snapshot:
        record = json.loads(json.dumps(row))
        record["scheduled_receipts"] = sorted(
            record.get("scheduled_receipts", []), key=lambda r: r["receipt_id"])
        live[record["item_id"]] = record
    gone = set()
    for movement in sorted(journal, key=lambda m: m["seq"]):
        item_id = movement["item_id"]
        if item_id in gone or item_id not in live:
            continue
        kind = movement["kind"]
        if kind == "adjust":
            live[item_id]["on_hand"] = movement["on_hand"]
        elif kind == "receipt_add":
            live[item_id]["scheduled_receipts"] = sorted(
                live[item_id]["scheduled_receipts"] + [{
                    "receipt_id": movement["receipt_id"],
                    "qty": movement["qty"],
                    "due_day": movement["due_day"],
                }],
                key=lambda r: r["receipt_id"])
        elif kind == "receipt_cancel":
            kept, dropped = [], False
            for entry in live[item_id]["scheduled_receipts"]:
                if not dropped and entry["receipt_id"] == movement["receipt_id"]:
                    dropped = True
                    continue
                kept.append(entry)
            live[item_id]["scheduled_receipts"] = kept
        elif kind == "retract":
            gone.add(item_id)
            live.pop(item_id, None)
    return [
        {"item_id": row["item_id"], "on_hand": row["on_hand"],
         "scheduled_receipts": row["scheduled_receipts"]}
        for row in sorted(live.values(), key=lambda r: r["item_id"])
    ]


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


def test_the_replay_is_a_program_at_the_documented_path():
    """The recovery is left runnable, not just its output."""
    assert RECOVERY_PATH.is_file(), "no replay program at /app/workflow/recover_positions.go"
    source = RECOVERY_PATH.read_text(encoding="utf-8")
    assert re.search(r"^package main$", source, re.MULTILINE)


def test_the_replay_runs_over_a_snapshot_and_journal_it_has_never_seen():
    """The submitted replay is executed over a world the fixtures do not cover.

    The graded positions file is one answer, and a delivered file can be right
    about it for the wrong reasons. This derives a different world from the
    operational sources -- a third of the items, half the movements, and a tail
    that retracts, re-adjusts a retracted item, adds and cancels receipts and
    names an item the snapshot never carried -- and requires the submission's own
    program to reproduce the governed answer on it.
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
    expected = _governed_replay(snapshot, journal)
    assert _run_recovery(snapshot, journal) == expected
    # the world really is a different one, so passing here is not the graded run
    assert _digest(expected) != FIXTURE["recovered_positions_digest"]


def test_the_replay_follows_the_sequence_number_not_the_file_order():
    """#MRP-4170: ascending seq governs, and the journal ships out of order here."""
    snapshot = [_pos("ITM-A", 10)]
    journal = [
        {"seq": 3, "item_id": "ITM-A", "kind": "adjust", "on_hand": 300},
        {"seq": 1, "item_id": "ITM-A", "kind": "adjust", "on_hand": 100},
        {"seq": 2, "item_id": "ITM-A", "kind": "adjust", "on_hand": 200},
    ]
    assert _run_recovery(snapshot, journal) == [_pos("ITM-A", 300)]


def test_a_retraction_is_permanent_and_a_later_movement_cannot_undo_it():
    """The reversed draft #MRP-4022 would bring ITM-B back; the final rule does not."""
    snapshot = [_pos("ITM-A", 5), _pos("ITM-B", 50, [_rct("PO-B-1")])]
    journal = [
        {"seq": 1, "item_id": "ITM-B", "kind": "retract"},
        {"seq": 2, "item_id": "ITM-B", "kind": "adjust", "on_hand": 500},
        {"seq": 3, "item_id": "ITM-B", "kind": "receipt_add",
         "receipt_id": "PO-B-2", "qty": 9, "due_day": 1},
        {"seq": 4, "item_id": "ITM-A", "kind": "adjust", "on_hand": 6},
    ]
    assert _run_recovery(snapshot, journal) == [_pos("ITM-A", 6)]


def test_a_movement_naming_an_item_the_snapshot_never_carried_is_ignored():
    """No position is conjured for an item that was never in the snapshot."""
    snapshot = [_pos("ITM-A", 5)]
    journal = [
        {"seq": 1, "item_id": "ITM-GHOST", "kind": "adjust", "on_hand": 900},
        {"seq": 2, "item_id": "ITM-GHOST", "kind": "receipt_add",
         "receipt_id": "PO-G-1", "qty": 9, "due_day": 1},
        {"seq": 3, "item_id": "ITM-A", "kind": "adjust", "on_hand": 6},
    ]
    assert _run_recovery(snapshot, journal) == [_pos("ITM-A", 6)]


def test_a_cancel_drops_the_first_match_and_is_otherwise_a_no_op():
    """One cancel removes one receipt, and a cancel with nothing to match changes nothing."""
    snapshot = [
        _pos("ITM-A", 0, [_rct("PO-A-1", 10, 1), _rct("PO-A-1", 20, 2), _rct("PO-A-2", 30, 3)]),
        _pos("ITM-B", 0, [_rct("PO-B-1", 40, 4)]),
    ]
    journal = [
        {"seq": 1, "item_id": "ITM-A", "kind": "receipt_cancel", "receipt_id": "PO-A-1"},
        {"seq": 2, "item_id": "ITM-B", "kind": "receipt_cancel", "receipt_id": "PO-NOT-HERE"},
    ]
    assert _run_recovery(snapshot, journal) == [
        _pos("ITM-A", 0, [_rct("PO-A-1", 20, 2), _rct("PO-A-2", 30, 3)]),
        _pos("ITM-B", 0, [_rct("PO-B-1", 40, 4)]),
    ]


def test_the_replay_sorts_its_result_and_drops_the_journals_bookkeeping():
    """#MRP-4174: ascending item_id, receipts ascending by receipt_id, three fields only."""
    snapshot = [_pos("ITM-C", 3), _pos("ITM-A", 1, [_rct("PO-A-9", 1, 1)]), _pos("ITM-B", 2)]
    journal = [
        {"seq": 1, "item_id": "ITM-A", "kind": "receipt_add",
         "receipt_id": "PO-A-1", "qty": 7, "due_day": 2, "posted_by": "erp-batch"},
    ]
    recovered = _run_recovery(snapshot, journal)
    assert [row["item_id"] for row in recovered] == ["ITM-A", "ITM-B", "ITM-C"]
    for row in recovered:
        assert set(row) == POSITION_KEYS
        for entry in row["scheduled_receipts"]:
            assert set(entry) == {"receipt_id", "qty", "due_day"}
    assert [r["receipt_id"] for r in recovered[0]["scheduled_receipts"]] == ["PO-A-1", "PO-A-9"]


def test_the_replay_defaults_to_the_operational_paths():
    """With no options at all it reads the shipped sources and writes the positions.

    Every other run here points the program at a world of the verifier's making,
    which exercises the three options but never their defaults. This one grades
    the documented default run against the governed answer for the real snapshot
    and journal, and puts the positions file back afterwards.
    """
    binary = _build(RECOVERY_PATH)
    _publish_inputs()
    saved = POSITIONS_PATH.read_text(encoding="utf-8")
    data_mode = DATA.stat().st_mode & 0o7777
    # the default output path sits inside /app/data, so the candidate uid needs
    # to be able to replace it there
    os.chmod(DATA, 0o1777)
    os.chmod(POSITIONS_PATH, 0o666)
    try:
        result = _run_agent([binary], cwd=_candidate_dir())
        assert result.returncode == 0, f"the default run failed:\n{result.stdout}\n{result.stderr}"
        recovered = _load_json(POSITIONS_PATH)
        assert len(recovered) == FIXTURE["recovered_position_count"]
        assert _digest(recovered) == FIXTURE["recovered_positions_digest"]
    finally:
        os.chmod(DATA, data_mode)
        POSITIONS_PATH.write_text(saved, encoding="utf-8")


# --------------------------------------------------------------------------
# Step two: the plan itself
# --------------------------------------------------------------------------
def test_primary_run_matches_the_sealed_reference(primary_outputs):
    """Summary, item plan and exception queue all match the sealed reference run."""
    _, summary, plan, exceptions = primary_outputs
    assert summary == FIXTURE["primary"]["summary"]
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
    assert summary["pulled_order_count"] == sum(1 for o in orders if o["pulled"] > 0)
    assert summary["capacity_exceeded_count"] == sum(
        1 for r in exceptions if r["kind"] == "capacity_exceeded")
    items = {i["item_id"]: i for i in _load_json(DATA / "item_master.json")}
    unplaced = {(r["item_id"], r["receipt_day"]) for r in exceptions
                if r["kind"] == "capacity_exceeded"}
    loaded = {(items[o["item_id"]]["work_centre"], o["load_day"]) for o in orders
              if (o["item_id"], o["receipt_day"]) not in unplaced}
    assert summary["loaded_work_centre_day_count"] == len(loaded)


def test_exceptions_only_carry_material_orders(primary_outputs):
    """A past-due order is queued only when material; a pushed one always is."""
    _, summary, _, exceptions = primary_outputs
    floor = summary["effective_exception_min_qty"]
    past_due = [r for r in exceptions
                if r["kind"] not in ("inside_fence", "capacity_exceeded")]
    assert past_due
    for row in past_due:
        assert row["qty"] >= floor
        assert row["release_day"] < -summary["effective_grace_days"]
    fenced = [r for r in exceptions if r["kind"] == "inside_fence"]
    assert fenced, "the graded run exercises no firm fence"
    assert any(r["qty"] < floor for r in fenced), "the fence rule is only met by material orders"
    for row in fenced:
        assert row["release_day"] >= 0


def test_every_exception_kind_occurs(primary_outputs):
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
            "yield_pct": 100, "firm_fence_days": 0, "work_centre": "WC-1", "run_hours": 1}
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
                                   "max_pull_days": 5}]}


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
# --------------------------------------------------------------------------
# #MRP-4256: the work centres are loaded to capacity, exactly
# --------------------------------------------------------------------------
CAPACITY_PATH = DATA / "work_centre_capacity.json"


def _capacity(**rows):
    """A capacity file naming one row per centre."""
    return {"work_centres": [
        {"work_centre": name, "daily_hours": hours, "max_pull_days": pull}
        for name, (hours, pull) in sorted(rows.items())]}


def _best_fitting(hours: list, room: int) -> int:
    """The largest total of these hours that does not go over the room left."""
    reach = {0}
    for value in hours:
        reach |= {total + value for total in reach if total + value <= room}
    return max(reach)


def _governed_loading(orders: list, items: dict, centres: dict, non_working: set) -> dict:
    """#MRP-4256, worked out here independently of the submission.

    Returns {(item_id, receipt_day): (load_day, pulled, placed)}. Days are settled
    from the last working day backwards, a day sheds whatever does not fit into
    the candidates of the day before it, and the set that stays is the one that
    fills the day best, ties going to the order earlier in the plan order.
    """
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
            hours = [items[o["item_id"]]["run_hours"] for o in cands]
            target = _best_fitting(hours, room)
            keep, left, need = set(), room, target
            for index in range(len(cands)):
                if hours[index] <= left and _best_fitting(
                        hours[index + 1:], left - hours[index]) == need - hours[index]:
                    keep.add(index)
                    left -= hours[index]
                    need -= hours[index]
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


def test_the_loading_matches_the_governed_one_recomputed_here(primary_outputs):
    """Every order's load day is the one the rule gives, worked out independently.

    The sealed digests say what the answer is; this says why. The whole cascade is
    recomputed in the verifier from the item master, the capacity file and the
    calendar, and every order's load day, pull count and placement must agree.
    """
    _, summary, plan, exceptions = primary_outputs
    items, centres, non_working = _graded_world()
    orders = [o for row in plan for o in row["planned_orders"]]
    expected = _governed_loading(orders, items, centres, non_working)
    unplaced = {(r["item_id"], r["receipt_day"]) for r in exceptions
                if r["kind"] == "capacity_exceeded"}
    assert len(expected) == len(orders), "an order was lost in the loading"
    for order in orders:
        key = (order["item_id"], order["receipt_day"])
        load_day, pulled, placed = expected[key]
        assert order["load_day"] == load_day, key
        assert order["pulled"] == pulled, key
        assert (key in unplaced) == (not placed), key
    assert summary["capacity_exceeded_count"] == len(unplaced) > 0
    assert summary["pulled_order_count"] == sum(
        1 for value in expected.values() if value[1] > 0) > 0


def test_a_work_centre_never_starts_more_than_its_day(primary_outputs):
    """No centre is loaded over its hours, and a non-working day starts nothing."""
    _, _, plan, exceptions = primary_outputs
    items, centres, non_working = _graded_world()
    unplaced = {(r["item_id"], r["receipt_day"]) for r in exceptions
                if r["kind"] == "capacity_exceeded"}
    loaded = {}
    for order in (o for row in plan for o in row["planned_orders"]):
        if (order["item_id"], order["receipt_day"]) in unplaced:
            continue
        item = items[order["item_id"]]
        assert order["load_day"] not in non_working, order
        loaded[(item["work_centre"], order["load_day"])] = loaded.get(
            (item["work_centre"], order["load_day"]), 0) + item["run_hours"]
    assert loaded
    for (centre, day), hours in loaded.items():
        assert hours <= centres[centre]["daily_hours"], (centre, day, hours)
    # and the constraint is a real one on this batch, not slack everywhere
    assert any(hours > centres[centre]["daily_hours"] - 4
               for (centre, _), hours in loaded.items())


def test_an_order_is_pulled_earlier_and_never_pushed_later(primary_outputs):
    """The reversed draft #MRP-4030 sent the overflow to the NEXT working day."""
    _, _, plan, exceptions = primary_outputs
    items, centres, non_working = _graded_world()
    unplaced = {(r["item_id"], r["receipt_day"]) for r in exceptions
                if r["kind"] == "capacity_exceeded"}
    moved = 0
    for order in (o for row in plan for o in row["planned_orders"]):
        assert order["load_day"] <= order["release_day"], order
        if (order["item_id"], order["receipt_day"]) in unplaced:
            assert order["load_day"] == order["release_day"] and order["pulled"] == 0
            continue
        limit = centres[items[order["item_id"]]["work_centre"]]["max_pull_days"]
        assert 0 <= order["pulled"] <= limit, order
        assert order["pulled"] == sum(
            1 for day in range(order["load_day"] + 1, order["release_day"] + 1)
            if day not in non_working), order
        moved += 1 if order["pulled"] else 0
    assert moved > 0, "the graded run pulls nothing, so the rule is untested"


def test_the_set_that_stays_fills_the_day_better_than_a_greedy_pass(primary_outputs):
    """A greedy loading of the graded run's own days loads strictly fewer hours.

    Taking the biggest orders first is the natural implementation and is what the
    previous data system does. On this batch it leaves hours on the table, so the
    exact fit is not a distinction without a difference.
    """
    _, _, plan, _ = primary_outputs
    items, centres, non_working = _graded_world()
    orders = [o for row in plan for o in row["planned_orders"]]
    days = {}
    for order in orders:
        item = items[order["item_id"]]
        days.setdefault((item["work_centre"], order["release_day"]), []).append(
            (item["run_hours"], order["item_id"], order["receipt_day"]))
    short = differing = contested = 0
    for (centre, day), rows in days.items():
        room = centres[centre]["daily_hours"]
        hours = [row[0] for row in sorted(rows, key=lambda r: (r[1], r[2]))]
        if sum(hours) <= room:
            continue
        contested += 1
        best = _best_fitting(hours, room)
        used = 0
        for value in sorted(hours, reverse=True):
            if used + value <= room:
                used += value
        if used < best:
            short += 1
        if used != best:
            differing += 1
    assert contested > 20, "too few contested days to tell the two apart"
    assert short > 0, "the greedy pass never loses hours, so the exact fit is untested"


def test_a_phantom_occupies_no_work_centre():
    """A phantom raises no order, so it loads nothing however tight the centre is."""
    summary, by_id, exceptions = _probe_full({
        "item_master.json": [
            _item("ITM-A", lead_time_days=2, run_hours=5),
            _item("ITM-P", lot_policy="phantom", run_hours=9), _item("ITM-B", run_hours=5)],
        "bill_of_materials.json": [_bom("ITM-A", "ITM-P"), _bom("ITM-P", "ITM-B")],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 6}],
        "work_centre_capacity.json": _capacity(**{"WC-1": (10, 2)}),
    })
    assert by_id["ITM-P"]["planned_orders"] == []
    assert summary["capacity_exceeded_count"] == 0
    assert [r["kind"] for r in exceptions if r["kind"] == "capacity_exceeded"] == []


def test_the_day_keeps_the_set_that_fills_it_not_the_biggest_order():
    """Three orders, ten hours of room: 6+4 fills it and 7 alone does not.

    A pass that takes the biggest first keeps the seven-hour order and loads ten
    hours' worth of work as seven; the governed rule keeps the pair.
    """
    summary, by_id, _ = _probe_full({
        "item_master.json": [_item("ITM-A", run_hours=7), _item("ITM-B", run_hours=6),
                             _item("ITM-C", run_hours=4)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 5},
            {"demand_id": "D2", "item_id": "ITM-B", "qty": 10, "due_day": 5},
            {"demand_id": "D3", "item_id": "ITM-C", "qty": 10, "due_day": 5}],
        "work_centre_capacity.json": _capacity(**{"WC-1": (10, 2)}),
    })
    load = {iid: row["planned_orders"][0] for iid, row in by_id.items()}
    assert (load["ITM-B"]["load_day"], load["ITM-C"]["load_day"]) == (5, 5)
    assert load["ITM-A"]["load_day"] == 4 and load["ITM-A"]["pulled"] == 1
    assert summary["pulled_order_count"] == 1


def test_a_tie_on_hours_keeps_the_order_earlier_in_the_plan():
    """Two ways to fill the day exactly; the one keeping ITM-A governs."""
    _, by_id, _ = _probe_full({
        "item_master.json": [_item("ITM-A", run_hours=5), _item("ITM-B", run_hours=5),
                             _item("ITM-C", run_hours=5)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 5},
            {"demand_id": "D2", "item_id": "ITM-B", "qty": 10, "due_day": 5},
            {"demand_id": "D3", "item_id": "ITM-C", "qty": 10, "due_day": 5}],
        "work_centre_capacity.json": _capacity(**{"WC-1": (10, 2)}),
    })
    assert by_id["ITM-A"]["planned_orders"][0]["load_day"] == 5
    assert by_id["ITM-B"]["planned_orders"][0]["load_day"] == 5
    assert by_id["ITM-C"]["planned_orders"][0]["load_day"] == 4


def test_what_a_day_sheds_competes_on_the_day_before():
    """The cascade is real: a shed order joins the previous day's candidates."""
    _, by_id, _ = _probe_full({
        "item_master.json": [_item("ITM-A", run_hours=6), _item("ITM-B", run_hours=6),
                             _item("ITM-C", run_hours=6)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 5},
            {"demand_id": "D2", "item_id": "ITM-B", "qty": 10, "due_day": 5},
            {"demand_id": "D3", "item_id": "ITM-C", "qty": 10, "due_day": 4}],
        "work_centre_capacity.json": _capacity(**{"WC-1": (6, 3)}),
    })
    # day 5 keeps ITM-A, sheds ITM-B onto day 4 where ITM-C already sits; the
    # earlier key stays, so ITM-C is pushed on to day 3
    assert by_id["ITM-A"]["planned_orders"][0]["load_day"] == 5
    assert by_id["ITM-B"]["planned_orders"][0]["load_day"] == 4
    assert by_id["ITM-C"]["planned_orders"][0]["load_day"] == 3


def test_an_order_past_the_pull_limit_is_reported_capacity_exceeded():
    """One day of room, two orders, no room to pull: the loser is reported."""
    summary, by_id, exceptions = _probe_full({
        "item_master.json": [_item("ITM-A", run_hours=6), _item("ITM-B", run_hours=6)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 5},
            {"demand_id": "D2", "item_id": "ITM-B", "qty": 10, "due_day": 5}],
        "work_centre_capacity.json": _capacity(**{"WC-1": (6, 0)}),
    })
    assert by_id["ITM-A"]["planned_orders"][0]["load_day"] == 5
    stranded = by_id["ITM-B"]["planned_orders"][0]
    assert (stranded["load_day"], stranded["pulled"]) == (5, 0)
    assert [(r["item_id"], r["kind"]) for r in exceptions if r["kind"] == "capacity_exceeded"] == [
        ("ITM-B", "capacity_exceeded")]
    assert summary["capacity_exceeded_count"] == 1


def test_a_non_working_day_starts_nothing():
    """A centre cannot load on a closed day; the order pulls past it."""
    _, by_id, _ = _probe_full({
        "item_master.json": [_item("ITM-A", run_hours=6), _item("ITM-B", run_hours=6)],
        "planning_calendar.json": {"horizon_days": 30, "non_working_days": [4]},
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 5},
            {"demand_id": "D2", "item_id": "ITM-B", "qty": 10, "due_day": 5}],
        "work_centre_capacity.json": _capacity(**{"WC-1": (6, 2)}),
    })
    assert by_id["ITM-A"]["planned_orders"][0]["load_day"] == 5
    shed = by_id["ITM-B"]["planned_orders"][0]
    assert shed["load_day"] == 3, "day 4 is closed, so the order lands on day 3"
    assert shed["pulled"] == 1, "a closed day is not a working day pulled over"


def test_capacity_file_actually_influences_the_output():
    """The hours and the pull limit are resolved from the file, not inlined."""
    tight, tight_by_id, tight_exceptions = _probe_full({
        "item_master.json": [_item("ITM-A", run_hours=6), _item("ITM-B", run_hours=6)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 5},
            {"demand_id": "D2", "item_id": "ITM-B", "qty": 10, "due_day": 5}],
        "work_centre_capacity.json": _capacity(**{"WC-1": (6, 1)}),
    })
    wide, wide_by_id, wide_exceptions = _probe_full({
        "item_master.json": [_item("ITM-A", run_hours=6), _item("ITM-B", run_hours=6)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 10, "due_day": 5},
            {"demand_id": "D2", "item_id": "ITM-B", "qty": 10, "due_day": 5}],
        "work_centre_capacity.json": _capacity(**{"WC-1": (12, 1)}),
    })
    assert tight_by_id["ITM-B"]["planned_orders"][0]["load_day"] == 4
    assert tight["pulled_order_count"] == 1
    assert wide_by_id["ITM-B"]["planned_orders"][0]["load_day"] == 5
    assert wide["pulled_order_count"] == 0
    assert tight_exceptions == wide_exceptions == []


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


def test_exception_min_qty_decides_whether_an_order_is_queued_at_all():
    """#MRP-4220's floor is read from the policy, not carried as a constant.

    The same order of 100 is reported under the baseline floor of 40 and is not
    reported once the floor is raised past it, while the plan itself is unchanged:
    the field governs reporting, and it governs it from the policy file.
    """
    quiet_summary, quiet_plan, quiet = _probe_full(
        {**_PAST_DUE_WORLD, "planning_policy.json": _policy(exception_min_qty=150)})
    loud_summary, loud_plan, loud = _probe_full(
        {**_PAST_DUE_WORLD, "planning_policy.json": _policy(exception_min_qty=40)})
    assert quiet_summary["effective_exception_min_qty"] == 150
    assert loud_summary["effective_exception_min_qty"] == 40
    assert quiet == []
    assert [(r["kind"], r["qty"]) for r in loud] == [("past_due_release", 100)]
    assert quiet_plan["ITM-A"]["planned_orders"] == loud_plan["ITM-A"]["planned_orders"]


def test_past_due_grace_days_moves_the_boundary_the_report_is_measured_from():
    """A release of -3 is past due under a grace of 2 and inside it under 5."""
    world = {
        "item_master.json": [_item("ITM-A", lead_time_days=5)],
        "independent_demand.json": [
            {"demand_id": "D1", "item_id": "ITM-A", "qty": 100, "due_day": 2}],
    }
    tight_summary, tight_plan, tight = _probe_full(
        {**world, "planning_policy.json": _policy(past_due_grace_days=2)})
    slack_summary, slack_plan, slack = _probe_full(
        {**world, "planning_policy.json": _policy(past_due_grace_days=5)})
    assert [o["release_day"] for o in tight_plan["ITM-A"]["planned_orders"]] == [-3]
    assert tight_plan["ITM-A"]["planned_orders"] == slack_plan["ITM-A"]["planned_orders"]
    assert tight_summary["effective_grace_days"] == 2
    assert slack_summary["effective_grace_days"] == 5
    assert [r["kind"] for r in tight] == ["past_due_release"]
    assert slack == []


def test_max_release_backlog_days_decides_which_kind_is_reported():
    """The same release of -8 is past_due_release at 14 and backlog_exceeded at 5."""
    inside_summary, _, inside = _probe_full(
        {**_PAST_DUE_WORLD, "planning_policy.json": _policy(max_release_backlog_days=14)})
    beyond_summary, _, beyond = _probe_full(
        {**_PAST_DUE_WORLD, "planning_policy.json": _policy(max_release_backlog_days=5)})
    assert inside_summary["effective_max_backlog_days"] == 14
    assert beyond_summary["effective_max_backlog_days"] == 5
    assert [(r["kind"], r["release_day"]) for r in inside] == [("past_due_release", -8)]
    assert [(r["kind"], r["release_day"]) for r in beyond] == [("backlog_exceeded", -8)]


def test_period_of_supply_cap_days_shortens_the_span_a_lot_covers():
    """#MRP-4205's cap is read from the policy and really truncates the span.

    ITM-C asks for ten days of supply. Under a cap of 20 the lot reaches the
    day-6 demand and covers both in one order of 130; under a cap of 3 the span
    stops at day 4, so the day-6 demand falls to a second order.
    """
    world = {
        "item_master.json": [_item("ITM-C", lot_policy="period_of_supply", period_days=10)],
        "independent_demand.json": [
            {"demand_id": "D3", "item_id": "ITM-C", "qty": 90, "due_day": 2},
            {"demand_id": "D4", "item_id": "ITM-C", "qty": 40, "due_day": 6}],
    }
    wide_summary, wide_plan, _ = _probe_full(
        {**world, "planning_policy.json": _policy(period_of_supply_cap_days=20)})
    capped_summary, capped_plan, _ = _probe_full(
        {**world, "planning_policy.json": _policy(period_of_supply_cap_days=3)})
    assert wide_summary["effective_pos_cap_days"] == 20
    assert capped_summary["effective_pos_cap_days"] == 3
    assert [(o["receipt_day"], o["qty"]) for o in wide_plan["ITM-C"]["planned_orders"]] == [(2, 130)]
    assert [(o["receipt_day"], o["qty"]) for o in capped_plan["ITM-C"]["planned_orders"]] == [
        (2, 90), (6, 40)]


def test_item_master_actually_influences_the_output():
    """The item master is resolved from its fixed path, not inlined."""
    path = DATA / "item_master.json"
    saved = path.read_text(encoding="utf-8")
    try:
        items = _load_json(path)
        for it in items:
            it["lead_time_days"] = 0
        _write_json(path, items)
        _, summary, plan, _ = _run_pipeline()
        assert summary != FIXTURE["primary"]["summary"]
        # with no lead time an order releases on the day it is needed, unless the
        # item's firm fence pushes it out
        orders = [o for row in plan for o in row["planned_orders"]]
        assert orders
        for order in orders:
            assert order["release_day"] == order["receipt_day"] or order["pushed"]
    finally:
        path.write_text(saved, encoding="utf-8")


def test_bill_of_materials_actually_influences_the_output():
    """The bill of materials is resolved from its fixed path; without it nothing explodes."""
    path = DATA / "bill_of_materials.json"
    saved = path.read_text(encoding="utf-8")
    try:
        _write_json(path, [])
        _, summary, plan, _ = _run_pipeline()
        assert summary["max_low_level_code"] == 0
        assert all(row["low_level_code"] == 0 for row in plan)
        assert summary != FIXTURE["primary"]["summary"]
    finally:
        path.write_text(saved, encoding="utf-8")


def test_independent_demand_actually_influences_the_output():
    """Independent demand is resolved from its fixed path; with none, nothing is planned."""
    path = DATA / "independent_demand.json"
    saved = path.read_text(encoding="utf-8")
    try:
        _write_json(path, [])
        _, summary, plan, _ = _run_pipeline()
        # what survives with no independent demand is driven by safety stock alone
        assert summary["planned_order_count"] < (
            FIXTURE["primary"]["summary"]["planned_order_count"] // 4)
        # every surviving order traces to a buffered item or to something below one
        buffered = {i["item_id"] for i in _load_json(DATA / "item_master.json")
                    if i["safety_stock"] > 0}
        children: dict[str, list[str]] = {}
        for line in _load_json(DATA / "bill_of_materials.json"):
            children.setdefault(line["parent_item"], []).append(line["component_item"])
        reachable, stack = set(buffered), list(buffered)
        while stack:
            for child in children.get(stack.pop(), ()):
                if child not in reachable:
                    reachable.add(child)
                    stack.append(child)
        for row in plan:
            for order in row["planned_orders"]:
                assert order["item_id"] in reachable, order
    finally:
        path.write_text(saved, encoding="utf-8")


def test_planning_calendar_actually_influences_the_output():
    """The calendar is resolved from its fixed path and drives the working-day offset."""
    path = DATA / "planning_calendar.json"
    saved = path.read_text(encoding="utf-8")
    try:
        cal = _load_json(path)
        cal["non_working_days"] = []
        _write_json(path, cal)
        _, summary, _, _ = _run_pipeline()
        assert summary != FIXTURE["primary"]["summary"]
    finally:
        path.write_text(saved, encoding="utf-8")


def test_run_is_idempotent(primary_outputs):
    """Re-running over the same inputs reproduces the same artifacts."""
    _, summary, plan, exceptions = primary_outputs
    _, again_summary, again_plan, again_exceptions = _run_pipeline()
    assert again_summary == summary
    assert _digest(again_plan) == _digest(plan)
    assert _digest(again_exceptions) == _digest(exceptions)


def test_no_argument_run_writes_to_the_documented_defaults(primary_outputs):
    """With no flags at all the planner reads and writes its documented defaults.

    The previous form still passed --output-dir, so it only exercised the --input
    default; a changed default output directory went unnoticed.
    """
    binary = _build(WORKFLOW_PATH)
    _publish_inputs()
    default_out = Path("/app/output")
    shutil.rmtree(default_out, ignore_errors=True)
    default_out.mkdir(parents=True, exist_ok=True)
    os.chmod(default_out, 0o777)
    result = _run_agent([binary], cwd=_candidate_dir())
    assert result.returncode == 0, result.stderr
    assert sorted(q.name for q in default_out.iterdir()) == [
        "exception_queue.jsonl", "item_plan.json", "summary.json"]
    _, summary, plan, exceptions = primary_outputs
    assert _load_json(default_out / "summary.json") == summary
    assert _digest(_load_json(default_out / "item_plan.json")) == _digest(plan)
    assert _digest(_load_jsonl(default_out / "exception_queue.jsonl")) == _digest(exceptions)


def test_the_budget_is_enforced_by_killing_an_overrunning_run(primary_outputs):
    """The budget is enforced, and not by timing the machine.

    Every candidate run is executed with the contract's published budget as its
    hard timeout, so a run that overruns is killed and the suite fails. There is
    no measured elapsed time compared against a threshold, which would make the
    verdict depend on how fast the grading host happens to be.
    """
    assert HARD_TIMEOUT_SEC == int(RUNTIME_BUDGET_SEC)
    assert primary_outputs[1]["planned_order_count"] > 0, "the graded run did not complete"

def test_runtime_budget_is_stated_in_the_contract():
    """The budget enforced above is the one the contract publishes."""
    assert int(SPEC["runtime_budget_seconds"]) == int(RUNTIME_BUDGET_SEC)


def test_planner_imports_only_the_standard_library():
    """Every package the planner and the replay import is standard library.

    Only import declarations are consulted. A dotted filename literal in the body,
    such as "summary.json" passed to filepath.Join, is not an import and is not a
    breach of the standard-library requirement.
    """
    for source in (WORKFLOW_PATH, RECOVERY_PATH):
        paths = _go_imports(source.read_text(encoding="utf-8"))
        assert paths, f"{source.name} must declare at least one import"
        third_party = sorted({p for p in paths if "." in p.split("/")[0]})
        assert not third_party, f"third-party import(s) in {source.name}: {third_party}"


def test_the_import_check_reads_declarations_not_string_literals():
    """The check fires on a real third-party import and stays silent on a correct
    planner that happens to build its output paths with filepath.Join."""
    offending = (
        'package main\n\n'
        'import (\n'
        '\t"fmt"\n'
        '\tsolver "github.com/example/mrp-solver"\n'
        ')\n\n'
        'func main() { fmt.Println(solver.Run()) }\n'
    )
    assert _go_imports(offending) == ["fmt", "github.com/example/mrp-solver"]
    assert [p for p in _go_imports(offending) if "." in p.split("/")[0]]

    innocent = (
        'package main\n\n'
        'import (\n'
        '\t"encoding/json"\n'
        '\t"path/filepath"\n'
        ')\n\n'
        '// not an import: github.com/example/not-really\n'
        'const note = `github.com/example/also-not`\n'
        'func out(dir string) string { return filepath.Join(dir, "summary.json") }\n'
        'var q = filepath.Join("out", "exception_queue.jsonl")\n'
        'var p = filepath.Join("out", "item_plan.json")\n'
    )
    assert _go_imports(innocent) == ["encoding/json", "path/filepath"]
    assert not [p for p in _go_imports(innocent) if "." in p.split("/")[0]]

    assert _go_imports('package main\n\nimport "os"\n') == ["os"]
    assert _go_imports('package main\n\nimport alias "os"\n') == ["os"]


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
    """Both programs derive their answers rather than reading anything verifier-side."""
    for source in (WORKFLOW_PATH, RECOVERY_PATH):
        literals = _go_strings(source.read_text(encoding="utf-8"))
        for token in ("/tests", "expected_report.json", "alt_positions.json"):
            assert not any(token in literal for literal in literals), f"{source.name}: {token}"


def test_shipped_contract_matches_the_golden_copy():
    """The output contract in the environment is unmodified.

    Field lists, container shapes and sort orders are golden metadata and are read
    from the verifier's own image; this proves the agent's copy still agrees with
    it, so the contract cannot be trimmed to weaken a schema check.
    """
    shipped = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    assert shipped == json.loads(GOLDEN_CONTRACT_PATH.read_text(encoding="utf-8"))


def test_missing_policy_fields_fall_back_to_the_governed_baseline():
    """#MRP-4240: a field the policy omits keeps its baseline, not zero.

    An empty policy object must still resolve past_due_grace_days 2,
    exception_min_qty 40, max_release_backlog_days 14 and
    period_of_supply_cap_days 20. Reading a missing key as zero would admit every
    order to the exception queue and treat every release as past due.
    """
    path = DATA / "planning_policy.json"
    saved = path.read_text(encoding="utf-8")
    try:
        _write_json(path, {"default": {}})
        _, summary, _, exceptions = _run_pipeline()
        assert summary["effective_grace_days"] == 2
        assert summary["effective_exception_min_qty"] == 40
        assert summary["effective_max_backlog_days"] == 14
        assert summary["effective_pos_cap_days"] == 20
        # a zero minimum would have queued every short order
        assert all(row["qty"] >= 40 for row in exceptions
               if row["kind"] not in ("inside_fence", "capacity_exceeded"))
    finally:
        path.write_text(saved, encoding="utf-8")
