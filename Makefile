.PHONY: metrics metrics-json metrics-html lint

metrics:
	@echo "== Radon Cyclomatic Complexity (A best, F worst) =="
	radon cc -s -a app || true
	@echo "\n== Radon Maintainability Index =="
	radon mi -s app || true
	@echo "\n== Xenon thresholds (max-abs=B, avg=A, modules=A) =="
	xenon --max-absolute B --max-average A --max-modules A app || true
	@echo "\n== Pylint design rules =="
	pylint -j 0 app || true

metrics-json:
	@mkdir -p reports
	radon cc -j app > reports/radon-cc.json || true
	radon mi -j app > reports/radon-mi.json || true
	radon hal -j app > reports/radon-hal.json || true
	pylint -f json -j 0 app > reports/pylint.json || true

metrics-html: metrics-json
	@echo "== Generating HTML report: reports/index.html =="
	@mkdir -p reports
	python3 scripts/generate_metrics_html.py reports || true
	@echo "Open reports/index.html in your browser."

lint:
	pylint -j 0 app
