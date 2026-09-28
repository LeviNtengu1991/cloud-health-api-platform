.PHONY: configure build up unit integration backup drill report metrics stop clean
configure:
	python3 scripts/configure.py
build:
	docker compose build db api ops unit-tests
up:
	docker compose up -d --wait
unit:
	docker compose run --build --rm --no-deps unit-tests
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
	docker compose --profile dashboard --profile testing down
clean:
	@test "$(CONFIRM)" = "delete-lab-data" || (echo 'This deletes local databases and backups. Use make clean CONFIRM=delete-lab-data'; exit 1)
	docker compose --profile dashboard --profile testing down --volumes --remove-orphans

.PHONY: dashboard s3-upload s3-drill
dashboard:
	docker compose --profile dashboard up -d --wait grafana
s3-upload:
	docker compose -f docker-compose.yml -f docker-compose.s3.yml run --rm ops s3-upload
s3-drill:
	docker compose -f docker-compose.yml -f docker-compose.s3.yml run --rm ops s3-drill
