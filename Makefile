PYTHON ?= .venv/bin/python

.PHONY: demo-ui demo-video

demo-ui:
	./scripts/run_demo_ui.sh

demo-video:
	$(PYTHON) examples/run_poc_video_demo.py
