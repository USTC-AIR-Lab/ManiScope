#!/usr/bin/env bash
# Local configuration is shell code: source only your own trusted file.
_MANIPSCOPE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_MANIPSCOPE_CONFIG="${MANIPSCOPE_CONFIG:-$_MANIPSCOPE_ROOT/configs/local.env}"
_MANIPSCOPE_SAVED="$(export -p)"
if [[ -f "$_MANIPSCOPE_CONFIG" ]]; then
  set -a
  source "$_MANIPSCOPE_CONFIG"
  set +a
  eval "$_MANIPSCOPE_SAVED"
fi
export ROBOTWIN_PYTHON="${ROBOTWIN_PYTHON:-python3}"
export YAML_PY="${YAML_PY:-python3}"
unset _MANIPSCOPE_ROOT _MANIPSCOPE_CONFIG _MANIPSCOPE_SAVED
