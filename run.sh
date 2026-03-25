#!/bin/bash
# Launch vargen
cd "$(dirname "$0")"
python -m vargen --host 0.0.0.0 --port 8188 "$@"
