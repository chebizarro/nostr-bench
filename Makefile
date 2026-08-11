PY := python
RUNS := runs

.PHONY: help install phase1 phase2 phase3 report smoke clean

help:
	@echo "nostr-bench targets:"
	@echo "  install   install python + node deps"
	@echo "  smoke     dry-run wiring check (no API calls)"
	@echo "  phase1    one-shot screen: all models x all suites x both tiers x n reps"
	@echo "  phase2    agent harness on models that advanced from phase1"
	@echo "  phase3    Repo Prompt CE orchestration pairings"
	@echo "  report    aggregate runs/*.json into report/results.html"

install:
	$(PY) -m pip install -r requirements.txt
	@echo "Node deps install lazily per-task on first grade. Ensure Node 22+ is on PATH."
	node --version

smoke:
	$(PY) -m grade.selfcheck
	$(PY) -m drivers.oneshot --task n1_implement --tier T1 --model DRYRUN --dry-run

phase1:
	$(PY) -m runner --phase phase1_oneshot

phase2:
	$(PY) -m runner --phase phase2_agent

phase3:
	$(PY) -m runner --phase phase3_orchestration

report:
	$(PY) -m report.aggregate $(RUNS) report/results.html
	@echo "open report/results.html"

clean:
	rm -rf $(RUNS)/*.tmp tasks/*/node_modules tasks/*/.work
