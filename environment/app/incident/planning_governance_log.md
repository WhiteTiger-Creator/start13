# Planning governance log

How the requirements planner is *meant* to behave -- the recovery of the truncated inventory positions, the low-level coding, the netting of gross requirements against on-hand and scheduled receipts, safety-stock treatment, lot sizing, yield and scrap allowances, phantom assemblies, component effectivity, the lead-time offset, the firm fence, dependent demand, the finite capacity of the work centres and exception reporting -- was settled incrementally by the planning board, and those decisions live in the review entries below, not in any single summary. Several stages deliberately depart from a textbook MRP run, and which ones they are is settled in the entries below rather than here. The February draft proposals were revisited during the 2026-05 planning review and several were reversed; where a draft or interim conflicts with a later decision, the later dated decision governs. `/app/docs/report_spec.json` is the output contract only.

- 2026-02-25: A stand-up note recorded a routine observation. A question raised on the floor was withdrawn once the entry was reread. The thread was archived after review.

> **Capacity draft proposal (2026-02-11 - #MRP-4030)** Marek: where a work centre is loaded past its day's hours, the orders that do not fit go to the NEXT working day, since the shop cannot start work it has no hours for and the requirement can wait a day *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-04 - #MRP-4022)** Rosa: where the positions file has been truncated, rebuild it by appending the movement journal to the pre-rollout snapshot and letting the later record win on collision; retracted items come back if a later movement mentions them *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-09 - #MRP-4028)** Anders: the low-level code of an item is the FIRST level at which the explosion reaches it, since that is the level the planner meets it on *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-15 - #MRP-4034)** Rosa: lead time is subtracted in raw calendar days; the shop calendar is a reporting convenience and does not enter the offset *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-21 - #MRP-4040)** Marek: safety stock is a buffer to be consumed, so a shortfall is measured against zero and the buffer is refilled by the following order *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-11 - #MRP-4030)** Anders: an item's yield is a shop-floor concern reported after the fact; the planner releases exactly the quantity the requirement calls for and does not inflate it *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-17 - #MRP-4036)** Marek: a component's scrap allowance is carried in the standard cost and must not be added to the issued quantity, or the allowance would be counted twice *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-24 - #MRP-4042)** Rosa: a phantom assembly is planned like any other item -- it is netted, sized, offset by its own lead time and raises its own planned order *(Superseded -- reversed in the 2026-05 planning review.)*

- 2026-02-14: A stand-up note spot-checked a routine observation. The variance sat inside tolerance and no adjustment was raised.

- 2026-02-03: The controls team filed a routine observation. A batch retried once after a transient timeout and completed on the second pass.

- 2026-02-03: The audit lead logged a routine observation. A query about a prior-period entry was answered from the published schedule. No action was carried forward.

- 2026-02-18: An on-call engineer carried forward a routine observation. A duplicate order was cancelled at source and never reached the run. Nothing here bears on engine behaviour.

- 2026-02-14: A reviewer on shift opened a query on a routine observation. A duplicate order was cancelled at source and never reached the run. No follow-up was requested.

- 2026-02-12: The reconciliation desk signed off a routine observation. Storage on the staging host was extended after the export outgrew its allocation. No action was carried forward.

- 2026-02-08: The controls team raised and closed a routine observation. A duplicate order was cancelled at source and never reached the run. The desk confirmed no downstream impact.

- 2026-02-09: A weekly review noted a routine observation. A query about a prior-period entry was answered from the published schedule. No follow-up was requested.

- 2026-02-22: The audit lead filed a routine observation. Nightly reconciliation matched exactly and the file was released without comment.

- 2026-02-13: The reconciliation desk signed off a routine observation. One record appeared twice in the export after a mid-cycle correction.

- 2026-02-23: The duty analyst noted a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine. No follow-up was requested.

- 2026-02-09: The platform team raised and closed a routine observation. Storage on the staging host was extended after the export outgrew its allocation. No action was carried forward.

- 2026-02-21: A shift handover reviewed a routine observation. A typo in a reference record was corrected before the run started. Referred to the dated decisions and closed.

- 2026-02-18: The platform team raised and closed a routine observation. A batch retried once after a transient timeout and completed on the second pass. Closed with no parameter change.

- 2026-02-06: The reconciliation desk recorded a routine observation. Two accounts showed a same-day transfer the export had not yet picked up. Closed with no parameter change.

- 2026-02-25: The exceptions queue owner logged a routine observation. The variance sat inside tolerance and no adjustment was raised.

- 2026-02-12: A reviewer on shift opened a query on a routine observation. The downstream vendor confirmed receipt inside the agreed window. No follow-up was requested.

- 2026-02-09: The reconciliation desk signed off a routine observation. An operator asked whether a credit had posted; it had, in the preceding period. Filed for the record.

- 2026-02-13: A reviewer on shift noted a routine observation. Storage on the staging host was extended after the export outgrew its allocation.

- 2026-02-27: A stand-up note reviewed a routine observation. Late inputs arrived from one feed and were loaded before the cut.

- 2026-02-01: The operations desk spot-checked a routine observation. The count sat a little above the running mean, entirely from estimated inputs. Closed with no parameter change.

- 2026-02-27: The controls team spot-checked a routine observation. The downstream vendor confirmed receipt inside the agreed window. The desk confirmed no downstream impact.

- 2026-02-05: A shift handover logged a routine observation. A question raised on the floor was withdrawn once the entry was reread. Filed for the record.

- 2026-03-27: The operations desk recorded a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine. Closed with no parameter change.

> **Interim decision (2026-03-06 - #MRP-4048)** Priya: a bill-of-materials line's effectivity window is tested against the day the parent order is RECEIVED, that being the day the components are consumed *(Revised -- see the 2026-05 planning review.)*

> **Interim decision (2026-03-14 - #MRP-4052)** Lena: the firm fence is advisory. A release computed inside it is left where it falls and reported past due like any other early release *(Revised -- see the 2026-05 planning review.)*

> **Interim decision (2026-03-03 - #MRP-4058)** Priya: dependent demand from a parent lands on its components on the day the parent's order is RECEIVED *(Revised -- see the 2026-05 planning review.)*

- 2026-03-14: The reconciliation desk carried forward a routine observation. A query about a prior-period entry was answered from the published schedule.

- 2026-03-06: The platform team reviewed a routine observation. A duplicate order was cancelled at source and never reached the run. Referred to the dated decisions and closed.

- 2026-03-25: The exceptions queue owner carried forward a routine observation. The variance sat inside tolerance and no adjustment was raised. The desk confirmed no downstream impact.

- 2026-03-08: The reconciliation desk filed a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine.

- 2026-03-11: The duty analyst signed off a routine observation. An operator asked whether a credit had posted; it had, in the preceding period. No action was carried forward.

- 2026-03-03: A reviewer on shift opened a query on a routine observation. A query about a prior-period entry was answered from the published schedule. Filed for the record.

- 2026-03-04: An on-call engineer filed a routine observation. A question raised on the floor was withdrawn once the entry was reread. Filed for the record.

- 2026-03-11: The platform team logged a routine observation. Nightly reconciliation matched exactly and the file was released without comment.

- 2026-03-15: The platform team logged a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine.

- 2026-03-21: A stand-up note filed a routine observation. A query about a prior-period entry was answered from the published schedule. No action was carried forward.

- 2026-03-14: A reviewer on shift logged a routine observation. A query about a prior-period entry was answered from the published schedule. Closed with no parameter change.

- 2026-03-09: The operations desk spot-checked a routine observation. A typo in a reference record was corrected before the run started. The thread was archived after review.

- 2026-03-16: The operations desk raised and closed a routine observation. An operator asked whether a credit had posted; it had, in the preceding period. Referred to the dated decisions and closed.

- 2026-03-10: A shift handover filed a routine observation. A batch retried once after a transient timeout and completed on the second pass. Filed for the record.

- 2026-03-21: An on-call engineer raised and closed a routine observation. Two accounts showed a same-day transfer the export had not yet picked up.

- 2026-03-27: The exceptions queue owner carried forward a routine observation. A duplicate order was cancelled at source and never reached the run. Closed with no parameter change.

- 2026-03-24: The audit lead recorded a routine observation. Storage on the staging host was extended after the export outgrew its allocation. Nothing here bears on engine behaviour.

- 2026-03-27: A weekly review noted a routine observation. A duplicate order was cancelled at source and never reached the run. The thread was archived after review.

- 2026-03-21: A weekly review opened a query on a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine. No follow-up was requested.

- 2026-03-10: The exceptions queue owner raised and closed a routine observation. Two accounts showed a same-day transfer the export had not yet picked up. No follow-up was requested.

- 2026-03-16: The duty analyst noted a routine observation. The overnight window ran long behind an unrelated platform patch. The thread was archived after review.

- 2026-04-17: The reconciliation desk raised and closed a routine observation. The count sat a little above the running mean, entirely from estimated inputs. No action was carried forward.

- 2026-04-20: The duty analyst noted a routine observation. The overnight window ran long behind an unrelated platform patch. Nothing here bears on engine behaviour.

- 2026-04-14: A stand-up note signed off a routine observation. An operator asked whether a credit had posted; it had, in the preceding period. Referred to the dated decisions and closed.

- 2026-04-27: The exceptions queue owner spot-checked a routine observation. Storage on the staging host was extended after the export outgrew its allocation. The thread was archived after review.

- 2026-04-04: A reviewer on shift filed a routine observation. One record appeared twice in the export after a mid-cycle correction. Nothing here bears on engine behaviour.

- 2026-04-07: A weekly review carried forward a routine observation. Nightly reconciliation matched exactly and the file was released without comment. Filed for the record.

- 2026-04-26: The platform team opened a query on a routine observation. A typo in a reference record was corrected before the run started.

- 2026-04-01: The reconciliation desk recorded a routine observation. Storage on the staging host was extended after the export outgrew its allocation. No follow-up was requested.

- 2026-04-16: A stand-up note noted a routine observation. A batch retried once after a transient timeout and completed on the second pass. No action was carried forward.

- 2026-04-07: The platform team opened a query on a routine observation. Storage on the staging host was extended after the export outgrew its allocation.

- 2026-04-18: The controls team logged a routine observation. A batch retried once after a transient timeout and completed on the second pass. The thread was archived after review.

- 2026-04-17: The operations desk recorded a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine. No action was carried forward.

- 2026-04-08: The exceptions queue owner raised and closed a routine observation. Two accounts showed a same-day transfer the export had not yet picked up. No action was carried forward.

- 2026-04-25: The exceptions queue owner raised and closed a routine observation. One record appeared twice in the export after a mid-cycle correction.

- 2026-04-22: The operations desk reviewed a routine observation. The downstream vendor confirmed receipt inside the agreed window. No follow-up was requested.

- 2026-04-22: A weekly review spot-checked a routine observation. Storage on the staging host was extended after the export outgrew its allocation. The thread was archived after review.

- 2026-04-09: The reconciliation desk recorded a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine. Referred to the dated decisions and closed.

- 2026-04-08: The operations desk carried forward a routine observation. The variance sat inside tolerance and no adjustment was raised. Filed for the record.

- 2026-04-01: A stand-up note logged a routine observation. The overnight window ran long behind an unrelated platform patch. The desk confirmed no downstream impact.

- 2026-04-18: An on-call engineer raised and closed a routine observation. The downstream vendor confirmed receipt inside the agreed window.

- 2026-04-06: A shift handover carried forward a routine observation. Two accounts showed a same-day transfer the export had not yet picked up. Filed for the record.

- 2026-04-24: The reconciliation desk filed a routine observation. The variance sat inside tolerance and no adjustment was raised. The desk confirmed no downstream impact.

- 2026-04-25: The reconciliation desk signed off a routine observation. The count sat a little above the running mean, entirely from estimated inputs.

- 2026-05-08: The duty analyst opened a query on a routine observation. Two accounts showed a same-day transfer the export had not yet picked up. The desk confirmed no downstream impact.

> **Governance decision (2026-05-04 - #MRP-4150)** Priya: Input paths, final. The item master, bill of materials, independent demand, planning calendar, planning policy and work-centre capacity are always read from their fixed absolute paths under /app/data; `--input` selects the inventory positions file only and never relocates any of the others. Both `--input` and `--output-dir` keep their documented defaults.

> **Governance decision (2026-05-06 - #MRP-4170)** Yusuf: Position recovery, final (supersedes #MRP-4022). Start from the pre-rollout snapshot and replay the movement journal in ascending `seq`, never in file order. An `adjust` overwrites the item's on-hand in place. A `receipt_add` adds the scheduled receipt it carries. A `receipt_cancel` drops the first scheduled receipt whose `receipt_id` matches, and is a no-op when the item holds no such receipt; where the item holds more than one receipt under that id, the first is the one the record carries first and only that one goes. A `retract` withdraws the item's position for good: once retracted, an item stays out and any later movement naming it is ignored. A movement naming an item the snapshot never carried is ignored.

> **Governance decision (2026-05-07 - #MRP-4174)** Yusuf: Recovered shape, final. The rebuilt file is a JSON array ascending by `item_id`. Each record carries exactly `item_id`, `on_hand` and `scheduled_receipts` -- the journal's bookkeeping fields (`seq`, `kind`, `posted_by`) never survive the replay. Within a record the scheduled receipts are ascending by `receipt_id`.

> **Governance decision (2026-05-11 - #MRP-4190)** Lena: Low-level code, final (supersedes #MRP-4028; deviates from a first-encounter reading). An item's low-level code is the DEEPEST level at which it appears anywhere in the structure, not the first level the explosion reaches it at. An item that is never a component has code 0. Because a component may be reached again through a longer path, the code has to be settled over the whole structure before any netting begins.

> **Governance decision (2026-05-12 - #MRP-4192)** Lena: Planning order, final. Items are planned in ascending low-level code, and within one code ascending by `item_id`, so every parent's planned releases are already known by the time its components are netted. Two base conventions the board never wrote down and should have: an independent demand line's `due_day` IS the day its gross requirement falls on, and the run spans day 0 through the calendar's `horizon_days` inclusive -- a demand due before day 0 or after the horizon is outside the run and raises nothing.

> **Governance decision (2026-05-14 - #MRP-4200)** Marek: Safety stock, final (supersedes #MRP-4040; deviates from the consume-and-refill draft). The projected balance is carried day by day as opening balance plus scheduled receipts plus planned receipts less gross requirement. An order is raised on the first day the balance falls BELOW the item's safety stock, and the shortfall is measured from the safety stock, not from zero -- the buffer is covered by the order rather than eaten into.

> **Governance decision (2026-05-18 - #MRP-4205)** Marek: Lot sizing, final. `lot_for_lot` orders exactly the shortfall. `fixed_quantity` orders the smallest whole number of `lot_size` multiples that covers the shortfall. `period_of_supply` covers the shortfall plus, for each of the following `period_days` minus one days, whatever that day's gross requirement exceeds its scheduled receipts by, counting nothing where receipts already cover the day; the span is capped at the policy's `period_of_supply_cap_days`.

> **Governance decision (2026-05-21 - #MRP-4210)** Priya: Lead-time offset, final (supersedes #MRP-4034; deviates from a raw-day offset). The planned release day is reached by stepping back from the receipt day over WORKING days only, skipping every day the planning calendar lists as non-working. The count does not stop at day zero: an order whose lead time reaches back past the start of the horizon takes a negative release day, and that is what is reported.

> **Governance decision (2026-05-23 - #MRP-4214)** Priya: Dependent demand, final (revises #MRP-4058). A parent's planned order places demand on each of its components on the day the parent's order is RELEASED, not the day it is received, and the quantity is the parent's order quantity times the component's `qty_per`. A release falling outside the horizon places no dependent demand.

> **Governance decision (2026-05-15 - #MRP-4204)** Marek: Lot sizing basis, final. The lot policy sizes the quantity that must ARRIVE good against the requirement, not the quantity released to the shop. Sizing happens first and is never re-applied after any allowance has been added.

> **Governance decision (2026-05-16 - #MRP-4234)** Marek: Yield, final (supersedes #MRP-4030; deviates from the release-as-required draft). An item that does not yield in full must be over-released: the released quantity is the arriving quantity multiplied by 100, divided by the item master's `yield_pct` and rounded UP to a whole unit. An item yielding 100 releases exactly what arrives. The projected balance is credited with the ARRIVING quantity, never the released one, and the yield allowance is applied once, at the item's own level.

> **Governance decision (2026-05-17 - #MRP-4238)** Marek: Scrap, final (supersedes #MRP-4036; deviates from the standard-cost draft). A bill-of-materials line's `scrap_pct` inflates what the line must issue: the component requirement is the parent's RELEASED quantity times `qty_per`, multiplied by 100, divided by 100 less `scrap_pct` and rounded UP. Components are issued for everything an order starts, so the parent's released quantity drives the explosion and not the quantity that will arrive. Yield belongs to the item and scrap to the line; each is applied once at its own level, so down a deep structure the allowances compound.

> **Governance decision (2026-05-19 - #MRP-4242)** Lena: Phantom assemblies, final (supersedes #MRP-4042; deviates from the plan-it-normally draft). An item whose `lot_policy` is `phantom` is blown through. It is netted against its own on-hand and scheduled receipts exactly like any other item, and its shortfall is taken lot for lot whatever `lot_size` or `period_days` say, but it raises NO planned order and its plan entry carries an empty order list. What it passes to its components moves on the day the requirement arose -- a phantom has no lead time to offset and its `lead_time_days` is ignored -- and its own yield still inflates what is passed through. A phantom is never queued as an exception because it has no order to be early or late.

> **Governance decision (2026-05-22 - #MRP-4246)** Priya: Component effectivity, final (revises #MRP-4048). A bill-of-materials line applies only where the parent order's RELEASE day falls within its window, from `effective_from` through `effective_to` inclusive. The release day settles it -- not the receipt day and not the day the demand was raised -- so a line phased in mid-horizon is selected by when the order starts. Where a parent has no line effective on that day for a given component, that component takes no demand from that order at all. For a phantom the pass-through day stands in for the release day.

> **Governance decision (2026-05-24 - #MRP-4250)** Priya: Firm fence, final (revises #MRP-4052). An item's firm fence sits `firm_fence_days` WORKING days after day zero, day zero itself not counted; a `firm_fence_days` of zero means the item has no fence. A planned order whose computed release day falls before the fence is PUSHED OUT to the fence day. Its receipt day does not move, so the order is knowingly late rather than the requirement being rescheduled, and the pushed release day is the one the effectivity of its component lines is judged on. A pushed order is reported as `inside_fence` whatever its quantity, and it is not also reported past due.

> **Governance decision (2026-05-27 - #MRP-4220)** Yusuf: Exception reporting, final. An order is reported only when its quantity is at least the policy's `exception_min_qty`. Such an order whose release day falls earlier than the negated `past_due_grace_days` is reported as `past_due_release`; where the release day is further back than `max_release_backlog_days` before day zero it is reported as `backlog_exceeded` instead. An order meeting neither test is not queued.

> **Governance decision (2026-05-26 - #MRP-4256)** Marek: Finite capacity, final (reverses #MRP-4030). Every planned order occupies its item's `run_hours` at the work centre the item master names, on the day it loads; a phantom raises no order and loads nothing. A work centre starts at most the `daily_hours` its row in /app/data/work_centre_capacity.json carries, on a working day; a non-working day starts nothing. An order loads on its own release day where the hours are there. Where they are not, the orders that do not fit are PULLED EARLIER -- the shop starts them sooner, it does not start them late, and the receipt day and the release day both stay where the requirement put them. Days are settled from the last working day backwards so that what a day sheds joins the candidates of the working day before it. On a day whose candidates exceed the centre's hours, the orders that STAY are the ones whose run hours total the most without going over; where two such sets total the same, the set that keeps the order earlier in the plan order -- ascending `item_id`, then `receipt_day` -- stays, and that reading is applied in turn down the candidates. An order may not be pulled more than its centre's `max_pull_days` WORKING days before its own release day: one that would be is not loaded at all, carries a `load_day` equal to its release day with `pulled` zero, and is reported `capacity_exceeded` whatever its quantity. Every other order carries the working day it loads on and the count of working days it was pulled.

> **Governance decision (2026-06-04 - #MRP-4260)** Marek: Changeover blocks, final (amends #MRP-4256 on what a day's hours are spent on; everything else in that decision stands). Each item names the `family` it belongs to in the item master, and each work centre carries a `setup_hours` block in /app/data/work_centre_capacity.json. A centre that starts orders from a family on a day pays that block ONCE for the day, however many orders of that family it starts: three orders of one family cost one block, one order each from three families costs three. What a day starts is therefore its orders' run hours PLUS one block per DISTINCT family among them, and it is that total the centre's `daily_hours` bounds. A changeover block is capacity spent, never work done: the set that STAYS is still the one whose RUN hours total the most, now among the sets whose run hours and blocks together stay inside the day, and the #MRP-4256 tie-break is unchanged -- where two such sets tie on run hours the set that keeps the order earlier in the plan order stays, read in turn down the candidates. A day that starts nothing pays no block, and a non-working day pays none because it starts nothing. A phantom raises no order, so it neither runs nor sets up. Where a centre's `setup_hours` is zero the day loads exactly as #MRP-4256 left it

> **Governance decision (2026-05-28 - #MRP-4230)** Lena: Emission order, final. The item plan is ascending by `item_id`, and each item's planned orders stay in the order they were raised, earliest receipt day first. The exception queue is ascending by `release_day`, then by `item_id`, then by `receipt_day`, then by `kind`, then by `qty`. That key names every field a queue row carries, so two rows can only tie on it by being the same row: an order reported both `inside_fence` and `capacity_exceeded` on the same day separates on `kind`, and nothing is left to the order the rows happened to be raised in.

- 2026-05-21: The platform team signed off a routine observation. The count sat a little above the running mean, entirely from estimated inputs. Filed for the record.

- 2026-05-10: The audit lead carried forward a routine observation. The variance sat inside tolerance and no adjustment was raised. Filed for the record.

- 2026-05-01: The platform team signed off a routine observation. A query about a prior-period entry was answered from the published schedule. Closed with no parameter change.

- 2026-05-08: The audit lead logged a routine observation. A typo in a reference record was corrected before the run started. Filed for the record.

- 2026-05-07: The platform team filed a routine observation. One record appeared twice in the export after a mid-cycle correction.

- 2026-05-11: The reconciliation desk reviewed a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine. No follow-up was requested.

- 2026-05-05: A weekly review reviewed a routine observation. A question raised on the floor was withdrawn once the entry was reread.

- 2026-05-26: A shift handover spot-checked a routine observation. The variance sat inside tolerance and no adjustment was raised. No follow-up was requested.

- 2026-05-16: A weekly review filed a routine observation. One record appeared twice in the export after a mid-cycle correction.

- 2026-05-26: The controls team filed a routine observation. The overnight window ran long behind an unrelated platform patch. Filed for the record.

- 2026-05-24: The audit lead reviewed a routine observation. Nightly reconciliation matched exactly and the file was released without comment.

- 2026-05-24: The operations desk spot-checked a routine observation. Two accounts showed a same-day transfer the export had not yet picked up.

- 2026-05-23: The controls team carried forward a routine observation. The downstream vendor confirmed receipt inside the agreed window. No action was carried forward.

- 2026-05-22: The exceptions queue owner opened a query on a routine observation. Storage on the staging host was extended after the export outgrew its allocation.

- 2026-05-22: The platform team logged a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine. Filed for the record.

- 2026-05-25: The duty analyst opened a query on a routine observation. The count sat a little above the running mean, entirely from estimated inputs. Closed with no parameter change.

- 2026-05-08: A shift handover opened a query on a routine observation. The variance sat inside tolerance and no adjustment was raised. No action was carried forward.

- 2026-05-15: The reconciliation desk noted a routine observation. The overnight window ran long behind an unrelated platform patch. Nothing here bears on engine behaviour.

- 2026-05-11: A shift handover noted a routine observation. The count sat a little above the running mean, entirely from estimated inputs. No follow-up was requested.

- 2026-06-19: A stand-up note filed a routine observation. The variance sat inside tolerance and no adjustment was raised. No action was carried forward.

> **Governance decision (2026-06-05 - #MRP-4244)** Lena: Run summary, final. The counts the summary carries are aggregates of what the run itself emitted and nothing else. `item_count` is the number of item plans, `position_count` the number of records in the positions file the run read, and `max_low_level_code` the deepest code assigned. `planned_order_count` is every planned order across the plan, `total_planned_qty` the sum of the released quantities and `total_receipt_qty` the sum of the arriving ones, so the two differ exactly where a yield is short. `total_net_requirement` is the sum of the item plans' `net_requirement_total`, and an item's `ending_on_hand` is the projected balance left once the horizon is planned out. `phantom_item_count` counts the items the master gives a phantom lot policy, whether or not anything required them, and `pushed_order_count` the orders the fence moved. `exception_count` is the length of the queue and `past_due_count` the rows of it reported `past_due_release` or `backlog_exceeded` -- a pushed order is not past due and is not counted here. `pulled_order_count` is the orders whose `pulled` is not zero, `capacity_exceeded_count` the orders capacity could not place, and `loaded_work_centre_day_count` the number of work-centre working days that ended up carrying at least one order.

> **Governance decision (2026-06-02 - #MRP-4240)** Priya: Planning policy baseline, read from /app/data/planning_policy.json at that fixed absolute path. Any field the policy file omits keeps its baseline: past_due_grace_days = 2; exception_min_qty = 40; max_release_backlog_days = 14; period_of_supply_cap_days = 20.

- 2026-06-10: The controls team recorded a routine observation. A question raised on the floor was withdrawn once the entry was reread. No action was carried forward.

- 2026-06-17: The reconciliation desk filed a routine observation. A batch retried once after a transient timeout and completed on the second pass.

- 2026-06-23: A stand-up note signed off a routine observation. An operator asked whether a credit had posted; it had, in the preceding period. No follow-up was requested.

- 2026-06-05: The controls team opened a query on a routine observation. The variance sat inside tolerance and no adjustment was raised. The desk confirmed no downstream impact.

- 2026-06-05: A shift handover spot-checked a routine observation. The overnight window ran long behind an unrelated platform patch.

- 2026-06-12: The exceptions queue owner logged a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine. Filed for the record.

- 2026-06-03: A shift handover signed off a routine observation. The variance sat inside tolerance and no adjustment was raised. Filed for the record.

- 2026-06-14: A weekly review signed off a routine observation. Two accounts showed a same-day transfer the export had not yet picked up. No action was carried forward.

- 2026-06-17: A stand-up note spot-checked a routine observation. A typo in a reference record was corrected before the run started. Filed for the record.

- 2026-06-07: An on-call engineer filed a routine observation. Storage on the staging host was extended after the export outgrew its allocation. Referred to the dated decisions and closed.

- 2026-06-04: A weekly review carried forward a routine observation. A duplicate order was cancelled at source and never reached the run.

- 2026-06-01: The exceptions queue owner noted a routine observation. Two accounts showed a same-day transfer the export had not yet picked up. The desk confirmed no downstream impact.

- 2026-06-13: The audit lead reviewed a routine observation. Dashboard tiles lagged the refresh; traced to cache staleness rather than the engine. The desk confirmed no downstream impact.

- 2026-06-03: An on-call engineer filed a routine observation. A typo in a reference record was corrected before the run started.

- 2026-06-20: The exceptions queue owner spot-checked a routine observation. The downstream vendor confirmed receipt inside the agreed window. Referred to the dated decisions and closed.

- 2026-06-16: The duty analyst signed off a routine observation. A batch retried once after a transient timeout and completed on the second pass. Filed for the record.

- 2026-06-12: The exceptions queue owner spot-checked a routine observation. The count sat a little above the running mean, entirely from estimated inputs. Filed for the record.

- 2026-06-27: The operations desk signed off a routine observation. One record appeared twice in the export after a mid-cycle correction. Nothing here bears on engine behaviour.

- 2026-06-19: The platform team raised and closed a routine observation. A query about a prior-period entry was answered from the published schedule. Closed with no parameter change.

- 2026-06-02: The exceptions queue owner carried forward a routine observation. A query about a prior-period entry was answered from the published schedule. Nothing here bears on engine behaviour.

- 2026-06-26: A reviewer on shift reviewed a routine observation. A question raised on the floor was withdrawn once the entry was reread. Referred to the dated decisions and closed.

- 2026-06-20: A shift handover reviewed a routine observation. An operator asked whether a credit had posted; it had, in the preceding period. Filed for the record.

- 2026-06-17: An on-call engineer recorded a routine observation. The count sat a little above the running mean, entirely from estimated inputs.

- 2026-06-13: The operations desk spot-checked a routine observation. Nightly reconciliation matched exactly and the file was released without comment.
