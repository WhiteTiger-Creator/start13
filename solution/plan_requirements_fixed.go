// Stage two of the reference: the corrected requirements planner.
//
// Every governing value is traced to its final dated entry in
// /app/incident/planning_governance_log.md; report_spec.json supplies the output
// contract only and no derivation rule.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
)

type item struct {
	ItemID       string `json:"item_id"`
	LeadTimeDays int    `json:"lead_time_days"`
	LotPolicy    string `json:"lot_policy"`
	LotSize      int64  `json:"lot_size"`
	PeriodDays   int    `json:"period_days"`
	SafetyStock  int64  `json:"safety_stock"`
	UnitCostC    int64  `json:"unit_cost_cents"`
	YieldPct     int64  `json:"yield_pct"`
	FirmFence    int    `json:"firm_fence_days"`
	WorkCentre   string `json:"work_centre"`
	RunHours     int    `json:"run_hours"`
	Family       string `json:"family"`
}

type workCentre struct {
	WorkCentre  string `json:"work_centre"`
	DailyHours  int    `json:"daily_hours"`
	MaxPullDays int    `json:"max_pull_days"`
	SetupHours  int    `json:"setup_hours"`
}

type capacityFile struct {
	WorkCentres []workCentre `json:"work_centres"`
}

type bomRow struct {
	Parent        string `json:"parent_item"`
	Component     string `json:"component_item"`
	QtyPer        int64  `json:"qty_per"`
	ScrapPct      int64  `json:"scrap_pct"`
	EffectiveFrom int    `json:"effective_from"`
	EffectiveTo   int    `json:"effective_to"`
}

type demandRow struct {
	DemandID string `json:"demand_id"`
	ItemID   string `json:"item_id"`
	Qty      int64  `json:"qty"`
	DueDay   int    `json:"due_day"`
}

type receipt struct {
	ReceiptID string `json:"receipt_id"`
	Qty       int64  `json:"qty"`
	DueDay    int    `json:"due_day"`
}

type position struct {
	ItemID            string    `json:"item_id"`
	OnHand            int64     `json:"on_hand"`
	ScheduledReceipts []receipt `json:"scheduled_receipts"`
}

type calendar struct {
	HorizonDays    int   `json:"horizon_days"`
	NonWorkingDays []int `json:"non_working_days"`
}

type policy struct {
	Default map[string]int64 `json:"default"`
}

type plannedOrder struct {
	ItemID     string `json:"item_id"`
	ReceiptDay int    `json:"receipt_day"`
	ReleaseDay int    `json:"release_day"`
	Qty        int64  `json:"qty"`
	ReceiptQty int64  `json:"receipt_qty"`
	LotPolicy  string `json:"lot_policy"`
	Pushed     bool   `json:"pushed"`
	LoadDay    int    `json:"load_day"`
	Pulled     int    `json:"pulled"`
}

type itemPlan struct {
	ItemID        string         `json:"item_id"`
	LowLevelCode  int            `json:"low_level_code"`
	GrossTotal    int64          `json:"gross_requirement_total"`
	NetTotal      int64          `json:"net_requirement_total"`
	PlannedOrders []plannedOrder `json:"planned_orders"`
	EndingOnHand  int64          `json:"ending_on_hand"`
}

type exceptionRow struct {
	ItemID     string `json:"item_id"`
	Kind       string `json:"kind"`
	ReceiptDay int    `json:"receipt_day"`
	ReleaseDay int    `json:"release_day"`
	Qty        int64  `json:"qty"`
}

func readJSON(path string, into interface{}) {
	raw, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := json.Unmarshal(raw, into); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func writeJSON(path string, value interface{}) {
	encoded, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.WriteFile(path, append(encoded, '\n'), 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

// #MRP-4210: the release date steps back over WORKING days only, not raw
// calendar days. Stepping past day zero keeps counting, so the release day goes
// negative and the order is past due.
func offsetWorkingDays(day, lead int, nonWorking map[int]bool) int {
	d := day
	remaining := lead
	for remaining > 0 {
		d--
		if !nonWorking[d] {
			remaining--
		}
		if d < -10000 {
			break
		}
	}
	return d
}

// #MRP-4250: the firm fence sits the item's firm_fence_days WORKING days after
// day zero, day zero itself not counted. A fence of zero means the item has no
// fence at all.
func fenceDay(fence int, nonWorking map[int]bool) int {
	d := 0
	remaining := fence
	for remaining > 0 {
		d++
		if !nonWorking[d] {
			remaining--
		}
		if d > 10000 {
			break
		}
	}
	return d
}

// ceilDiv divides rounding away from zero for the non-negative quantities the
// allowances are applied to.
func ceilDiv(numerator, denominator int64) int64 {
	if denominator <= 0 {
		return numerator
	}
	return (numerator + denominator - 1) / denominator
}

// ceilScale returns ceil(value*mul/div) for non-negative quantities without
// ever forming value*mul, which overflows int64 well before the scaled result
// itself would. The allowances are stated as integer arithmetic on quantities
// the contract does not bound, so the intermediate must not be the limit.
func ceilScale(value, mul, div int64) int64 {
	if div <= 0 {
		return value * mul
	}
	whole, remainder := value/div, value%div
	return whole*mul + ceilDiv(remainder*mul, div)
}

// #MRP-4240: the policy is read from its fixed absolute path, and any field the
// file omits keeps its governed baseline. A missing Go map key is zero, not the
// baseline, so the fallback has to be explicit.
func policyValue(pol policy, field string, baseline int64) int64 {
	if value, ok := pol.Default[field]; ok {
		return value
	}
	return baseline
}


// #MRP-4256: finite capacity. Every planned order occupies its item's run hours
// at its work centre on the day it loads; a centre starts at most its daily
// hours on a working day and nothing at all on a non-working one. An order that
// does not fit is pulled EARLIER -- the draft that pushed it to the next working
// day was reversed -- and days are settled from the last working day backwards so
// that what a day sheds joins the candidates of the day before it.
type candidate struct {
	order      *plannedOrder
	hours      int
	family     int
	releaseDay int
}

// #MRP-4260: a day's hours are spent on run hours PLUS one changeover block per
// distinct family it starts, so what an order costs depends on which of its
// neighbours stay. bestRun reports the largest RUN total reachable from the
// candidates at or after `from`, given the hours still free and the families
// whose block the day has already paid for. Blocks are capacity spent, never
// work done, so they are charged against the room and never counted into the
// total that decides which set stays.
type dayFill struct {
	cands []candidate
	setup int
	memo  map[[3]int]int
}

func (f *dayFill) bestRun(from, room, paid int) int {
	if from >= len(f.cands) || room <= 0 {
		return 0
	}
	key := [3]int{from, room, paid}
	if cached, ok := f.memo[key]; ok {
		return cached
	}
	best := f.bestRun(from+1, room, paid)
	bit := 1 << f.cands[from].family
	cost := f.cands[from].hours
	if paid&bit == 0 {
		cost += f.setup
	}
	if cost <= room {
		if taken := f.cands[from].hours + f.bestRun(from+1, room-cost, paid|bit); taken > best {
			best = taken
		}
	}
	f.memo[key] = best
	return best
}

// staying picks the set whose run hours total the most without the day going
// over, and among the sets that tie, the one that keeps the order earlier in
// the plan order -- read in turn down the candidates, which arrive already in
// that order (#MRP-4256, as amended by #MRP-4260).
func staying(cands []candidate, room, setup int) map[int]bool {
	fill := &dayFill{cands: cands, setup: setup, memo: map[[3]int]int{}}
	target := fill.bestRun(0, room, 0)
	keep := make(map[int]bool, len(cands))
	paid := 0
	for i := range cands {
		bit := 1 << cands[i].family
		cost := cands[i].hours
		if paid&bit == 0 {
			cost += setup
		}
		if cost > room {
			continue
		}
		if cands[i].hours+fill.bestRun(i+1, room-cost, paid|bit) == target {
			keep[i] = true
			room -= cost
			target -= cands[i].hours
			paid |= bit
		}
	}
	return keep
}

func workingDaysBetween(from, to int, nonWorking map[int]bool) int {
	count := 0
	for d := from + 1; d <= to; d++ {
		if !nonWorking[d] {
			count++
		}
	}
	return count
}

func loadCapacity(plans []itemPlan, byID map[string]item, centres map[string]workCentre,
	nonWorking map[int]bool) (pulled, exceeded, loadedDays int, raised []exceptionRow) {
	// #MRP-4260: a family is a changeover block, so each one needs a stable
	// index to carry in the day's paid-for set.
	familyNames := []string{}
	seenFamily := map[string]bool{}
	for _, it := range byID {
		if !seenFamily[it.Family] {
			seenFamily[it.Family] = true
			familyNames = append(familyNames, it.Family)
		}
	}
	sort.Strings(familyNames)
	familyIndex := map[string]int{}
	for i, name := range familyNames {
		familyIndex[name] = i
	}

	perCentre := map[string]map[int][]candidate{}
	for i := range plans {
		for j := range plans[i].PlannedOrders {
			order := &plans[i].PlannedOrders[j]
			it := byID[order.ItemID]
			day := order.ReleaseDay
			order.LoadDay = day
			order.Pulled = 0
			if perCentre[it.WorkCentre] == nil {
				perCentre[it.WorkCentre] = map[int][]candidate{}
			}
			perCentre[it.WorkCentre][day] = append(perCentre[it.WorkCentre][day],
				candidate{order: order, hours: it.RunHours,
					family: familyIndex[it.Family], releaseDay: day})
		}
	}

	names := make([]string, 0, len(perCentre))
	for name := range perCentre {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		released := perCentre[name]
		centre := centres[name]
		low, high := 0, 0
		first := true
		for day := range released {
			if first || day < low {
				low = day
			}
			if first || day > high {
				high = day
			}
			first = false
		}
		// nothing may be pulled further back than the centre allows
		for step := 0; step < centre.MaxPullDays; {
			low--
			if !nonWorking[low] {
				step++
			}
		}
		carried := []candidate{}
		for day := high; day >= low; day-- {
			cands := append(append([]candidate{}, released[day]...), carried...)
			carried = nil
			if len(cands) == 0 {
				continue
			}
			sort.Slice(cands, func(i, j int) bool {
				if cands[i].order.ItemID != cands[j].order.ItemID {
					return cands[i].order.ItemID < cands[j].order.ItemID
				}
				return cands[i].order.ReceiptDay < cands[j].order.ReceiptDay
			})
			room := centre.DailyHours
			if nonWorking[day] {
				room = 0 // a non-working day starts nothing
			}
			keep := staying(cands, room, centre.SetupHours)
			if len(keep) > 0 {
				loadedDays++
			}
			for i, c := range cands {
				if keep[i] {
					c.order.LoadDay = day
					c.order.Pulled = workingDaysBetween(day, c.releaseDay, nonWorking)
					if c.order.Pulled > 0 {
						pulled++
					}
					continue
				}
				previous := day - 1
				for previous >= low && nonWorking[previous] {
					previous--
				}
				moved := -1
				if previous >= low {
					moved = workingDaysBetween(previous, c.releaseDay, nonWorking)
				}
				if moved < 0 || moved > centre.MaxPullDays {
					c.order.LoadDay = c.releaseDay
					c.order.Pulled = 0
					exceeded++
					raised = append(raised, exceptionRow{
						ItemID: c.order.ItemID, Kind: "capacity_exceeded",
						ReceiptDay: c.order.ReceiptDay, ReleaseDay: c.order.ReleaseDay,
						Qty: c.order.Qty,
					})
					continue
				}
				carried = append(carried, c)
			}
		}
	}
	return pulled, exceeded, loadedDays, raised
}

func main() {
	input := flag.String("input", "/app/data/inventory_positions.json", "inventory positions")
	outputDir := flag.String("output-dir", "/app/output", "output directory")
	flag.Parse()

	var items []item
	var bom []bomRow
	var demand []demandRow
	var positions []position
	var cal calendar
	var pol policy
	var capacity capacityFile

	// #MRP-4150: the master data, bill of materials, demand, calendar and policy
	// are always read from their fixed absolute paths; --input selects the
	// positions file only.
	readJSON("/app/data/item_master.json", &items)
	readJSON("/app/data/bill_of_materials.json", &bom)
	readJSON("/app/data/independent_demand.json", &demand)
	readJSON("/app/data/planning_calendar.json", &cal)
	readJSON("/app/data/planning_policy.json", &pol)
	readJSON("/app/data/work_centre_capacity.json", &capacity)
	readJSON(*input, &positions)

	nonWorking := make(map[int]bool, len(cal.NonWorkingDays))
	for _, d := range cal.NonWorkingDays {
		nonWorking[d] = true
	}
	graceDays := int(policyValue(pol, "past_due_grace_days", 2))
	exceptionMinQty := policyValue(pol, "exception_min_qty", 40)
	maxBacklog := int(policyValue(pol, "max_release_backlog_days", 14))
	posCap := int(policyValue(pol, "period_of_supply_cap_days", 20))

	byID := make(map[string]item, len(items))
	for _, it := range items {
		byID[it.ItemID] = it
	}
	posByID := make(map[string]position, len(positions))
	for _, p := range positions {
		posByID[p.ItemID] = p
	}

	children := map[string][]bomRow{}
	isComponent := map[string]bool{}
	for _, r := range bom {
		children[r.Parent] = append(children[r.Parent], r)
		isComponent[r.Component] = true
	}

	// #MRP-4190: the low-level code is the DEEPEST level at which an item appears
	// anywhere in the structure, not the first level it is met at. Computed once
	// by relaxing over the structure; re-exploding per demand line does not
	// finish inside the budget.
	llc := map[string]int{}
	for _, it := range items {
		llc[it.ItemID] = 0
	}
	order := make([]string, 0, len(items))
	for _, it := range items {
		order = append(order, it.ItemID)
	}
	sort.Strings(order)
	for pass := 0; pass < len(items); pass++ {
		changed := false
		for _, parent := range order {
			for _, r := range children[parent] {
				if llc[parent]+1 > llc[r.Component] {
					llc[r.Component] = llc[parent] + 1
					changed = true
				}
			}
		}
		if !changed {
			break
		}
	}

	horizon := cal.HorizonDays
	gross := map[string][]int64{}
	ensure := func(id string) []int64 {
		if _, ok := gross[id]; !ok {
			gross[id] = make([]int64, horizon+1)
		}
		return gross[id]
	}
	for _, d := range demand {
		if d.DueDay < 0 || d.DueDay > horizon {
			continue
		}
		g := ensure(d.ItemID)
		g[d.DueDay] += d.Qty
	}

	// #MRP-4192: items are planned in ascending low-level code, then ascending
	// item id, so a parent's planned releases are already known when its
	// components are netted.
	planOrder := append([]string(nil), order...)
	sort.Slice(planOrder, func(i, j int) bool {
		if llc[planOrder[i]] != llc[planOrder[j]] {
			return llc[planOrder[i]] < llc[planOrder[j]]
		}
		return planOrder[i] < planOrder[j]
	})

	plans := make([]itemPlan, 0, len(items))
	exceptions := make([]exceptionRow, 0)
	var totalPlannedQty, totalReceiptQty, totalNet int64
	plannedOrderCount, phantomCount, pushedCount := 0, 0, 0

	for _, id := range planOrder {
		it := byID[id]
		g := ensure(id)
		sched := make([]int64, horizon+1)
		var onHand int64
		if p, ok := posByID[id]; ok {
			onHand = p.OnHand
			for _, r := range p.ScheduledReceipts {
				if r.DueDay >= 0 && r.DueDay <= horizon {
					sched[r.DueDay] += r.Qty
				}
			}
		}

		var grossTotal, netTotal int64
		for _, v := range g {
			grossTotal += v
		}

		phantom := it.LotPolicy == "phantom"
		if phantom {
			phantomCount++
		}
		fence := 0
		if it.FirmFence > 0 {
			fence = fenceDay(it.FirmFence, nonWorking)
		}

		available := onHand
		orders := make([]plannedOrder, 0)
		for day := 0; day <= horizon; day++ {
			available += sched[day] - g[day]
			if available >= it.SafetyStock {
				continue
			}
			// #MRP-4200: the shortfall is measured against the safety stock, so
			// safety stock is covered by the order rather than eaten into.
			shortfall := it.SafetyStock - available
			// #MRP-4204: the lot policy sizes the quantity that must ARRIVE good.
			receiptQty := shortfall
			switch it.LotPolicy {
			case "fixed_quantity":
				if it.LotSize > 0 {
					lots := (shortfall + it.LotSize - 1) / it.LotSize
					receiptQty = lots * it.LotSize
				}
			case "period_of_supply":
				span := it.PeriodDays
				if posCap > 0 && span > posCap {
					span = posCap
				}
				for k := day + 1; k < day+span && k <= horizon; k++ {
					if extra := g[k] - sched[k]; extra > 0 {
						receiptQty += extra
					}
				}
			}
			// #MRP-4234: the RELEASED quantity is the arriving quantity inflated for
			// the item's own yield, rounded up, and the lot policy has already sized
			// the arrival -- the inflation is never re-sized to a lot multiple.
			released := receiptQty
			if it.YieldPct > 0 && it.YieldPct < 100 {
				released = ceilScale(receiptQty, 100, it.YieldPct)
			}
			netTotal += shortfall
			totalNet += shortfall

			// #MRP-4242: a phantom is netted like any other item but raises no order,
			// and what it passes on moves on the day it arrived -- its own lead time
			// is never offset.
			release := day
			pushed := false
			if !phantom {
				release = offsetWorkingDays(day, it.LeadTimeDays, nonWorking)
				// #MRP-4250: a release inside the firm fence is pushed OUT to the
				// fence day; the receipt day does not move, so the order is knowingly
				// late rather than the requirement being moved.
				if it.FirmFence > 0 && release < fence {
					release = fence
					pushed = true
					pushedCount++
				}
				orders = append(orders, plannedOrder{
					ItemID: id, ReceiptDay: day, ReleaseDay: release,
					Qty: released, ReceiptQty: receiptQty,
					LotPolicy: it.LotPolicy, Pushed: pushed,
				})
			}
			// the projected balance is credited with what ARRIVES, not what was
			// released
			available += receiptQty

			if pushed {
				// #MRP-4250: a pushed order is always reported, whatever its size.
				exceptions = append(exceptions, exceptionRow{
					ItemID: id, Kind: "inside_fence", ReceiptDay: day,
					ReleaseDay: release, Qty: released,
				})
			} else if !phantom && released >= exceptionMinQty && release < -graceDays {
				// #MRP-4220: an order whose release falls before day zero by more than
				// the grace is past due; one that also exceeds the backlog window is
				// reported separately, and both only when the lot is material.
				kind := "past_due_release"
				if -release > maxBacklog {
					kind = "backlog_exceeded"
				}
				exceptions = append(exceptions, exceptionRow{
					ItemID: id, Kind: kind, ReceiptDay: day,
					ReleaseDay: release, Qty: released,
				})
			}

			// dependent demand lands on the component at the parent's RELEASE day,
			// driven by the RELEASED quantity because the components must be issued
			// for everything the order starts, scrap included.
			if release >= 0 && release <= horizon {
				for _, r := range children[id] {
					// #MRP-4246: only a line effective on that release day applies.
					if release < r.EffectiveFrom || release > r.EffectiveTo {
						continue
					}
					// #MRP-4238: the line's scrap allowance inflates what must be issued.
					need := released * r.QtyPer
					if r.ScrapPct > 0 && r.ScrapPct < 100 {
						need = ceilScale(need, 100, 100-r.ScrapPct)
					}
					cg := ensure(r.Component)
					cg[release] += need
				}
			}
		}

		for _, o := range orders {
			totalPlannedQty += o.Qty
			totalReceiptQty += o.ReceiptQty
		}
		plannedOrderCount += len(orders)
		plans = append(plans, itemPlan{
			ItemID: id, LowLevelCode: llc[id], GrossTotal: grossTotal,
			NetTotal: netTotal, PlannedOrders: orders, EndingOnHand: available,
		})
	}

	// #MRP-4230: the plan is emitted ascending by item id; the exception queue is
	// worst backlog first, then by item and receipt day.
	sort.Slice(plans, func(i, j int) bool { return plans[i].ItemID < plans[j].ItemID })

	// #MRP-4256: the finished orders are loaded against the work centres before
	// the queue is ordered, so the capacity exceptions take their place in it.
	centres := make(map[string]workCentre, len(capacity.WorkCentres))
	for _, wc := range capacity.WorkCentres {
		centres[wc.WorkCentre] = wc
	}
	pulledCount, capacityExceeded, loadedCentreDays, capacityExceptions :=
		loadCapacity(plans, byID, centres, nonWorking)
	exceptions = append(exceptions, capacityExceptions...)

	// #MRP-4230: the key runs over every field a row carries, so the order is
	// total. The previous form compared only the first three and used the UNSTABLE
	// sort.Slice, which left rows tying on those three -- an order reported both
	// inside_fence and capacity_exceeded on the same day -- in whatever order
	// pdqsort happened to produce, and sealed that accident into the fixture.
	sort.SliceStable(exceptions, func(i, j int) bool {
		if exceptions[i].ReleaseDay != exceptions[j].ReleaseDay {
			return exceptions[i].ReleaseDay < exceptions[j].ReleaseDay
		}
		if exceptions[i].ItemID != exceptions[j].ItemID {
			return exceptions[i].ItemID < exceptions[j].ItemID
		}
		if exceptions[i].ReceiptDay != exceptions[j].ReceiptDay {
			return exceptions[i].ReceiptDay < exceptions[j].ReceiptDay
		}
		if exceptions[i].Kind != exceptions[j].Kind {
			return exceptions[i].Kind < exceptions[j].Kind
		}
		return exceptions[i].Qty < exceptions[j].Qty
	})

	maxLLC := 0
	for _, v := range llc {
		if v > maxLLC {
			maxLLC = v
		}
	}
	pastDue := 0
	for _, e := range exceptions {
		if e.Kind == "past_due_release" || e.Kind == "backlog_exceeded" {
			pastDue++
		}
	}

	if err := os.MkdirAll(*outputDir, 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	summary := map[string]interface{}{
		"schema_version":              "mrp-plan-v1",
		"item_count":                  len(plans),
		"position_count":              len(positions),
		"planned_order_count":         plannedOrderCount,
		"total_planned_qty":           totalPlannedQty,
		"total_receipt_qty":           totalReceiptQty,
		"phantom_item_count":          phantomCount,
		"pushed_order_count":          pushedCount,
		"pulled_order_count":           pulledCount,
		"capacity_exceeded_count":      capacityExceeded,
		"loaded_work_centre_day_count": loadedCentreDays,
		"total_net_requirement":       totalNet,
		"exception_count":             len(exceptions),
		"past_due_count":              pastDue,
		"max_low_level_code":          maxLLC,
		"effective_grace_days":        graceDays,
		"effective_exception_min_qty": exceptionMinQty,
		"effective_max_backlog_days":  maxBacklog,
		"effective_pos_cap_days":      posCap,
	}
	writeJSON(*outputDir+"/summary.json", summary)
	writeJSON(*outputDir+"/item_plan.json", plans)

	handle, err := os.Create(*outputDir + "/exception_queue.jsonl")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer handle.Close()
	enc := json.NewEncoder(handle)
	for _, e := range exceptions {
		if err := enc.Encode(e); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	fmt.Fprintf(os.Stderr, "planned %d orders across %d items\n", plannedOrderCount, len(plans))
}
