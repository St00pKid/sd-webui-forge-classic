@echo off

:: set PYTHON=
:: set GIT=
:: set VENV_DIR=

set COMMANDLINE_ARGS=--uv --reserve-vram 1 --cuda-malloc --cuda-stream --pin-shared-memory --flash
:: --xformers --sage --uv
:: --pin-shared-memory --cuda-malloc --cuda-stream
:: --skip-python-version-check --skip-torch-cuda-test --skip-version-check --skip-prepare-environment --skip-install

call webui.bat
