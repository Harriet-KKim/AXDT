# Repo Structure
- docs
  - sot
    - specification
    - requirements
    - rule
  - interim
    - ADR
    - plan
      - wave
      - task
- src
- test

# Rules
Docker를 통해서 Worktree 폴더만 접근 가능하도록 격리
Branch/Worktree naming 규칙

# Roles
- Maintainer
  - 프로젝트 전체 진척도 관리
  - Leader 생성을 통한 프로젝트 개발 진행 (Skill로 만들 예정)
  - Tmux로 Leader 관리
- Watcher
  - Maintainer 관리
  - context 확인
  - Cron 등을 통해 주기적으로 호출
- Leader
  - 기능 단위 개발 담당
  - 필요에 따라 Developer/Reviewer 호출
  - worktree에 종속됨
  - 작업 진행상황은 report 파일을 별도로 만들어서 Maintainer와 내용 공유 (Skill로 만들 예정)
- Developer
- Reviewer
- Tester

# Workflow
- 개발
  - Maintainer가 Worktree 생성 후 Leader Docker로 배치
  - Leader는 상세 구현 계획 (+리뷰), 실제 구현 (+리뷰), 유닛 테스트 진행
- 명세 업데이트
  - Leader가 report에 명세 업데이트 요구 시 Maintainer가 필요 여부 판단, 만약 업데이트 필요한 경우 SoT PR 생성.

# Doc format
- Specification
- Requirements
