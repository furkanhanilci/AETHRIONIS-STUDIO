#!/usr/bin/env bash
# AETHRION Studio. The DUM-E gateway reads the harness's state store, so the
# harness's package has to be importable for the lifecycle transitions.
export PYTHONPATH="$(dirname "$0"):/home/otonom/Desktop/FH/DUM-E"
exec python3 -m studio.app "$@"
