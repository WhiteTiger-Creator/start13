// Stage one of the reference: rebuild the authoritative inventory positions the
// failed rollout truncated at /app/data/inventory_positions.json.
//
// Governed by #MRP-4170 (replay semantics) and #MRP-4174 (shape of the result):
// start from the pre-rollout snapshot, replay the movement journal in ascending
// seq, and write the survivors back over the truncated file. Nothing the planner
// emits is correct until this has run.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
)

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

type movement struct {
	Seq       int    `json:"seq"`
	ItemID    string `json:"item_id"`
	Kind      string `json:"kind"`
	OnHand    *int64 `json:"on_hand"`
	ReceiptID string `json:"receipt_id"`
	Qty       int64  `json:"qty"`
	DueDay    int    `json:"due_day"`
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

func sortReceipts(rs []receipt) {
	sort.Slice(rs, func(i, j int) bool { return rs[i].ReceiptID < rs[j].ReceiptID })
}

func main() {
	// The replay stays runnable over a different snapshot and journal, so the
	// three paths are options defaulting to the operational ones.
	snapshotPath := flag.String("snapshot", "/app/data/inventory_snapshot_pre_rollout.json",
		"pre-rollout snapshot to replay onto")
	journalPath := flag.String("journal", "/app/data/inventory_movement_journal.json",
		"movement journal to replay")
	outPath := flag.String("out", "/app/data/inventory_positions.json",
		"where the rebuilt positions are written")
	flag.Parse()

	var snapshot []position
	var journal []movement
	readJSON(*snapshotPath, &snapshot)
	readJSON(*journalPath, &journal)

	live := make(map[string]*position, len(snapshot))
	for i := range snapshot {
		p := snapshot[i]
		sortReceipts(p.ScheduledReceipts)
		live[p.ItemID] = &p
	}
	// #MRP-4170: a retraction withdraws the position for good; a later movement
	// for that item does not resurrect it.
	retracted := map[string]bool{}

	// ascending seq, not file order (the journal ships ordered, but the rule is
	// the sequence number)
	sort.Slice(journal, func(i, j int) bool { return journal[i].Seq < journal[j].Seq })

	for _, m := range journal {
		if retracted[m.ItemID] {
			continue
		}
		p, ok := live[m.ItemID]
		if !ok {
			continue
		}
		switch m.Kind {
		case "adjust":
			if m.OnHand != nil {
				p.OnHand = *m.OnHand
			}
		case "receipt_add":
			p.ScheduledReceipts = append(p.ScheduledReceipts,
				receipt{ReceiptID: m.ReceiptID, Qty: m.Qty, DueDay: m.DueDay})
			sortReceipts(p.ScheduledReceipts)
		case "receipt_cancel":
			kept := p.ScheduledReceipts[:0]
			dropped := false
			for _, r := range p.ScheduledReceipts {
				if !dropped && r.ReceiptID == m.ReceiptID {
					dropped = true
					continue
				}
				kept = append(kept, r)
			}
			p.ScheduledReceipts = kept
		case "retract":
			retracted[m.ItemID] = true
			delete(live, m.ItemID)
		}
	}

	out := make([]position, 0, len(live))
	for _, p := range live {
		if p.ScheduledReceipts == nil {
			p.ScheduledReceipts = []receipt{}
		}
		out = append(out, *p)
	}
	// #MRP-4174: ascending item_id, and the record carries only the three
	// declared fields -- journal bookkeeping never survives the replay.
	sort.Slice(out, func(i, j int) bool { return out[i].ItemID < out[j].ItemID })

	encoded, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	encoded = append(encoded, '\n')
	if err := os.WriteFile(*outPath, encoded, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Fprintf(os.Stderr, "recovered %d positions\n", len(out))
}
