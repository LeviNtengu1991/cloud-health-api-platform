.PHONY: configure build up unit integration backup drill report metrics stop clean
configure:
	python3 scripts/configure.py
build:
	docker compose build db api ops
up:
	docker compose up -d --wait
unit:
	docker compose run --rm --no-deps --entrypoint python -v "$(CURDIR)/tests:/tests:ro" -v "$(CURDIR)/recovery:/app/recovery:ro" api -m unittest discover -s /tests -v
integration:
	docker compose up -d --wait db restore-db api
	python3 scripts/integration.py
backup:
	docker compose run --rm ops backup
drill:
	docker compose run --rm ops drill
report:
	docker compose run --rm --no-deps ops report
metrics:
	docker compose run --rm --no-deps ops metrics
stop:
	docker compose down
clean:
	@test "$(CONFIRM)" = "delete-lab-data" || (echo 'This deletes local databases and backups. Use make clean CONFIRM=delete-lab-data'; exit 1)
	docker compose down --volumes --remove-orphans
