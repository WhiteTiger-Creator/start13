// Requirements planner shipped with the ERP rollout, before the planning review.
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

// Steps the release date back by the lead time.
func offsetWorkingDays(day, lead int, _ map[int]bool) int {
	return day - lead
}

// Walks forward from day zero counting days the calendar does not mark
// non-working, and returns where it lands.
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

	// Operational inputs, read from their fixed absolute paths.
	readJSON("/app/data/item_master.json", &items)
	readJSON("/app/data/bill_of_materials.json", &bom)
	readJSON("/app/data/independent_demand.json", &demand)
	readJSON("/app/data/planning_calendar.json", &cal)
	readJSON("/app/data/planning_policy.json", &pol)
	readJSON(*input, &positions)

	nonWorking := make(map[int]bool, len(cal.NonWorkingDays))
	for _, d := range cal.NonWorkingDays {
		nonWorking[d] = true
	}
	graceDays := int(pol.Default["past_due_grace_days"])
	exceptionMinQty := pol.Default["exception_min_qty"]
	maxBacklog := int(pol.Default["max_release_backlog_days"])
	posCap := int(pol.Default["period_of_supply_cap_days"])

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

	// Low-level codes, computed once over the structure rather than per demand
	// line so the run stays inside its budget.
	llc := map[string]int{}
	seen := map[string]bool{}
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
				if seen[r.Component] {
					continue
				}
				seen[r.Component] = true
				llc[r.Component] = llc[parent] + 1
				changed = true
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

	// The order items are planned in.
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
		_ = phantom
		fence := 0
		if it.FirmFence > 0 {
			fence = fenceDay(it.FirmFence, nonWorking)
		}

		available := onHand
		orders := make([]plannedOrder, 0)
		for day := 0; day <= horizon; day++ {
			available += sched[day] - g[day]
			if available >= 0 {
				continue
			}
			// What the period is short by.
			shortfall := -available
			// Sized by the item's lot policy.
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
			// What is released for the arrival just sized.
			released := receiptQty
			netTotal += shortfall
			totalNet += shortfall

			// Where this item's release lands.
			pushed := false
			release := offsetWorkingDays(day, it.LeadTimeDays, nonWorking)
			_ = fence
			orders = append(orders, plannedOrder{
				ItemID: id, ReceiptDay: day, ReleaseDay: release,
				Qty: released, ReceiptQty: receiptQty,
				LotPolicy: it.LotPolicy, Pushed: pushed,
			})
			// Credits the projected balance.
			available += receiptQty

			if pushed {
				// Reported when the order was pushed.
				exceptions = append(exceptions, exceptionRow{
					ItemID: id, Kind: "inside_fence", ReceiptDay: day,
					ReleaseDay: release, Qty: released,
				})
			} else if !phantom && released >= exceptionMinQty && release < -graceDays {
				// Reported when the release lands early enough to matter.
				kind := "past_due_release"
				if -release > maxBacklog {
					kind = "backlog_exceeded"
				}
				exceptions = append(exceptions, exceptionRow{
					ItemID: id, Kind: kind, ReceiptDay: day,
					ReleaseDay: release, Qty: released,
				})
			}

			// Pushes this item's demand down to its components.
			if day >= 0 && day <= horizon {
				for _, r := range children[id] {
					// Skips a line outside its effectivity window.
					if day < r.EffectiveFrom || day > r.EffectiveTo {
						continue
					}
					// What the line has to issue.
					need := released * r.QtyPer
					cg := ensure(r.Component)
					cg[day] += need
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

	// Emission order.
	sort.Slice(plans, func(i, j int) bool { return plans[i].ItemID < plans[j].ItemID })
	sort.Slice(exceptions, func(i, j int) bool {
		if exceptions[i].ReleaseDay != exceptions[j].ReleaseDay {
			return exceptions[i].ReleaseDay < exceptions[j].ReleaseDay
		}
		if exceptions[i].ItemID != exceptions[j].ItemID {
			return exceptions[i].ItemID < exceptions[j].ItemID
		}
		return exceptions[i].ReceiptDay < exceptions[j].ReceiptDay
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
