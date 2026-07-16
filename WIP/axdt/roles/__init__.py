"""Phase 2 — 역할(Role) 정의.

LLM 역할 5종(Maintainer·Leader·Developer·Reviewer·Tester)의 능력 등급·강제
등급·쓰기 경로·시스템 프롬프트를 담는 단일 정의원. 책임 경계 자체는
docs/sot/rule/role-responsibilities.md가 단일 명세이고, 여기는 그것을
코드(RoleSpec)와 프롬프트 문구(prompts/<role>.md)로 번역한다.
설계: WIP/specs/2026-07-09-phase2-roles-and-protocol-design.md §2.2·§3·§5.
"""
