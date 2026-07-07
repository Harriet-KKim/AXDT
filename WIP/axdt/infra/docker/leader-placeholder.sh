#!/usr/bin/env bash
# AXDT Leader placeholder (Phase 3 seam).
#
# Phase 5의 agent runner가 이 명령을 대체한다(adapter.build_launch_command).
# 지금은 send-keys로 주입된 라인을 그대로 되울려, 주입→stdin→capture 경로를
# agent 없이 실증한다. 출력은 line-buffered(printf)로 즉시 캡처된다.
set -u

echo "axdt-leader placeholder ready (pid $$)"

while IFS= read -r line; do
  printf 'received: %s\n' "$line"
done
