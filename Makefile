.PHONY: venv install test unit integration helper-check dev-install

venv:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip

install: venv
	.venv/bin/pip install -e . -e ./ui

unit:
	PYTHONPATH=src .venv/bin/python -m unittest \
		tests.unit.daemon.test_state_store \
		tests.unit.daemon.test_audio_manager \
		tests.unit.daemon.test_adb_adapter \
		tests.unit.daemon.test_android_backend \
		tests.unit.daemon.test_scrcpy_adapter \
		tests.unit.daemon.test_privilege_client

integration:
	PYTHONPATH=src .venv/bin/python -m unittest \
		tests.integration.test_api_status \
		tests.integration.test_video_and_doctor

test: unit integration

helper-check:
	cd helper && cargo check

dev-install:
	bash scripts/dev-install-all.sh
