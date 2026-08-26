# Planning governance log

How the requirements planner is *meant* to behave -- the recovery of the truncated inventory positions, the low-level coding, the netting of gross requirements against on-hand and scheduled receipts, safety-stock treatment, lot sizing, yield and scrap allowances, phantom assemblies, component effectivity, the lead-time offset, the firm fence, dependent demand, the finite capacity of the work centres and exception reporting -- was settled incrementally by the planning board, and those decisions live in the review entries below, not in any single summary. Several stages deliberately DEVIATE from a textbook MRP run: the low-level code is the deepest level rather than the first, the lead-time offset counts working days rather than calendar days, safety stock is covered rather than consumed, dependent demand lands on the release day rather than the receipt day, a released order is over-released for yield while the balance is credited only with what arrives, a line's scrap allowance is added to what it issues, a phantom assembly is blown through without an order or a lead-time offset, a line's effectivity turns on the release day, a release inside the firm fence is pushed out rather than left past due, and an order a work centre has no hours for is pulled earlier rather than pushed later. The February draft proposals were revisited during the 2026-05 planning review and several were reversed; where a draft or interim conflicts with a later decision, the later dated decision governs. `/app/docs/report_spec.json` is the output contract only.

- 2026-02-25: Materials review for the goods-in dock in window 1002 closed with no action; the standing parameters were reconfirmed as they are.

> **Capacity draft proposal (2026-02-11 - #MRP-4030)** Marek: where a work centre is loaded past its day's hours, the orders that do not fit go to the NEXT working day, since the shop cannot start work it has no hours for and the requirement can wait a day *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-04 - #MRP-4022)** Rosa: where the positions file has been truncated, rebuild it by appending the movement journal to the pre-rollout snapshot and letting the later record win on collision; retracted items come back if a later movement mentions them *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-09 - #MRP-4028)** Anders: the low-level code of an item is the FIRST level at which the explosion reaches it, since that is the level the planner meets it on *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-15 - #MRP-4034)** Rosa: lead time is subtracted in raw calendar days; the shop calendar is a reporting convenience and does not enter the offset *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-21 - #MRP-4040)** Marek: safety stock is a buffer to be consumed, so a shortfall is measured against zero and the buffer is refilled by the following order *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-11 - #MRP-4030)** Anders: an item's yield is a shop-floor concern reported after the fact; the planner releases exactly the quantity the requirement calls for and does not inflate it *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-17 - #MRP-4036)** Marek: a component's scrap allowance is carried in the standard cost and must not be added to the issued quantity, or the allowance would be counted twice *(Superseded -- reversed in the 2026-05 planning review.)*

> **Recovery draft proposal (2026-02-24 - #MRP-4042)** Rosa: a phantom assembly is planned like any other item -- it is netted, sized, offset by its own lead time and raises its own planned order *(Superseded -- reversed in the 2026-05 planning review.)*

- 2026-02-14: Shift lead recorded a routine note against line 3 assembly for window 1004. Expediting queue reviewed and cleared with no amendment raised.

- 2026-02-03: Scheduling desk noted a supplier acknowledgement backlog on the packaging lane in window 1005. Chased with procurement; the planning parameters were not touched.

- 2026-02-03: Shift lead recorded a routine note against line 3 assembly for window 1006. Expediting queue reviewed and cleared with no amendment raised.

- 2026-02-18: Materials review for the sub-assembly cell in window 1007 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-02-14: Planner on duty logged a routine observation for the goods-in dock during review window 1009. Cycle-count variances reconciled; no policy change requested.

- 2026-02-12: Planner on duty logged a routine observation for supplier portal feeds during review window 1011. Cycle-count variances reconciled; no policy change requested.

- 2026-02-08: Shift lead recorded a routine note against the packaging lane for window 1013. Expediting queue reviewed and cleared with no amendment raised.

- 2026-02-09: Scheduling desk noted a supplier acknowledgement backlog on line 3 assembly in window 1016. Chased with procurement; the planning parameters were not touched.

- 2026-02-22: Shift lead recorded a routine note against line 3 assembly for window 1019. Expediting queue reviewed and cleared with no amendment raised.

- 2026-02-13: Scheduling desk noted a supplier acknowledgement backlog on the goods-in dock in window 1022. Chased with procurement; the planning parameters were not touched.

- 2026-02-23: Planner on duty logged a routine observation for the goods-in dock during review window 1025. Cycle-count variances reconciled; no policy change requested.

- 2026-02-09: Materials review for supplier portal feeds in window 1028 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-02-21: Planner on duty logged a routine observation for supplier portal feeds during review window 1030. Cycle-count variances reconciled; no policy change requested.

- 2026-02-18: Planner on duty logged a routine observation for the packaging lane during review window 1033. Cycle-count variances reconciled; no policy change requested.

- 2026-02-06: Materials review for line 3 assembly in window 1034 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-02-25: Planner on duty logged a routine observation for line 3 assembly during review window 1037. Cycle-count variances reconciled; no policy change requested.

- 2026-02-12: Planner on duty logged a routine observation for the goods-in dock during review window 1038. Cycle-count variances reconciled; no policy change requested.

- 2026-02-09: Scheduling desk noted a supplier acknowledgement backlog on the sub-assembly cell in window 1041. Chased with procurement; the planning parameters were not touched.

- 2026-02-13: Scheduling desk noted a supplier acknowledgement backlog on the goods-in dock in window 1042. Chased with procurement; the planning parameters were not touched.

- 2026-02-27: Scheduling desk noted a supplier acknowledgement backlog on the goods-in dock in window 1043. Chased with procurement; the planning parameters were not touched.

- 2026-02-01: Materials review for the packaging lane in window 1045 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-02-27: Shift lead recorded a routine note against line 3 assembly for window 1048. Expediting queue reviewed and cleared with no amendment raised.

- 2026-02-05: Materials review for the packaging lane in window 1049 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-03-27: Shift lead recorded a routine note against the goods-in dock for window 1052. Expediting queue reviewed and cleared with no amendment raised.

> **Interim decision (2026-03-06 - #MRP-4048)** Priya: a bill-of-materials line's effectivity window is tested against the day the parent order is RECEIVED, that being the day the components are consumed *(Revised -- see the 2026-05 planning review.)*

> **Interim decision (2026-03-14 - #MRP-4052)** Lena: the firm fence is advisory. A release computed inside it is left where it falls and reported past due like any other early release *(Revised -- see the 2026-05 planning review.)*

> **Interim decision (2026-03-03 - #MRP-4058)** Priya: dependent demand from a parent lands on its components on the day the parent's order is RECEIVED *(Revised -- see the 2026-05 planning review.)*

- 2026-03-14: Planner on duty logged a routine observation for the packaging lane during review window 1053. Cycle-count variances reconciled; no policy change requested.

- 2026-03-06: Planner on duty logged a routine observation for line 3 assembly during review window 1054. Cycle-count variances reconciled; no policy change requested.

- 2026-03-25: Planner on duty logged a routine observation for the sub-assembly cell during review window 1056. Cycle-count variances reconciled; no policy change requested.

- 2026-03-08: Scheduling desk noted a supplier acknowledgement backlog on supplier portal feeds in window 1059. Chased with procurement; the planning parameters were not touched.

- 2026-03-11: Scheduling desk noted a supplier acknowledgement backlog on line 3 assembly in window 1062. Chased with procurement; the planning parameters were not touched.

- 2026-03-03: Materials review for the packaging lane in window 1064 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-03-04: Materials review for the goods-in dock in window 1066 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-03-11: Planner on duty logged a routine observation for line 3 assembly during review window 1067. Cycle-count variances reconciled; no policy change requested.

- 2026-03-15: Planner on duty logged a routine observation for line 3 assembly during review window 1069. Cycle-count variances reconciled; no policy change requested.

- 2026-03-21: Materials review for line 3 assembly in window 1070 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-03-14: Planner on duty logged a routine observation for the sub-assembly cell during review window 1072. Cycle-count variances reconciled; no policy change requested.

- 2026-03-09: Materials review for supplier portal feeds in window 1075 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-03-16: Planner on duty logged a routine observation for the sub-assembly cell during review window 1077. Cycle-count variances reconciled; no policy change requested.

- 2026-03-10: Scheduling desk noted a supplier acknowledgement backlog on the packaging lane in window 1079. Chased with procurement; the planning parameters were not touched.

- 2026-03-21: Planner on duty logged a routine observation for supplier portal feeds during review window 1080. Cycle-count variances reconciled; no policy change requested.

- 2026-03-27: Planner on duty logged a routine observation for the goods-in dock during review window 1081. Cycle-count variances reconciled; no policy change requested.

- 2026-03-24: Shift lead recorded a routine note against supplier portal feeds for window 1082. Expediting queue reviewed and cleared with no amendment raised.

- 2026-03-27: Shift lead recorded a routine note against the packaging lane for window 1083. Expediting queue reviewed and cleared with no amendment raised.

- 2026-03-21: Materials review for the sub-assembly cell in window 1086 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-03-10: Scheduling desk noted a supplier acknowledgement backlog on line 3 assembly in window 1089. Chased with procurement; the planning parameters were not touched.

- 2026-03-16: Scheduling desk noted a supplier acknowledgement backlog on the goods-in dock in window 1092. Chased with procurement; the planning parameters were not touched.

- 2026-04-17: Scheduling desk noted a supplier acknowledgement backlog on supplier portal feeds in window 1095. Chased with procurement; the planning parameters were not touched.

- 2026-04-20: Scheduling desk noted a supplier acknowledgement backlog on the packaging lane in window 1098. Chased with procurement; the planning parameters were not touched.

- 2026-04-14: Shift lead recorded a routine note against the goods-in dock for window 1099. Expediting queue reviewed and cleared with no amendment raised.

- 2026-04-27: Scheduling desk noted a supplier acknowledgement backlog on line 3 assembly in window 1102. Chased with procurement; the planning parameters were not touched.

- 2026-04-04: Planner on duty logged a routine observation for the packaging lane during review window 1103. Cycle-count variances reconciled; no policy change requested.

- 2026-04-07: Shift lead recorded a routine note against line 3 assembly for window 1106. Expediting queue reviewed and cleared with no amendment raised.

- 2026-04-26: Materials review for supplier portal feeds in window 1109 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-04-01: Planner on duty logged a routine observation for the packaging lane during review window 1110. Cycle-count variances reconciled; no policy change requested.

- 2026-04-16: Planner on duty logged a routine observation for the packaging lane during review window 1111. Cycle-count variances reconciled; no policy change requested.

- 2026-04-07: Scheduling desk noted a supplier acknowledgement backlog on the packaging lane in window 1114. Chased with procurement; the planning parameters were not touched.

- 2026-04-18: Materials review for the goods-in dock in window 1116 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-04-17: Materials review for supplier portal feeds in window 1118 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-04-08: Materials review for the packaging lane in window 1121 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-04-25: Planner on duty logged a routine observation for the goods-in dock during review window 1123. Cycle-count variances reconciled; no policy change requested.

- 2026-04-22: Scheduling desk noted a supplier acknowledgement backlog on the sub-assembly cell in window 1124. Chased with procurement; the planning parameters were not touched.

- 2026-04-22: Shift lead recorded a routine note against the packaging lane for window 1127. Expediting queue reviewed and cleared with no amendment raised.

- 2026-04-09: Planner on duty logged a routine observation for line 3 assembly during review window 1130. Cycle-count variances reconciled; no policy change requested.

- 2026-04-08: Shift lead recorded a routine note against the sub-assembly cell for window 1132. Expediting queue reviewed and cleared with no amendment raised.

- 2026-04-01: Materials review for the sub-assembly cell in window 1133 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-04-18: Scheduling desk noted a supplier acknowledgement backlog on the sub-assembly cell in window 1134. Chased with procurement; the planning parameters were not touched.

- 2026-04-06: Planner on duty logged a routine observation for line 3 assembly during review window 1136. Cycle-count variances reconciled; no policy change requested.

- 2026-04-24: Planner on duty logged a routine observation for supplier portal feeds during review window 1137. Cycle-count variances reconciled; no policy change requested.

- 2026-04-25: Shift lead recorded a routine note against the goods-in dock for window 1138. Expediting queue reviewed and cleared with no amendment raised.

- 2026-05-08: Shift lead recorded a routine note against the packaging lane for window 1141. Expediting queue reviewed and cleared with no amendment raised.

> **Governance decision (2026-05-04 - #MRP-4150)** Priya: Input paths, final. The item master, bill of materials, independent demand, planning calendar, planning policy and work-centre capacity are always read from their fixed absolute paths under /app/data; `--input` selects the inventory positions file only and never relocates any of the others. Both `--input` and `--output-dir` keep their documented defaults.

> **Governance decision (2026-05-06 - #MRP-4170)** Yusuf: Position recovery, final (supersedes #MRP-4022). Start from the pre-rollout snapshot and replay the movement journal in ascending `seq`, never in file order. An `adjust` overwrites the item's on-hand in place. A `receipt_add` adds the scheduled receipt it carries. A `receipt_cancel` drops the first scheduled receipt whose `receipt_id` matches, and is a no-op when the item holds no such receipt; where the item holds more than one receipt under that id, the first is the one the record carries first and only that one goes. A `retract` withdraws the item's position for good: once retracted, an item stays out and any later movement naming it is ignored. A movement naming an item the snapshot never carried is ignored.

> **Governance decision (2026-05-07 - #MRP-4174)** Yusuf: Recovered shape, final. The rebuilt file is a JSON array ascending by `item_id`. Each record carries exactly `item_id`, `on_hand` and `scheduled_receipts` -- the journal's bookkeeping fields (`seq`, `kind`, `posted_by`) never survive the replay. Within a record the scheduled receipts are ascending by `receipt_id`.

> **Governance decision (2026-05-11 - #MRP-4190)** Lena: Low-level code, final (supersedes #MRP-4028; deviates from a first-encounter reading). An item's low-level code is the DEEPEST level at which it appears anywhere in the structure, not the first level the explosion reaches it at. An item that is never a component has code 0. Because a component may be reached again through a longer path, the code has to be settled over the whole structure before any netting begins.

> **Governance decision (2026-05-12 - #MRP-4192)** Lena: Planning order, final. Items are planned in ascending low-level code, and within one code ascending by `item_id`, so every parent's planned releases are already known by the time its components are netted.

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

> **Governance decision (2026-05-28 - #MRP-4230)** Lena: Emission order, final. The item plan is ascending by `item_id`, and each item's planned orders stay in the order they were raised, earliest receipt day first. The exception queue is ascending by `release_day`, then by `item_id`, then by `receipt_day`, then by `kind`, then by `qty`. That key names every field a queue row carries, so two rows can only tie on it by being the same row: an order reported both `inside_fence` and `capacity_exceeded` on the same day separates on `kind`, and nothing is left to the order the rows happened to be raised in.

- 2026-05-21: Shift lead recorded a routine note against supplier portal feeds for window 1144. Expediting queue reviewed and cleared with no amendment raised.

- 2026-05-10: Scheduling desk noted a supplier acknowledgement backlog on line 3 assembly in window 1145. Chased with procurement; the planning parameters were not touched.

- 2026-05-01: Materials review for the packaging lane in window 1148 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-05-08: Scheduling desk noted a supplier acknowledgement backlog on line 3 assembly in window 1151. Chased with procurement; the planning parameters were not touched.

- 2026-05-07: Shift lead recorded a routine note against the sub-assembly cell for window 1152. Expediting queue reviewed and cleared with no amendment raised.

- 2026-05-11: Planner on duty logged a routine observation for the goods-in dock during review window 1153. Cycle-count variances reconciled; no policy change requested.

- 2026-05-05: Materials review for the sub-assembly cell in window 1155 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-05-26: Scheduling desk noted a supplier acknowledgement backlog on line 3 assembly in window 1156. Chased with procurement; the planning parameters were not touched.

- 2026-05-16: Scheduling desk noted a supplier acknowledgement backlog on line 3 assembly in window 1157. Chased with procurement; the planning parameters were not touched.

- 2026-05-26: Scheduling desk noted a supplier acknowledgement backlog on the sub-assembly cell in window 1159. Chased with procurement; the planning parameters were not touched.

- 2026-05-24: Planner on duty logged a routine observation for supplier portal feeds during review window 1161. Cycle-count variances reconciled; no policy change requested.

- 2026-05-24: Materials review for the sub-assembly cell in window 1163 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-05-23: Planner on duty logged a routine observation for line 3 assembly during review window 1166. Cycle-count variances reconciled; no policy change requested.

- 2026-05-22: Materials review for the sub-assembly cell in window 1167 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-05-22: Shift lead recorded a routine note against line 3 assembly for window 1170. Expediting queue reviewed and cleared with no amendment raised.

- 2026-05-25: Shift lead recorded a routine note against the sub-assembly cell for window 1171. Expediting queue reviewed and cleared with no amendment raised.

- 2026-05-08: Planner on duty logged a routine observation for the packaging lane during review window 1172. Cycle-count variances reconciled; no policy change requested.

- 2026-05-15: Shift lead recorded a routine note against line 3 assembly for window 1173. Expediting queue reviewed and cleared with no amendment raised.

- 2026-05-11: Planner on duty logged a routine observation for supplier portal feeds during review window 1176. Cycle-count variances reconciled; no policy change requested.

- 2026-06-19: Shift lead recorded a routine note against the goods-in dock for window 1177. Expediting queue reviewed and cleared with no amendment raised.

> **Governance decision (2026-06-05 - #MRP-4244)** Lena: Run summary, final. The counts the summary carries are aggregates of what the run itself emitted and nothing else. `item_count` is the number of item plans, `position_count` the number of records in the positions file the run read, and `max_low_level_code` the deepest code assigned. `planned_order_count` is every planned order across the plan, `total_planned_qty` the sum of the released quantities and `total_receipt_qty` the sum of the arriving ones, so the two differ exactly where a yield is short. `total_net_requirement` is the sum of the item plans' `net_requirement_total`, and an item's `ending_on_hand` is the projected balance left once the horizon is planned out. `phantom_item_count` counts the items the master gives a phantom lot policy, whether or not anything required them, and `pushed_order_count` the orders the fence moved. `exception_count` is the length of the queue and `past_due_count` the rows of it reported `past_due_release` or `backlog_exceeded` -- a pushed order is not past due and is not counted here. `pulled_order_count` is the orders whose `pulled` is not zero, `capacity_exceeded_count` the orders capacity could not place, and `loaded_work_centre_day_count` the number of work-centre working days that ended up carrying at least one order.

> **Governance decision (2026-06-02 - #MRP-4240)** Priya: Planning policy baseline, read from /app/data/planning_policy.json at that fixed absolute path. Any field the policy file omits keeps its baseline: past_due_grace_days = 2; exception_min_qty = 40; max_release_backlog_days = 14; period_of_supply_cap_days = 20.

- 2026-06-10: Scheduling desk noted a supplier acknowledgement backlog on the sub-assembly cell in window 1180. Chased with procurement; the planning parameters were not touched.

- 2026-06-17: Scheduling desk noted a supplier acknowledgement backlog on the goods-in dock in window 1181. Chased with procurement; the planning parameters were not touched.

- 2026-06-23: Shift lead recorded a routine note against the sub-assembly cell for window 1183. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-05: Shift lead recorded a routine note against the goods-in dock for window 1184. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-05: Shift lead recorded a routine note against the goods-in dock for window 1185. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-12: Scheduling desk noted a supplier acknowledgement backlog on the sub-assembly cell in window 1188. Chased with procurement; the planning parameters were not touched.

- 2026-06-03: Planner on duty logged a routine observation for the sub-assembly cell during review window 1189. Cycle-count variances reconciled; no policy change requested.

- 2026-06-14: Shift lead recorded a routine note against the sub-assembly cell for window 1190. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-17: Materials review for the packaging lane in window 1193 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-06-07: Scheduling desk noted a supplier acknowledgement backlog on the sub-assembly cell in window 1196. Chased with procurement; the planning parameters were not touched.

- 2026-06-04: Shift lead recorded a routine note against the sub-assembly cell for window 1197. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-01: Planner on duty logged a routine observation for the goods-in dock during review window 1199. Cycle-count variances reconciled; no policy change requested.

- 2026-06-13: Shift lead recorded a routine note against the goods-in dock for window 1202. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-03: Scheduling desk noted a supplier acknowledgement backlog on the sub-assembly cell in window 1203. Chased with procurement; the planning parameters were not touched.

- 2026-06-20: Scheduling desk noted a supplier acknowledgement backlog on the packaging lane in window 1205. Chased with procurement; the planning parameters were not touched.

- 2026-06-16: Scheduling desk noted a supplier acknowledgement backlog on supplier portal feeds in window 1207. Chased with procurement; the planning parameters were not touched.

- 2026-06-12: Shift lead recorded a routine note against the sub-assembly cell for window 1208. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-27: Shift lead recorded a routine note against the goods-in dock for window 1210. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-19: Scheduling desk noted a supplier acknowledgement backlog on the goods-in dock in window 1211. Chased with procurement; the planning parameters were not touched.

- 2026-06-02: Materials review for line 3 assembly in window 1213 closed with no action; the standing parameters were reconfirmed as they are.

- 2026-06-26: Shift lead recorded a routine note against the goods-in dock for window 1214. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-20: Shift lead recorded a routine note against the goods-in dock for window 1215. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-17: Shift lead recorded a routine note against the sub-assembly cell for window 1217. Expediting queue reviewed and cleared with no amendment raised.

- 2026-06-13: Materials review for line 3 assembly in window 1220 closed with no action; the standing parameters were reconfirmed as they are.
