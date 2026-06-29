# Leader 베이스 이미지 — git + placeholder.
# Phase 5에서 agent runner(Claude Code/Codex) 설치·자격증명으로 확장한다.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# placeholder: send-keys→stdin→capture 경로를 agent 없이 실증.
COPY leader-placeholder.sh /usr/local/bin/axdt-leader-placeholder
RUN chmod +x /usr/local/bin/axdt-leader-placeholder

# 사용자/HOME은 빌드시 고정하지 않는다.
# run에서 `--user <uid>:<gid>` + `-e HOME=/tmp/axdt-home` 주입(§6.3/§7).
CMD ["axdt-leader-placeholder"]
