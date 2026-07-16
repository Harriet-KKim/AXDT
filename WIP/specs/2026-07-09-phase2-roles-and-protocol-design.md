# Phase 2 — 역할(Role) 정의 & 통신 프로토콜 설계

> 상태: **10차 개정본 — 3모델 재리뷰 만장일치 치명 0으로 수렴** (문구 정밀화 반영) · 초안 2026-07-09 · 2~5차 개정 2026-07-10 · 6~10차 개정 2026-07-12 · 범위: Phase 2 (WIP/TODO.md) · 다음: Phase 5 훅 기반 판정기 재설계 → §8.3a 라이브 측정(§8.3a 주 재-시퀀싱)
> 산출 깊이: **문서 + 구현** — LLM 역할 5종의 책임·프롬프트·호출 인터페이스를 확정하고, 주입 규약·중계 규칙을 Python으로 구현한다. 역할의 *책임 경계*는 SoT rule에 두고(사용자 게이트 PR), *프롬프트 문구*는 `WIP/axdt/roles/`에 둔다.
> **Watcher 설계는 본 스펙에서 확정하지 않는다** — 별도 작업으로 분리했다(§2.4). 본 스펙은 그 작업이 지켜야 할 하한선과 답해야 할 질문만 고정한다.
> 관련 결정: D1(상시 tmux Maintainer), D2(통신), D3(workspace당 컨테이너 1개), D4(Claude Code ↔ Codex 추상화), D9(glue=Python), D12(AXDT 자체 코드는 `WIP/`), D15(강제 지점)
> 관련 ADR: `WIP/adr/0001`(상시 tmux Maintainer), `0002`(무 DB/큐/이벤트로그), `0003`(tmux 하향·report 상향·Leader 허브), `0004`(report→progress 권위 흐름), `0005`(agent runner 합성·주입 backend), `0006`(허브 git 격리), `0007`(계층 강제)
> 관련 규칙: `docs/sot/rule/subagent-no-direct-communication.md`, `leader-coordination-via-maintainer.md`, `progress-single-writer.md`, `report-to-progress-authority.md`, `protected-paths.md`, `branch-workspace-naming.md`
> 교차-Phase 계약: Phase 3(`leader.up` substrate·cron·컨테이너 이미지), Phase 4(`recover`·`commit`·상태 어휘), Phase 5(`PlatformAdapter`·`AgentRunner`·`SessionBackend`·`PLATFORM_MATRIX`), Phase 7(`WAITING_INPUT`·블로커→메신저), Phase 8(오케스트레이션 루프가 본 프로토콜을 소비)

---

## 0. 개정 이력과 이 문서의 신뢰 등급

초안과 2차 개정본이 각각 세 모델(Codex·Opus 4.8·Fable 5)의 독립 리뷰에서 **전원 "구현 착수 불가"** 판정을 받았다.

**초안**의 지적은 치명 5건·중대 10건이었다. 반영 과정에서 실제 CLI와 설정 파일을 직접 조사해 초안의 추측 여러 개를 사실로 대체하거나 폐기했다.

**2차 개정본**은 두 곳에서 무너졌고, 둘 다 개정이 *새로 만든* 결함이었다.

- **재기동 절차.** 초안의 "`down()`이 workspace를 지워서 재기동할 수 없다"를 `down(keep_workspace=True)`로 고쳤으나, `up()`이 무조건 부르는 `provision()`도 기존 workspace에 fail-fast한다는 것을 놓쳤다(실측). 결함이 `down()`에서 `up()`으로 자리만 옮겼다.
- **주입 멱등.** 초안의 ADR-0002 위반 저장소를 "tmux 캡처 로그에서 토큰 찾기"로 바꿨는데, 이것이 세 겹으로 실패했다. 주입자가 제출 직전에 죽으면 재시도가 영원히 `SKIPPED`되어 **초안과 똑같은 조용한 유실**이 남았고, 오라클로 삼은 파일을 정작 **피검증자인 Leader가 쓰며**, "회전 금지"를 못박는 순간 그 파일이 ADR-0002가 기각한 append-only 이벤트 로그가 됐다.

3차 개정본은 두 번째 결함을 **문제 재정의로 푼다.** 메시지 배달을 세지 않고 상태를 맞춘다 — "이 지시를 보냈던가"가 아니라 "이 지시가 지금도 필요한가"를 묻는다(§4.1).

**3차 개정본**은 재정의 자체를 세 리뷰가 옳다고 판정했으나, 그것을 구현하는 결정표가 자기 오라클과 어긋났다. `report_invalid`가 "report 부재"로 뭉개져 깨진 report 위에 배정을 덮었고, `progress=rejected`·`report=done`이 `in_rework`와 `pending_acceptance`에 동시에 들어가는데 우선순위가 없었으며, "plan 있음"은 선언된 입력만으로 관측할 수 없었고, `restart()`의 실패 경로가 보존하려던 workspace를 지웠다.

**4차 개정본은 두 가지를 근본적으로 잘못 짚었다.** 둘 다 저장소의 실제 git 위상을 확인하지 않은 탓이다.

- **`git fetch`는 아무것도 자재화하지 않는다.** `recover`는 작업트리 파일을 읽는데(실측), Leader의 report는 허브의 task 브랜치 ref로만 도착한다. fetch는 작업트리도 `main`도 건드리지 않으므로, in-flight task의 report는 **영원히 "부재"로 관측**된다. 관측 파이프라인 전체가 허공 위에 있었다.
- **조상 질의로는 반려를 판별할 수 없다.** 반려 커밋은 호스트 `main`에, report 커밋은 허브 task 브랜치에 있다. `main`은 그 브랜치를 merge하지 않으므로 **두 커밋은 정상 경로에서 언제나 갈라져 있다.** `git merge-base --is-ancestor`는 항상 거짓을 반환해 반려를 영영 전달하지 않는다. 4차 개정본은 force-push를 "경계 조건"으로 적으면서 정상 경로가 항상 그 조건임을 놓쳤다.

그리고 **배정의 전달을 `progress`에 기록하려던 시도**는 `rule-report-to-progress-authority`를 어기고(권위 필드를 배달 플래그로 겸용) Phase 4의 정합성 매트릭스를 오염시켰다(정상 배정마다 `WARN`). 철회했다.

5차 개정본은 report 블롭을 작업트리로 **자재화**하고, 반려를 **블롭 내용 비교**로 판별하며, 재전송 상한을 맥락 있는 호출자에게 넘긴다.

**5차 개정본은 세 리뷰에서 다시 전원 "구현 착수 불가" 판정을 받았다. 치명 셋 모두 5차가 새로 넣은 메커니즘이 만든 것이다.**

- **반려가 자기 결정표에 가려 전달되지 않는다.** 5차는 4차의 조상 질의를 블롭 비교로 대체했으나, 반려의 정상 관측(`progress=rejected`·`report=done`·`IDLE`)이 결정표에서 `report=done → 수용 판단 차례` 행에 먼저 걸린다. `rework_pushed`를 보는 반려 판별 행은 `report`에 `rejected`가 없어(실측: `schema.py`의 `REPORT_STATUSES`) 정상 경로에서 도달하지 못하는 죽은 코드였다. 세 리뷰가 독립으로 같은 결론에 이르렀다.
- **`git fetch`가 force-push를 버린다.** 5차의 refspec `refs/heads/*:…`에는 강제 갱신 표식 `+`가 없어 non-fast-forward를 거부한다. 허브는 force-push를 받지만(실측: `hub.py`가 `receive.denyDeletes`만 켜고 `denyNonFastForwards`는 켜지 않는다) 호스트 fetch가 그 갱신을 버려, 재작업이 amend·force-push 형태이면 관측이 반려 시점 블롭에 영원히 묶인다. "위상에 흔들리지 않는다"는 확정 서술이 정작 블롭을 *공급*하는 fetch의 미확인 성질 위에 있었다. Fable이 bare 허브로 실증했다(`! [rejected] … (non-fast-forward)`).
- **락이 자기를 막는다.** cron은 `flock -n <lock> <tick>`으로 tick을 감싸는데(실측: `cron.py`), 5차는 그 파일을 프로젝트 락으로 통합하고 tick도 같은 락을 다시 잡게 했다. `flock`은 열린 파일 서술자(OFD) 단위라 자식 tick의 별도 open을 통한 재획득이 부모 래퍼의 락에 거부되어(문서: `flock(2)`), watcher tick이 매 주기 아무 일도 못 한다.

넷째 개정과 같은 자리에서 무너졌다 — 실측 인용은 40여 건 표본이 전부 정확했고, 결함은 인용한 사실들 *사이*의 접합부에 있었다(결정표 행 순서와 반려 관측, fetch와 블롭 공급, cron 래퍼와 락 재획득).

6차 개정본은 반려 판별 행을 `report=done` 앞으로 옮기고, fetch에 `+`를 붙여 허브 경로에서 직접 가져오며, cron overlap 락과 프로젝트 락을 분리하고, materialize 실패를 진짜 부재로 정규화한다. 그리고 살아 있는 세션의 ERROR 오판·`post_mortem` 반쪽 상태·전역 이름공간 등 중대 지적을 함께 반영한다.

**6차 개정본도 세 리뷰에서 다시 "구현 착수 불가"를 받았다 — 치명 하나가 만장일치였다.** 6차는 5차 치명 3건(결정표 반려 가림·fetch force-push 거부·락 자기부정)을 실제로 고쳤고 세 모델이 이를 확인했다(거짓 실측 인용 0건). 그러나 6차가 5차의 "박제 시점" 지적을 "materialize는 커밋에 선행한다"는 **서술로만** 닫았고, 그 순서를 실행하는 절차 표면을 만들지 않았다. 실제 반려·수용 커밋 경로(`axdt progress commit`)는 materialize를 부르지 않고 작업트리에 이미 있는 report만 조건부로 스테이징하므로(실측: `commit.py`가 `report_path.exists()`일 때만 스테이징), 커밋 시점 report가 부재·낡음이면 반려 커밋에 블롭이 실리지 않는다. 수용은 과claim 검사가 이를 시끄럽게 거부하지만(실측: 검사가 `accepted` 이벤트에만 있다) 반려는 조용히 성립하고, 그 블롭 없는 커밋이 `rework_pushed` 오라클의 기준이 되어 **정상 경로에서 최초 반려가 영구히 전달되지 않는다.** 6차가 새로 넣은 삭제 정규화가 그 부재 창을 넓혔다.

그리고 6차의 평면 결정표 재정렬이 새 가림 둘을 만들었다 — report 기반 행이 "plan 있음·progress 행 없음" 블로커를 가리고(M-2), 반려 행이 재작업 중 올라온 새 블로커를 가린다(M-4). 5차에서도 6차에서도 평면 순서표는 재정렬마다 가림을 낳았다.

7차 개정본은 세 가지로 답한다. ① 수용/반려 절차(§7.4)를 신설해 락 안에서 대상 report를 materialize한 뒤 커밋하게 하고, `commit`이 rejected 이벤트에도 블롭 실재를 요구하게 한다. ② 결정표를 progress 범주를 1차 키로 하는 **상호배타 구조**로 재작성해 가림을 구조적으로 없앤다. ③ materialize가 확인된 부재와 일시적 fetch 실패를 가른다(전자만 삭제, 후자는 블로커).

**7차 개정본은 세 리뷰에서 판정이 갈렸다 — Codex "구현 착수 불가(치명 1)", Opus·Fable "조건부 착수 가능(치명 0)". 그러나 세 지적이 한 자리로 수렴했고, 그 자리는 7차 §7.4가 B-1을 고치려다 새로 연 접합부였다.** 7차 §7.4는 "락 안에서 materialize→사람 판단→progress.md 편집→커밋"을 한 임계구역이라 못박았는데, 실제 `commit.py`는 판단도 편집도 하지 않고 호출자가 이미 반영해 뒀다고 가정하므로(실측: `commit.py:20`·`254`) **사람의 판단·편집 시간이 flock 안에 들어갈 방법이 없다**(Codex C-1). 게다가 "상태가 바뀌는 각 task"는 사람의 편집 결과로만 정해지는데 그것을 편집 전에 materialize하려는 순서가 닭-달걀이고(Fable M-C), 커밋이 재자재화한 블롭이 사람이 리뷰한 블롭과 다를 수 있었다(리뷰와 커밋 사이 Leader가 새 report를 push하면 리뷰 안 한 블롭이 박제·수용됨). 또 rejected 블롭 게이트는 report '실재'만 검사해 '낡음'(작업트리에 잔존하는 낡은 파일)은 못 잡았고, 표의 "구간 재정렬 불변·가림 구조적 불가능"이라는 메타 주장이 report축 조건인 무효 행(행 7) 때문에 거짓이었다(Fable M-A). 실측 인용은 세 모델 표본 전부 정확했고(거짓 0건), 무너진 것은 또 사실들 *사이*의 접합부였다.

8차 개정본은 이 수렴점을 닫는다. ① §7.4를 **사람 판단은 락 밖, diff로 변경 task 확정, 재자재화한 블롭을 리뷰본과 대조(다르면 `CommitRejected`)**로 재서술한다. ② 표의 재정렬-불변 주장을 progress 분할 네 구간에 한정하고 무효 행(행 7)은 순서 의존임을 정정한다. ③ 죽은 "부재" 문면 통일, `post_mortem` "gone" 배선, materialize 원자적 쓰기, `progress status` 범위 제한.

**8차 개정본은 세 리뷰에서 다시 전원 "구현 착수 불가" 판정을 받았다 — 치명 하나가 만장일치였다.** 8차가 C-1(판단이 락에 못 들어감)과 닭-달걀은 실제로 닫았으나, 그 대가로 도입한 "리뷰본 대조"의 기준(작업트리 report 파일)이 **공유 가변 상태**였다. 리뷰(`progress status`)와 커밋 사이 판단 창은 락 밖인데, 그 사이 §7.3 주입 경로의 `observe()`가 지시 필요 여부와 무관하게 같은 작업트리 report를 재자재화하고(§5 'ok'는 작업트리를 덮는다), 무인자 `progress status` 재실행도 같은 파일을 갱신하며, §4.5는 이미 다중 주입자가 같은 작업트리 report를 경쟁적으로 덮는 동시성 모델을 전제한다. 그래서 사람이 R1을 리뷰하고 커밋 전에 파일이 R2로 덮이면 커밋이 R2==R2로 통과해 **리뷰 안 한 R2가 박제·수용된다** — 7차 C-1과 같은 결과를 다른 경로로 다시 연 것이다. 세 모델이 독립으로 같은 결론(치명)에 이르렀고, Opus·Fable은 "리뷰 기준을 덮일 수 있는 파일에서 사람이 명령줄로 옮기는 내용 해시로 바꾸라"는 같은 방향을 제시했다. 세 모델은 또 catch-all 행 18도 무효 행처럼 순서 의존이라 8차의 M-A 정정이 미완임을(Opus·Fable), 반려 구간 행 10이 `참`+`todo`·`in-progress`를 `None`으로 삼켜 재작업 중 정지가 침묵함을(Codex), §5 `rework_pushed -> bool`이 §4.1의 제3의 `None` 사유를 표현 못 함을(Fable) 짚었다. 실측 인용은 표본 전부 정확(거짓 0건).

9차 개정본은 이들을 닫는다. ① §7.4의 대조 기준을 작업트리 파일에서 **사람이 명령줄로 넘기는 attest 해시**로 옮긴다 — `progress status`가 리뷰한 블롭의 git object-id를 출력하고, `progress commit --reviewed <task>=<hash>`가 허브 블롭 id를 읽어(`probe_report_blob`, 읽기 전용) 그 해시와 대조하며(없거나 다르면 `CommitRejected`), 통과 블롭만 박제한다. 기준이 사람의 명령 인자이므로 판단 창의 작업트리 덮어쓰기와 무관하고, 리뷰 스킵도 잡히며, `ADR-0002`(무 저장소)와 충돌하지 않는다. ② catch-all 행 18을 "구간 밖 최후 고정" 행으로 명시하고 착수 구간을 행 14~17로 재분류(M-A 완성), 반려 구간 행 9의 report 집합을 `{blocked·needs-spec·todo·in-progress}`로 넓혀 재작업 중 정지를 블로커로 올리고 행 10을 `done`으로 좁힌다. ③ §5 `rework_pushed`를 `bool | None`로, `probe_report_blob`를 신설하고, 원자적 rename의 동일 디렉터리·`post_mortem`의 좀비 창 배치 등 경미를 정리한다.

**9차 개정본은 세 리뷰에서 판정이 갈렸다 — Codex "구현 착수 불가(치명 1)", Opus·Fable "조건부 착수 가능(치명 0)". 다만 Fable이 그 치명(C-3)을 git으로 실증했고, 셋 다 attest 메커니즘 자체는 새 치명 없이 옳다고 확인했다.** Fable은 attest의 세 핵심 주장(해시 기준의 덮어쓰기 무관성, probe fetch의 블롭 공급, cat-file의 ref 이동 무관성)을 이 컴퓨터에서 재현해 전부 성립함을 보이고 "9차는 이 이력에서 처음으로 직전 개정이 새 치명을 만들지 않은 회차"라 했다. **C-3**은 attest가 만든 게 아니라 5차 블롭 비교부터 잠복한 취약점이다 — `rework_pushed`의 바이트 비교가 "박제 블롭 = 허브 블롭"에 기대는데, `cat-file`로 쓴 블롭을 `milestone_commit`이 `git add`할 때 `core.autocrlf`가 CRLF report를 정규화하면(이 컴퓨터 `autocrlf=true`, parser는 CRLF 허용) 인덱스 블롭 ≠ 허브 블롭이 되어 `rework_pushed`가 영구 참, 반려가 미전달된다(B-1 증상). 세 모델은 또 무효 행(행 7)이 행없음 구간(행 12·13)과도 겹쳐 순서 의존 서술이 미완임(Opus·Fable), `progress status` 스코프의 모집합이 미명시라 `∅→rejected` 신규 반려가 막힘(Fable), §8.1 회귀 문구가 `materialize_report`라 §7.4 `cat-file`과 충돌함(Codex)을 짚었다. 실측 인용은 표본 전부 정확(거짓 0건).

10차 개정본은 이들을 닫는다. ① **C-3 봉인**: 저장소에 `docs/interim/report/*.md -text`를 `.gitattributes`로 두어 report 경로의 줄끝 정규화를 끄고(Leader clone·호스트 정본 양쪽 바이트 보존), §7.4 커밋 경로가 스테이징 후 `git rev-parse :<path>`(인덱스 블롭 id)를 attest 해시와 대조해 다르면 `CommitRejected`로 기계 등급 봉인한다. ② 무효 행(행 7)의 순서 제약을 "종결·보류 뒤, `report` 열이 `—`인 모든 구간(반려·행없음)과 착수 앞"으로 완성하고 `(plan=없음, 행없음, 무효)→블로커` 경계 결과를 명시(§4.1·§8.1). ③ `progress status` 모집합을 **작업본 행(신규 포함) ∪ 명시 인자**에 HEAD 종결 필터로 못박아 `∅→rejected`를 지원. ④ §8.1 문구를 `cat-file`로 정정, 행 8 표 라벨의 제3 `None` 사유, ls-remote 빈-출력 판정, rev-parse 종료 코드 규율, 배치 전-대조-후-쓰기, 군더더기 attest 거부 등 경미를 정리한다.

**10차 개정본은 세 리뷰에서 전원 "치명 0"으로 수렴했다 — 이 이력에서 처음이다.** Opus·Fable은 C-3 봉인을 각자 git으로 실증했고(`.gitattributes -text` 유무로 인덱스 블롭이 허브 바이트에 항등/재인코딩됨을 재현), Fable은 결정표를 2,268 조합 × 네 구간 24 순열로 브루트포스해 "행 7·18 외 순서 의존 없음"을 전수 확인했다. 셋 다 attest 메커니즘의 건전성(9차 실증)이 유지되고 10차 수정이 새 치명·상호 간섭을 만들지 않음을 확인했다. 남은 지적은 전부 문구 오독 여지·문서 정합 수준이었고, 그 정밀화(§7.4 인덱스 대조의 삽입 지점을 `milestone_commit` 내부 add↔commit 사이로, §5 계약에 attest 파라미터·`_unstage` 명시, `.gitattributes`를 `-text -filter -ident`로, §11 행 7 요약, §4.5 락 목록에 `progress status`)를 반영했다. **다음 관문은 Phase 5 훅 기반 판정기 재설계이고, 그 뒤 §8.3a 라이브 측정이며, 그 통과 전에는 어댑터 argv·강제 등급을 동결하지 않는다(§8.3a 주 재-시퀀싱).**

이 문서는 모든 주장에 **신뢰 등급**을 붙인다. 초안이 미실증을 확정처럼 서술한 것이 첫 리뷰의 주된 지적이었기 때문이다. 그러나 등급이 지켜졌다고 설계가 옳은 것은 아니다 — 2·3·4차 개정본은 실측 인용이 (거의) 정확했는데도 매번 착수 불가 판정을 받았다. **무너진 것은 사실이 아니라 그 사실 위에 세운 설계였고, 특히 확인하지 않은 사실이 있는 자리에서 무너졌다.**

| 등급 | 뜻 |
|---|---|
| **실측** | 이 저장소·이 컴퓨터에서 명령을 실행하거나 파일을 열어 확인했다 |
| **문서** | 공식 문서에서 확인했다 |
| **측정 대상** | 확인하지 못했다. §8 라이브 측정이 확정한다. 그 전에는 참으로 가정하지 않는다 |

---

## 1. 목표와 비목표

### 목표
- **LLM 역할 5종**(Maintainer·Leader·Developer·Reviewer·Tester)의 책임 경계·실행 위치·능력 등급·쓰기 권한·호출 인터페이스를 확정한다. Watcher는 여섯 번째 역할이지만 LLM이 아니므로 `RoleSpec`에 넣지 않는다(§2.4).
- **역할 선언의 단일 정의원**을 `WIP/axdt/roles/`에 두고, 플랫폼 어댑터가 각자의 형식으로 번역한다 — 정의는 복사되지 않는다.
- **Maintainer→Leader 주입 규약**을 확정한다: 언제 보내도 되는가(`IDLE` 한정), 무엇을 어떤 형식으로 보내는가, 상태별 분기, 그리고 **어떤 지시가 지금 필요한지를 관측에서 도출하는 법**(§4.1의 수렴 판정).
- **세션 재부착(attach)** 경로를 만든다. 이것 없이는 주입 규약이 실행될 수 없다(§2.5).
- 실 백엔드에 **`exit_code()`·`last_error()`를 구현**해 `ERROR`와 `STOPPED`를 실환경에서 구분한다. 이것 없이는 §4.1 상태표의 절반이 죽은 조항이다.
- Maintainer를 호스트에서 구동할 `TmuxHostBackend`를 만들고, `leader.py`의 `PLACEHOLDER`를 실제 세션 명령으로 대체한다.
- **배선 회귀 테스트**로 모듈 경계를 고정하고, **라이브 측정**으로 플랫폼 거동을 확정한다(§8).

### 비목표 (이 Phase에서 하지 않음)
- **Watcher 설계.** 별도 작업으로 분리했다(§2.4). 본 스펙은 하한선과 질문만 고정한다.
- **오케스트레이션 루프.** 누가 언제 어떤 task를 띄우고 언제 wave를 닫는지는 Phase 8이다. 본 Phase는 그 루프가 호출할 **부품과 규약**만 만든다.
- **메신저·Web.** `WAITING_INPUT`과 블로커는 로그로만 올린다. 사람에게 실제로 닿게 하는 것은 Phase 7이다.
- **역할별 Skill.** TODO의 "Maintainer Skill·Leader Skill" 항목은 본 Phase에서 만들지 않는다. 역할의 행동 규범은 시스템 프롬프트가 담고, 재사용 가능한 절차를 스킬로 뽑는 일은 프롬프트가 안정된 뒤에 한다.
- **plan 소유권 이동.** `docs/interim/plan/**`은 Maintainer 단독으로 유지한다(§2.6).
- **report 포맷 재설계.** 포맷·네이밍·상태 어휘·전이표는 Phase 1과 Phase 4가 확정했다. 본 Phase는 그것을 **소비**하고, `## 후속 제안` 절 하나만 추가한다(§2.6).
- **허브 게이트 강제.** 역할별 쓰기 권한을 rule로 명세하되, push 거부 강제는 Phase 3·6의 `pre-receive`가 담당한다.
- **컨테이너 egress 하드닝.** 본 설계의 안전성이 이에 의존하지 않도록 만든다(§4.1). Phase 3 백로그로 올린다.

---

## 2. 핵심 설계 결정

### 2.1 역할 위상 — 세 층

```
호스트 (컨테이너가 접근할 수 없는 층, ADR-0007)
  Maintainer   AgentRunner + TmuxHostBackend(신규) · 상시 tmux 세션 "axdt"
  Watcher      cron이 부르는 프로세스 (설계는 별도 작업 — §2.4)

컨테이너 (workspace당 1개, D3)
  Leader       AgentRunner + TmuxDockerBackend(기존)
    │
    └ Developer / Reviewer / Tester
                 Claude Code: 네이티브 sub-agent
                 Codex:       AXDT 래퍼 스크립트가 부르는 `codex exec` 서브프로세스
```

Maintainer가 호스트에 사는 것은 `rule-protected-paths`의 전제다 — 강제 지점(허브 게이트)은 컨테이너가 닿을 수 없는 곳에 있어야 하고, `docs/interim/progress.md`를 쓰는 유일한 주체가 그곳에 있어야 한다.

sub-agent가 서로 직접 통신하지 않는다는 것(`rule-subagent-no-direct-communication`)은 **플랫폼마다 근거가 다르다.** Claude Code에서는 플랫폼의 sub-agent 모델이 그것을 보장한다. Codex에는 네이티브 sub-agent가 없으므로, AXDT가 래퍼 스크립트로 프로세스 경계를 만들어 근사한다(§2.3·§4.3). 이 비대칭을 숨기지 않는다.

**Maintainer의 이름 규약** — Maintainer는 task가 아니므로 `naming.Identifier`(`w<n>.t<n>-<slug>`) 체계 밖이다(실측: `naming.py`의 정규식). tmux 창 이름은 상수 `axdt-maintainer`, 캡처 로그는 `config.capture_dir(root) / "maintainer.log"`로 고정한다.

### 2.2 역할 정의의 이원 분리 — 그리고 그 분리가 닿지 않는 회색지대

역할 정의에는 성질이 다른 두 가지가 섞여 있다.

- **책임 경계** — "Leader는 sub-agent 산출물을 중계한다", "Reviewer는 코드를 고치지 않는다". 바뀌면 시스템의 의미가 바뀐다. → `docs/sot/rule/` (변경 = 사용자 게이트 PR)
- **시스템 프롬프트 문구·능력 등급·모델 힌트** — 모델 교체·표현 개선으로 자주 바뀐다. → `WIP/axdt/roles/`

의존 방향은 한쪽이다. rule이 바뀌면 프롬프트가 따라 바뀌지만, 프롬프트를 다듬는다고 rule이 바뀌지는 않는다. 그래서 프롬프트는 자신이 근거한 rule의 id를 명시적으로 참조하고(`rule_refs`), 그 참조가 실재하는지 테스트가 검사한다(§8).

**회색지대가 하나 있다.** Developer는 `src/`를, Tester는 `test/`를 쓴다는 구분은 명백한 책임 경계인데, `rule-protected-paths`에서 `src/**`·`test/**`는 **"자유 — 보호 대상 아님"**이다(실측). 즉 이 구분은 어떤 rule에도 살지 않는다. 초안은 이를 덮어두고 "책임은 전부 rule에" 라고 썼다. 사실이 아니었다.

정직한 서술은 이렇다. **이 구분은 rule이 아니라 프롬프트 규범이며, 기계 강제 대상이 아니다.** 위반은 Leader의 리뷰가 잡는다. 신설할 `rule-role-responsibilities`가 이 구분을 명문화하면 계약 검사의 오라클이 생기므로(§8), 그 문서에 담는다 — 다만 그것은 강제가 아니라 **명세**다.

**`writable_paths`의 단일 명세는 신설할 `rule-role-responsibilities`의 표다.** 기계가 읽을 역할 id 열과 경로 glob 열을 갖고, 계약 테스트가 `WIP/axdt/roles/`의 값과 **등가(=)** 로 대조한다.

`rule-protected-paths`를 오라클로 삼지 않는다. 그 문서는 **경로 축** 규칙이다 — 무엇이 보호 대상이고 허브 게이트가 무엇을 막는가. 역할 축 뷰를 거기서 기계적으로 뒤집으려면 한국어 산문을 해석해야 하고, 그 해석 로직 자체가 세 번째 사본이 된다.

두 문서는 내용이 겹친다. **그 겹침은 파서가 아니라 사람이 사용자 게이트 PR에서 대조한다.** 기계 오라클을 둘로 두면 둘이 어긋날 때 어느 쪽이 옳은지 판정할 세 번째 오라클이 필요해진다. 규칙 간 우선순위(겹치면 더 제한적인 쪽이 이긴다)는 `rule-role-responsibilities`가 자기 문서에 명시한다.

### 2.3 플랫폼 능력과 그 번역

두 플랫폼의 능력이 다르다.

| | Claude Code | Codex | 등급 |
|---|---|---|---|
| 네이티브 sub-agent | 있음 — `--agents <json>` 또는 `.claude/agents/*.md` | **없음** | 문서 / 실측 |
| sub-agent 정의에 도구·모델을 실을 수 있는가 | **가능** — `tools`·`disallowedTools`·`model`·`permissionMode` (양쪽 형식 동일 스키마) | 해당 없음 | 문서 |
| 비대화형 1회 실행 | `claude -p <prompt>` | `codex exec <prompt>` | 실측 |
| 시스템 프롬프트 | `--append-system-prompt` | **전용 플래그 없음** (프롬프트 본문 선두에 붙인다) | 실측 |
| 권한 모드 | `--permission-mode` = `acceptEdits`·`auto`·`bypassPermissions`·`manual`·`dontAsk`·`plan` | `-s` = `read-only`·`workspace-write`·`danger-full-access` | 실측 (둘 다 `--help`) |
| 도구 **집합** 제한 | `--tools <목록>` — 내장 도구 집합 자체를 정한다. `""`이면 전부 없앤다 | (해당 없음) | 실측 |
| 도구 **승인** 제한 | `--allowedTools`(사전 승인) / `--disallowedTools`(거부), 범위 문법 `Bash(git diff *)` | `.rules` 실행 정책 — `prefix_rule(pattern=[...], decision="allow")` | 문서 / 실측 |
| 역할별 설정 묶음 | `--settings <file-or-json>` | `-p <profile>` → `$CODEX_HOME/<name>.config.toml`을 겹쳐 얹음 | 실측 |
| 모델 선택 | `--model` | `-m` | 실측 |
| 구조화 출력 | `--json-schema <schema>` (인라인 스키마) | `--output-schema <FILE>` (파일 경로) | 실측 — **비대칭이므로 어댑터가 흡수한다** |
| 세션 내 압축 | `/compact [지침]` — 초점 지침을 인자로 받는다 | **측정 대상** | 문서 |
| 컨텍스트 사용량 조회 | `/context` | **측정 대상** | 문서 |
| 이력에 남기지 않는 질의 | `/btw <질문>` | **측정 대상** | 문서 |
| 신뢰 다이얼로그 사전 승인 | `~/.claude.json` → `projects["<절대경로>"].hasTrustDialogAccepted: true` | `~/.codex/config.toml` → `[projects.'<경로>'] trust_level = "trusted"` | 문서 / 실측 |
| 자격증명 주입 | `ANTHROPIC_API_KEY` 환경변수 (`--bare`는 OAuth·키체인을 건너뛴다) | `~/.codex/auth.json` 또는 환경변수 | 문서 / 실측 |

#### 2.3.1 능력 등급 — 플랫폼 중립 어휘

Claude Code는 도구 이름 목록으로, Codex는 샌드박스 모드로 제한한다. `RoleSpec`에 도구 목록을 직접 담으면 Claude Code 종속이 된다. 그래서 역할은 **능력 등급**만 선언하고 어댑터가 번역한다.

| `Capability` | Claude Code 번역 | Codex 번역 | 쓰는 역할 |
|---|---|---|---|
| `READ_ONLY` | `--tools Read,Grep,Glob` (**도구 집합에서 제거**) + `--permission-mode plan` | `-s read-only` | Reviewer |
| `WRITE_WORKSPACE` | `--permission-mode dontAsk` + `--allowedTools` 범위 허용 + `--disallowedTools` | `-s workspace-write` + `.rules` | Leader, Developer, Tester |
| `HOST_CONTROL` | `--permission-mode dontAsk` + 호스트 명령 허용 목록 | `-s danger-full-access` + 승인 정책 (**측정 대상**, §8.3) | Maintainer |

`HOST_CONTROL`을 별도 등급으로 둔 이유는, Maintainer가 호스트에서 `docker`·`tmux`·`cron`을 부리기 때문이다. Codex의 `-s workspace-write`는 workspace 밖 쓰기를 막으므로 그 일을 표현할 수 없다.

**`--tools`와 `--allowedTools`는 층이 다르다.** 전자는 세션이 가진 도구 집합 자체를 정하고, 후자는 그중 어느 것을 묻지 않고 실행할지를 정한다. `READ_ONLY`를 `--tools`로 번역하면 쓰기 도구가 **존재하지 않으므로** 강제 등급이 게이트가 아니라 **기계**가 될 수 있다. 초안은 이 옵션을 놓치고 `--allowedTools`만 썼다. 어느 등급인지는 §8.3 측정이 확정한다.

**번역이 적용되는 층위를 밝힌다.** SESSION 역할(Maintainer·Leader)은 세션 argv에 번역이 실린다. SUBAGENT 역할(Developer·Reviewer·Tester)은 세션이 아니라 `--agents` JSON의 `tools`·`disallowedTools`·`permissionMode` 필드에 실린다. Reviewer는 언제나 SUBAGENT이므로 실제 적용점은 후자다.

**등급이 플랫폼 간 등가가 아님을 기록한다.** `READ_ONLY`는 Claude Code에서 "도구 자체가 없음"이지만 Codex에서는 "파일 쓰기만 막는 샌드박스"라 읽기 명령과 네트워크가 열려 있다. 이 비대칭은 `PLATFORM_MATRIX.md`에 행으로 남긴다.

#### 2.3.2 강제 등급 — 무엇이 실제로 막히는가

초안은 "capability는 도구를 쥐여주지 않으므로 Reviewer는 파일을 고칠 수 없다"고 단언하면서, 동시에 "그것이 실제로 막는지는 확인되지 않았다"고 적었다. 한 문서 안의 모순이었고, 그 단정이 SoT rule로 굳을 예정이었다.

모든 강제 주장에 등급을 붙인다.

| 등급 | 뜻 | 예 |
|---|---|---|
| **기계** | 도구가 존재하지 않거나 커널·샌드박스가 막는다. 프롬프트를 무시해도 못 한다 | Codex `-s read-only`의 파일 쓰기, Claude Code `--tools`에서 뺀 도구 |
| **게이트** | 시도하면 승인을 묻거나 거부된다. 우회하려면 사람이 승인해야 한다 | `--permission-mode dontAsk`에서 허용 목록 밖 명령 |
| **권고** | 프롬프트가 지시하고 **상위 주체의 리뷰가 잡는다.** 기계는 모른다 | Developer가 `test/`를 건드리지 않는 것 (Leader가 잡는다) |
| **부재** | 기계도, 게이트도, 잡을 상위 주체도 없다 | Maintainer의 쓰기 경로 |

**"부재"는 등급이 아니라 등급의 결여다.** 그럼에도 표에 이름을 준 이유는, 강제가 없는 자리를 "권고"로 적으면 잡아줄 누군가가 있는 것처럼 읽히기 때문이다. Maintainer는 신뢰 루트이며(`ADR-0007`) 그를 검토할 상위 주체가 없다. 사후 통제는 사용자 게이트뿐이다.

`--agents` JSON이 `tools`·`disallowedTools`·`permissionMode`를 지원함이 문서로 확인됐고, `--tools`가 도구 집합 자체를 제한함이 실측됐다. 그래서 Claude Code sub-agent의 능력 제한은 **게이트 등급으로 서술하되 기계 등급 승격 후보**로 둔다. 어느 쪽인지는 §8.3 측정이 확정한다.

#### 2.3.3 sub-agent 물질화

- **Claude Code**: `RoleSpec`들을 `--agents <json>` argv로 변환한다. 네이티브 sub-agent로 호출되므로 격리는 플랫폼이 보장한다.
- **Codex**: 네이티브 sub-agent가 없다. AXDT가 **래퍼 스크립트를 컨테이너 이미지에 심는다.**

```
/usr/local/bin/axdt-subagent <role> "<지시>"
  └ AXDT가 조립:  codex exec -p <role> -s <mode> -m <model> "$(cat $CODEX_HOME/roles/<role>.md)

<지시>"
```

역할 프롬프트와 지시를 **한 인자로 이어 붙인다.** 초안 스케치는 역할 파일을 stdin으로 넘기면서 `<지시>`를 버렸다. `codex exec`의 위치 인자와 stdin 리다이렉트를 함께 쓸 때의 거동은 확인되지 않았으므로(측정 대상) 위치 인자 하나로 합친다.

**물질화 위치는 `$CODEX_HOME` 아래이지 workspace가 아니다.** `-p <profile>`은 `$CODEX_HOME/<name>.config.toml`을 겹쳐 얹으므로(실측), 프로파일을 workspace에 두면 찾지 못한다. 컨테이너에서 `$CODEX_HOME`은 `HOME`(`/tmp/axdt-home`) 아래다. 역할 프로파일·프롬프트·실행 정책은 **이미지 빌드 시점에 굽거나 컨테이너 기동 시 주입**한다.

workspace에 두지 않는 두 번째 이유가 있다. workspace는 git clone이므로, 역할 파일을 거기 쓰면 작업 트리를 오염시키고 Leader가 실수로 커밋할 수 있다.

**명령줄을 조립하는 주체가 누구인가가 강제 등급을 가른다.** Leader LLM이 직접 `codex exec -s read-only ...`를 타이핑한다면 그것은 권고 등급이다 — 옵션을 빼먹으면 그만이다. 래퍼 스크립트를 심고 Leader에게 `Bash(axdt-subagent *)`만 허용하면, 명령줄의 소유권이 AXDT로 넘어와 **게이트 등급**이 된다. 후자를 택한다.

어느 어댑터도 역할 텍스트를 자기 안에 갖지 않는다. 어댑터는 변환기다.

### 2.4 Watcher — 본 스펙에서 확정하지 않는다

초안은 Watcher를 "판단은 LLM, 실행은 코드"로 나누고 그것이 안전을 준다고 주장했다. **세 리뷰가 모두 이 주장을 거짓으로 판정했다.** `restart`가 LLM의 출력 어휘에 있는 한 코드는 죽이라면 죽인다. 게다가 초안은 "응답 해석 실패도 restart로 간주한다"고 써서, 형식이 한 번 어긋나면 멀쩡한 Maintainer가 죽고 ADR-0001이 보존하려던 살아 있는 맥락이 사라지게 만들었다.

**Watcher 설계를 Phase 2 안의 독립 작업으로 분리한다.** 본 스펙은 두 가지만 고정한다.

#### 하한선 (이 작업이 어겨서는 안 되는 것)
1. **재기동 결정은 LLM이 내리지 않는다.** 코드가 프로세스의 실제 죽음(`is_alive() == False`, 그리고 `exit_code()`)을 관측했을 때만 재기동한다.
2. **화면 마커에서 유래한 `ERROR`는 재기동 근거가 아니다.** `poll_state()`의 `ERROR`는 transcript에서 문자열을 찾아 나온다 — Claude Code는 `"Error:"`·`"fatal:"`(실측: `adapters/claude_code.py`의 `_ERROR_MARKERS`), Codex는 `"stream error:"`(실측: `adapters/codex.py`, 마커는 provisional). 테스트 실패 출력 한 줄이면 멀쩡히 일하는 세션이 `ERROR`로 보인다. 그것으로 죽이면 초안 Watcher를 기각한 사유가 하한선 문면으로 되살아난다.
3. **응답 해석 실패는 재기동이 아니라 이번 회차 건너뛰기다.** 다음 cron 주기에 다시 시도한다.

추가로, 초안이 폐기한 경로 하나를 명시한다. **"압축 명령이 없는 플랫폼이면 재기동으로 승격"을 하지 않는다.** 그러면 바쁜 Maintainer가 주기마다 죽는다. 압축할 수 없으면 임계 초과를 블로커로 사람에게 올린다.

#### 유력한 후보 흐름

조사 중 정정된 오판 하나가 후보 흐름을 연다. 초안은 "대화형 명령이라 외부 프로세스가 결과를 받을 수 없다"고 적었는데, 그것은 일반적인 CLI를 가정한 오판이었다. **`send-keys`로 문자를 밀어넣고 캡처 로그로 화면을 읽는 경로는 실재한다** — 이미 그 방식으로 상태 마커를 판정한다(실측).

다만 "문자를 전달할 수 있다"와 "그 슬래시 명령이 안정적으로 실행되고 응답을 파싱할 수 있다"는 다른 주장이다. 후자는 **측정 대상**이고(§8.3), Watcher 별도 작업의 입력이다.

```
Watcher(코드) → /context 주입 → 캡처 로그에서 실제 사용량 파싱   (임계 판정, 결정적)
              → /btw 진행 중인 판단과 대기 중인 것을 요약해줘      (이력 오염 없이 인터뷰)
              → /compact <그 결정과 미승격 report 대기를 보존하라> (Maintainer가 스스로 요약)
```

`/btw`는 **읽되 쓰지 않는다**(문서). 답하려면 현재 맥락을 읽으므로 Maintainer가 무엇을 하던 중인지 알고, 대화 이력에는 누적되지 않으므로 물어본 대가로 맥락이 더 차오르지 않는다. `/compact`는 **초점 지침을 인자로 받는다**(문서).

이 흐름을 택하면 **무엇을 남길지 판단하는 주체가 Maintainer 자신**이 되고, Watcher의 LLM 단계가 사라진다.

**다만 프롬프트 주입 위험이 사라진다고 말할 수는 없다.** 사라지는 것은 하나뿐이다 — 외부 Watcher LLM이 조작당해 세션을 죽이는 표면. 컨테이너의 Leader가 report에 심은 적대적 텍스트는 Maintainer가 정상 업무로 그 report를 읽는 순간 **이미 Maintainer 컨텍스트 안에 있고**, `/compact <이 결정을 보존하라>`는 바로 그 내용을 요약에 넣으라고 지시한다. 자기 요약도 주입면이다. 위험은 제거된 것이 아니라 **외부 LLM 경유 경로가 닫히고 자기 요약 오염이 잔존하는** 상태로 좁혀졌다.

`/btw` 답변의 용도도 아직 정해지지 않았다. 그 답을 코드가 **쓰면**(예: 압축 지침에 반영하면) 위 주입 경로가 되살아나고, **쓰지 않으면** 그 단계가 불필요하다. 별도 작업이 이를 정해야 한다.

덤으로, 초안이 임계 지표로 삼았던 캡처 로그 크기의 결함은 해소된다. 캡처 로그는 덧붙이기만 하므로 압축해도 줄지 않아 한 번 임계를 넘으면 영원히 넘은 상태가 된다. `/context`가 재는 것은 실제 컨텍스트 사용량이므로 압축 후 정직하게 줄어든다.

#### 본 Phase가 만드는 최소 Watcher

`cron.py`의 `cron.install(interval, watcher_cmd, ...)`는 `watcher_cmd`를 필수 인자로 받는다(실측). Watcher 전체를 미루면 cron 배선이 완성되지 않고, ADR-0001이 상시 Maintainer를 정당화한 근거("context 비대화는 Watcher가 관리")가 Phase 2 산출물 안에서 아무에게도 할당되지 않는다.

그래서 **결정적 부분만 본 Phase에서 만든다.** `axdt watcher tick`은 세션 생존을 확인하고, 죽었으면 사후 진단(§2.5 `post_mortem`)으로 종료 코드를 얻어 블로커로 기록한다. LLM 호출도, 압축도, 재기동도 하지 않는다. context 관리는 별도 작업이 이 진입점을 채운다.

#### 그 작업이 답해야 할 질문
- `/context` 출력을 ANSI 제어문자가 섞인 캡처 로그에서 안정적으로 파싱할 수 있는가 (**측정 대상**)
- Codex에 `/btw`·`/context`·`/compact` 대응 명령이 있는가. 없으면 **그 플랫폼의 Maintainer는 어떻게 오래 사는가** (**측정 대상**)
- `/btw` 답변을 코드가 쓰는가 쓰지 않는가. 쓴다면 자기 요약 오염을 어떻게 완화하는가
- 압축 지침 문구를 무엇으로 고정하는가. `/compact`가 실패하면(대화가 과대한 경우 등) 어떻게 관측하고 올리는가
- Watcher가 Maintainer 세션에 주입할 때도 `IDLE` 게이트(§4.1)를 통과해야 한다. Maintainer가 `progress.md`를 커밋하는 도중에는 어떻게 비켜서는가
- 바쁜 Maintainer는 계속 `BUSY`라 매번 건너뛰는데, 정작 그런 Maintainer의 컨텍스트가 가장 빨리 찬다. 연속 N회 건너뛰면 무엇을 하는가(기아 상한)
- Watcher가 어느 플랫폼 어댑터를 쓰는지 어떻게 아는가 (cron 항목에 인자로 고정하면 새 저장소가 필요 없다)
- 캡처 로그에 담길 수 있는 민감 정보가 외부 호출로 나가는 경계

Watcher는 `docs/` 아래 어떤 파일도 쓰지 않는다. `progress.md`는 Maintainer 단독이고(`rule-progress-single-writer`), report는 Leader의 자기보고 파일이므로, Watcher가 합법적으로 쓸 경로가 없다. 진단은 stdout으로 내보내고 cron 로그가 받는다(§6).

### 2.5 실행 substrate — 재부착과 상태 판정

초안에는 두 개의 구멍이 있었다. 둘 다 "스펙대로 만들면 작동하지 않는다"는 종류다.

#### 재부착(attach)이 없었다

`inject(runner, ...)`는 살아 있는 세션에 붙은 runner 인스턴스를 전제한다. 그런데 Maintainer가 Leader에게 지시를 보내는 것도, Watcher가 cron에서 깨어나는 것도 **매번 새 프로세스**다. 현행 코드에서는(실측):

- `TmuxDockerBackend._state`는 인메모리 필드라 새 프로세스에서는 항상 `NOT_STARTED`이고, `send_text()`는 그 상태에서 `NotStarted`를 던진다.
- `start()`는 창·컨테이너가 이미 있으면 `AlreadyStarted`로 거부한다.

붙을 방법이 없었다. §6의 CLI 목록에 `leader send`가 없던 것이 그 증상이다.

**이것은 CLI를 재개하는 문제가 아니라 tmux 창에 다시 붙는 문제다.** Claude Code의 `--resume`은 새 프로세스로 대화를 이어가는 기능이라 여기 해당하지 않는다(문서). 우리는 CLI가 아니라 터미널 창에 키를 보낸다.

`SessionBackend`에 `attach()` 생성 경로를 추가한다. tmux 창과 컨테이너의 존재를 **라이브 조회**로 확인해(`tmux.resolve_window`·`container.is_running` — 둘 다 이미 있다) 실행 중 상태로 구성한다. **새 상태 저장소가 생기지 않으므로 ADR-0002와 충돌하지 않는다.**

**`attach()`는 창과 컨테이너가 둘 다 살아 있을 때만 성공한다.** 반쪽 상태(창만·컨테이너만)에서는 `NotStarted`를 던지고 호출자를 `down()`으로 유도한다.

판정을 인스턴스 `status()`에 맡길 수 없다. 그 메서드는 `self._state == "NOT_STARTED" and self._win is None`이면 라이브 조회 전에 `NOT_STARTED`를 반환하는데(실측: `infra/backend.py`), 새 프로세스에서 갓 만든 인스턴스가 정확히 그 조건이다. 즉 attach 시나리오에서는 인용된 `WINDOW_ONLY`·`CONTAINER_ONLY` 분기에 **도달하지 못한다.** `attach()`는 `resolve_window`와 `container.is_running`을 직접 부르고, 성공 시 `_win`·`_state`를 실행 중으로 세팅한 인스턴스를 만든다.

그런데 여기에 함정이 있다. CLI가 죽으면 `docker run -it`이 끝나 tmux 창이 닫히고, `--rm`이 없으므로 컨테이너는 "종료됨" 상태로 잔존한다(실측: `container.run_args`). 이때 `is_alive()`가 거짓이므로 **attach가 실패한다.** 그러나 `ERROR`와 `STOPPED`를 가르는 `poll_state()`는 attach된 runner를 전제한다 — **죽은 세션이야말로 종료 코드가 필요한 순간인데, 죽은 세션에는 붙을 수 없다.**

그래서 사후 진단 경로를 따로 둔다.

```python
TmuxDockerBackend.post_mortem(i, root) -> tuple[int | None, str | None]   # (exit_code, reason)
```

**classmethod다.** `attach()`가 실패한 뒤 부르는 함수이므로 붙은 인스턴스가 존재하지 않는다.

**`post_mortem`은 컨테이너가 정말 죽었는지 먼저 확인한다.** `attach()`는 세 종류의 비-정상 상태를 모두 거부하는데, 의미가 다르다.

- **창 없음 + 컨테이너 종료·잔존** — CLI가 죽은 정상 사망이다(`--rm`이 없어 종료 컨테이너가 남는다, 실측: `container.run_args`). `docker inspect -f '{{.State.ExitCode}}'`로 종료 코드를 읽어 `(exit_code, reason)`을 돌려준다. 재기동해도 된다.
- **창 없음 + 컨테이너 실행 중** — tmux 서버 재시작이나 `stop()` 도중 크래시가 만드는 상태다(`stop()`은 `kill_window` → `container.stop` → `container.rm`이 원자적이지 않다, 실측: `infra/backend.py`). 컨테이너는 살아 있다. 여기서 `docker inspect`의 `ExitCode`는 실행 중 컨테이너에 `0`을 돌려주므로(문서), 그대로 쓰면 **살아 있는 Leader를 "정상 종료"로 오판**하고 §7.2 재기동이 산 컨테이너를 죽여 §2.4 하한선을 자기 메커니즘으로 뚫는다. 그래서 `post_mortem`은 `State.Running`을 함께 보고, **실행 중이면 종료 코드 대신 `(None, "half-state: container alive")`를 돌려준다.** 호출자는 이것을 사망이 아니라 이상으로 취급해 재기동하지 않고 **블로커**로 올린다.
- **창·컨테이너 모두 없음** — 이미 `stop()`이 완주해 정리된 상태다(또는 `rm` 후). 조회할 컨테이너가 없으므로 종료 코드도 없다. `(None, "gone")`을 돌려준다 — 예기치 못한 죽음이 아니라 정상 정리이므로 재기동하지 않고, 호출자(tick)는 정리됨으로 보고한다. 재기동이 필요한 상황이면 workspace도 없을 수 있어 `restart`의 `up(reuse_workspace=True)`가 `FileNotFoundError`로 정직하게 멈춘다(§4.5).
- **창 있음 + 컨테이너 부재** — 컨테이너만 `rm`되고 좀비 tmux 창이 남은 상태다(드묾 — `stop()`이 `kill_window`를 `container.rm`보다 먼저 하므로 정상 경로에선 안 생긴다). 종료 코드를 얻을 컨테이너가 없으니 `(None, "gone")`으로 묶어 재기동하지 않는다 — 다음 `up`이 좀비 창에 걸려 `AlreadyStarted`로 시끄럽게 실패하므로(실측: `infra/backend.py`) 조용히 되살아나지 않고 사람이 창을 걷어내게 된다. `"gone"`이 두 배치(정상 정리·좀비 창)를 겸함을 명시한다.

§2.4의 Watcher 하한선("코드가 세션 사망을 관측했을 때만 재기동")은 `attach` 성공 시 `poll_state()`로, 실패 시 `post_mortem()`으로 판정하되, `post_mortem`이 "실행 중"을 돌려주면 재기동하지 않는다.

캡처 로그 오프셋은 파일 끝으로 두되, 상태 마커 판정을 위해 마지막 `TAIL_WINDOW` 바이트를 읽어 transcript를 시드한다. **마지막 마커가 그 창 밖이면 `poll_state()`가 직전 상태를 오검출할 수 있다.** attach 직후의 첫 판정은 신뢰하지 않고, 주입 전에 `wait_until_idle(timeout)`으로 상태를 다시 확인한다.

#### `ERROR`와 `STOPPED`를 구분할 수 없었다

`AgentRunner.poll_state()`는 `backend.exit_code()`와 `backend.last_error()`로 두 상태를 가른다(실측: `runner.py`). 그런데 `agent_runner.SessionBackend` ABC는 이 둘을 요구하는 반면 `infra/backend.py`의 인라인 ABC에는 없고, `TmuxDockerBackend`도 구현하지 않는다. 즉 **§4.1 상태표의 `ERROR`·`STOPPED` 분기가 실환경에 존재하지 않았다.**

초안 §9는 이 통합을 "계약을 한 곳으로 모은다" 한 줄로 처리했다. 실제 작업은 셋이다.

1. `TmuxDockerBackend`·`TmuxHostBackend`에 `exit_code()`·`last_error()`를 구현한다. 컨테이너 종료 코드는 `docker inspect -f '{{.State.ExitCode}}'`로 얻는다. `stop()`이 `container.rm`을 부른 뒤에는 조회가 실패하므로, **`stop()` 직전에 종료 코드를 캡처해 보관**한다.
2. **오류 의미론을 세 갈래로 가른다.** `agent_runner.SessionBackend`의 계약은 "기동 실패를 raise하지 말고 `is_alive()==False` + `last_error()`로 표면화"인데(실측), `TmuxDockerBackend.start()`는 `AlreadyStarted`·`FileNotFoundError`를 던진다. 초안은 두 갈래로만 갈랐으나 실제로는 셋이다.
   - **호출자의 프로그래밍 오류** → raise (이미 시작함, 작업본 없음)
   - **세션의 런타임 실패** → 표면화 (`is_alive()==False` + `last_error()`)
   - **환경 실패** → 표면화 (`hub.serve`의 `RuntimeError`, `tmux.new_window`의 `FileExistsError`, `proc.run`의 `CalledProcessError`. 호출자 잘못도 세션 잘못도 아니지만 기동이 안 된 것은 같다)

   `agent_runner/backend.py`의 ABC docstring("NOT raised")도 이 분류에 맞춰 갱신한다.
3. `infra/backend.py`의 인라인 ABC를 지우고 `agent_runner`의 ABC를 import한다. 그 전에 1·2가 끝나야 한다 — 순서를 바꾸면 `TmuxDockerBackend`가 추상 메서드 미구현으로 인스턴스화되지 않는다.

#### `TmuxHostBackend`

`TmuxDockerBackend`는 tmux 윈도우 안에서 `docker run`을 띄운다. Maintainer는 호스트에 살아야 하므로 컨테이너 없이 tmux 윈도우에서 직접 CLI를 띄우는 구현이 필요하다. 계약이 같으므로 `AgentRunner`가 그대로 재사용된다. 캡처는 `TmuxDockerBackend`와 같은 `pipe-pane` 증분 방식을 쓴다.

두 가지가 도커 백엔드와 다르다.

- **창 조회.** `tmux.resolve_window(i)`는 `naming.Identifier`를 받는데(실측) Maintainer는 그 체계 밖이다(§2.1). `tmux`에 이름으로 창을 찾는 공개 함수를 추가한다(현재는 private `_find_window_by_name`).
- **종료 코드.** 호스트 tmux 창은 CLI가 죽으면 창째 닫혀 종료 코드가 사라진다. `remain-on-exit`을 켜고 `#{pane_dead_status}`로 읽는다 — **측정 대상**이다. 이 방법이 통하지 않으면 `TmuxHostBackend`는 `ERROR`와 `STOPPED`를 구분하지 않는다고 정직하게 좁힌다.

### 2.6 plan 소유는 옮기지 않는다 — 다만 제안 경로는 연다

`docs/interim/plan/**`은 Maintainer 단독 쓰기다(`rule-protected-paths`). 그대로 둔다.

**근거는 자가수정 방지 하나다.** `rule-protected-paths`는 "Leader가 자기 plan/task의 DoD·의존을 넓혀 자가수정"을 위반 예시로 명시한다(실측). 완료 조건을 스스로 느슨하게 만드는 경로를 열지 않는다.

초안은 여기에 "Leader가 자기 task를 짤 시점에는 아직 Leader가 없다"는 부트스트랩 논거를 덧붙였다. 이는 **최초 task에 대해서만 참인 좁은 명제**이므로 근거로 삼지 않는다 — 시점 T에 존재하는 Leader가 미래 task의 plan을 쓰는 것은 부트스트랩 문제가 아니다.

**실질적 공백이 하나 있었다.** 진행 중 발견한 후속 작업을 Leader가 제안할 자리가 report 양식에 없다. `## 블로커`는 의존이고 `## 사양 변경 요청`은 SoT 변경이라, "새 task가 필요하다"는 발견을 올릴 곳이 없다. `docs/interim/report/_TEMPLATE.md`에 `## 후속 제안` 절을 추가한다. **제안은 Leader가, 분해와 배정은 Maintainer가** 한다 — report→progress가 쓰는 것과 같은 "주장 → 수용" 패턴이다.

**ADR 기록도 같은 이유로 Maintainer가 소유한다.** 초안은 ADR 본문(`docs/interim/ADR/*.md`)을 Leader 쓰기 경로에 뒀으나, plan과 같은 사유 — 자가수정 방지, 그리고 여러 Leader가 서로 어긋나는 설계 결정을 조율 없이 기록하는 것을 막는 것 — 로 작성 권한을 Maintainer로 옮긴다. Leader는 설계 결정을 report로 제안하고, Maintainer가 `docs/interim/ADR/`에 기록한다. 폴더의 `README`·`_TEMPLATE`은 이미 Maintainer 소유다(§3·`rule-role-responsibilities` 각주 ⁵).

---

## 3. 역할 명세

`kind`는 실행 형태다. `SESSION`(장기 대화형 세션)과 `SUBAGENT`(상위 세션 안의 sub-agent) 둘뿐이다. Watcher의 실행 형태는 별도 작업이 정한다(§2.4) — 유력 후보 흐름에서는 LLM 호출이 없으므로, 1회성 비대화형 실행이라는 형태를 미리 계약에 넣지 않는다.

**`ROLES`는 다섯 종을 담는다.** Watcher는 `RoleSpec` 밖이다 — 실행 형태도 시스템 프롬프트 유무도 확정되지 않았고(§2.4), 유력 후보 흐름에서는 LLM이 없어 능력 등급을 번역할 대상조차 없다. 아래 표의 Watcher 행은 그 작업이 지켜야 할 **하한 권고**이지 확정된 선언이 아니다.

| 역할 | kind | 실행 위치 | substrate | capability | 쓰기 경로 | 강제 등급 |
|---|---|---|---|---|---|---|
| **Maintainer** | SESSION | 호스트 | `TmuxHostBackend` | `HOST_CONTROL` | `docs/interim/progress.md`, `docs/interim/plan/**`, `docs/interim/sot-readiness-review.md`, `docs/interim/**/README.md`·`_TEMPLATE.md`, `docs/interim/ADR/*.md` 본문 | **부재** (아래 참고) |
| **Leader** | SESSION | 컨테이너 | `TmuxDockerBackend` | `WRITE_WORKSPACE` | `src/**`, `test/**`, 자기 task의 `docs/interim/report/<task>.md` | 게이트 + 허브 경로 강제 |
| **Developer** | SUBAGENT | Leader 세션 | 플랫폼 / 래퍼 | `WRITE_WORKSPACE` | `src/**`, `test/**` | 권고 (역할 간 구분) |
| **Reviewer** | SUBAGENT | Leader 세션 | 플랫폼 / 래퍼 | `READ_ONLY` | 없음 (리뷰 결과를 Leader에 반환) | 측정 대상 (예상: 게이트, 측정 후 기계 승격 후보 — §8.3a-7·§11) |
| **Tester** | SUBAGENT | Leader 세션 | 플랫폼 / 래퍼 | `WRITE_WORKSPACE` | `test/**` | 권고 (역할 간 구분) |
| *(Watcher)* | *별도 작업* | 호스트 | *별도 작업(§2.4)* | *`READ_ONLY` 하한 권고* | *없음* | *별도 작업* |

**Maintainer의 쓰기 권한에는 강제 지점이 없다.** Maintainer는 호스트의 정본 작업본에 직접 쓰고 허브 push를 거치지 않으므로(`ADR-0007`: main은 push가 아니라 fetch/update-ref로 갱신된다), 경로 강제도 허브 게이트도 적용되지 않는다. 그를 검토할 상위 주체도 없다. 오작동한 Maintainer가 `docs/sot/**`를 사용자 게이트 없이 고치는 것을 막는 장치는 없으며, 사후 통제는 사용자 게이트뿐이다. `ADR-0007`의 신뢰 루트 모델과 정합하지만, "권고"라고 적으면 잡아줄 누군가가 있는 것처럼 읽히므로 **부재**로 표기한다.

**강제 등급 열이 가리키는 대상이 행마다 다르다.** Reviewer 행은 *능력 등급*의 강제를 말하고, Developer·Tester 행은 *역할 간 경로 구분*의 강제를 말한다. 두 축을 한 열에 담았으므로 읽을 때 주의한다. 능력 등급의 강제는 sub-agent에서 현재 게이트로 서술하되 그 확정은 측정 대상이고(Reviewer는 §8.3a 항목 7 — 측정 후 기계 승격 후보, Phase 5 이후 §11), 역할 간 경로 구분은 모두 권고다.

**역할 간 구분(Developer는 주로 `src/**`, Tester는 `test/**`)은 권고다.** `rule-protected-paths`가 두 경로를 "자유"로 두므로 허브 게이트가 모르고, 능력 등급도 둘을 가르지 않는다. 프롬프트가 지시하고 Leader의 리뷰가 잡는다(§2.2).

각 역할의 시스템 프롬프트는 자신의 `rule_refs`에 있는 rule의 규칙문을 인용하며, 인용이 아닌 창작 규범을 담지 않는다.

---

## 4. 통신 프로토콜

### 4.1 Maintainer → Leader 주입 규약

`ADR-0003`은 하향 통신이 tmux `send-keys`임을 정했다. 본 절은 **언제·무엇을·어떻게** 보내는가를 정한다.

#### 주입은 메시지 배달이 아니라 상태 수렴이다

2차 개정본은 "같은 메시지를 두 번 배달하지 않는다"를 목표로 삼고, tmux 캡처 로그에서 메시지 토큰을 찾아 중복을 막으려 했다. **세 리뷰가 그 접근을 함께 무너뜨렸다.** 실패는 세 겹이었다.

- **크래시 창이 닫히지 않았다.** 토큰이 로그에 닿은 뒤 제출 전에 주입자가 죽으면, 재기동한 주입자는 토큰을 보고 `SKIPPED`한다. 지시는 제출된 적이 없는데 영원히 다시 보내지지 않는다. 2차 개정본이 "닫았다"고 주장한 바로 그 유실이다. 죽은 프로세스는 `UNCONFIRMED`를 반환할 수 없다.
- **오라클을 피검증자가 쓴다.** 캡처 로그는 Leader 터미널의 출력이다. 토큰 산식과 메시지 형식은 결정적이고 Leader의 clone 안에 있다. 오염된 Leader가 미래 토큰을 미리 출력해 두면 Maintainer의 진짜 지시가 `SKIPPED`된다.
- **보존 의무가 곧 이벤트 로그다.** "세션 생존 중 회전·절단하지 않는다"고 못박는 순간, 상태 판정용 버퍼였던 파일에 append-only 보존 의무가 생긴다. `ADR-0002`가 대안 C로 기각한 성질이 이름만 바꿔 돌아온다. `read_increment`가 매 폴마다 파일 전체를 읽으므로(실측: `tmux.py`의 `p.read_bytes()`) 비용도 실재한다.

**메시지 단위 멱등을 버린다.** 대신 이렇게 묻는다 — *이 지시가 지금도 필요한가?*

Maintainer는 "내가 이 지시를 보냈던가"를 알 필요가 없다. 알아야 할 것은 "Leader가 해야 할 일을 하고 있는가"이고, 그것은 **이미 권위 있는 상태로 관측 가능하다.** plan 파일이 있고, report가 없고, Leader가 `IDLE`이면 그 task는 착수되지 않았다. 이때 배정을 (다시) 보내는 것은 중복이 아니라 **옳은 행동**이다. 최악의 결과는 Leader가 plan을 다시 읽는 것이다.

이것이 수렴 루프다. 배달을 세지 않고 상태를 맞춘다.

**관측(`Observation`)은 다섯 곳의 라이브 조회로 만든다.**

| 항목 | 출처 |
|---|---|
| `plan_exists` | `docs/interim/plan/task/<task>.md` 존재 여부 (파일시스템) |
| `progress` | `progress.md` 행의 status. **권위값**. 행이 없으면 `None` |
| `report`·`report_invalid` | canonical report의 status. 부재·파손이면 `None`·`True` |
| `rework_pushed` | 지금 report가 반려 커밋에 박제된 report와 **다른가** (git 블롭 비교) |
| `session` | `runner.poll_state()` |

가운데 셋은 Phase 4의 `recover.reconstruct(progress_path, report_dir)`가 이미 만든다(실측) — `plan_exists`와 `rework_pushed`만 새로 본다. `TaskState`에 plan 존재 항목이 없고 `reconstruct`가 `progress.md` 행만 순회하기 때문이다(실측). **새 저장소도 새 파싱도 없다.** `ADR-0002`가 요구한 "존재 여부는 라이브 조회로 도출"을 문면과 의미론 양쪽에서 지킨다.

#### report를 관측하려면 자재화(materialize)해야 한다

**`git fetch`만으로는 아무것도 보이지 않고, 잘못 부르면 force-push를 버린다.**

`recover._read_canonical_report`는 `report_dir / f"{task}.md"`를 **디스크에서 읽는다**(실측). 그런데 Leader의 report는 컨테이너 안 clone에서 쓰여 허브의 task 브랜치 `refs/heads/w<n>.t<n>-<slug>`로 push되고(`ADR-0006`·`0007`), 호스트는 그것을 원격 추적 ref로만 받는다. **`fetch`는 작업트리도 `main`도 건드리지 않는다.** 그대로 두면 Leader가 report를 push해도 Maintainer는 여전히 낡은(또는 없는) 파일을 읽고, 완료된 task에 배정을 다시 밀어넣는다.

여기에 두 함정이 더 있다.

- **강제 갱신 표식 `+`.** 반려받은 Leader의 자연스러운 재작업은 report 커밋을 amend해 force-push하는 것이다. 허브는 그것을 받는다 — pre-receive 게이트는 task-브랜치 allowlist와 삭제만 막고 `receive.denyNonFastForwards`를 켜지 않는다(실측: `hub.py`가 `denyDeletes`만 설정). 그런데 refspec에 `+`가 없으면 호스트 fetch가 non-fast-forward를 **거부**해 그 갱신을 버리고, 관측이 옛 블롭에 영원히 묶인다. refspec 앞에 `+`를 붙인다.
- **명명 원격이 아니라 허브 경로.** `hub` 원격은 workspace clone에만 있고(실측: `workspace.py`가 clone 뒤 `origin`을 `hub`로 rename) 호스트 정본 저장소에는 없다. 그래서 명명 원격 대신 허브 bare 저장소 경로에서 직접 fetch한다(`config`가 아는 경로).

`observe()`가 관측 전에 두 걸음을 밟는다. `HUB`는 허브 bare 저장소 경로, `BR`은 task 브랜치다.

```
git fetch <HUB> '+refs/heads/<BR>:refs/remotes/hub/<BR>'
git cat-file -e refs/remotes/hub/<BR>:docs/interim/report/<task>.md   # 트리에 경로가 있는가
git show    refs/remotes/hub/<BR>:docs/interim/report/<task>.md  >  <임시파일>
mv <임시파일>  docs/interim/report/<task>.md                        # show 성공 시에만 원자적 교체
```

필요한 task 하나의 브랜치만 가져온다. **merge가 아니라 블롭 복사다.** 각 report 파일의 소유자는 그 task의 Leader 하나뿐이고 Maintainer는 report를 편집하지 않으므로(`rule-protected-paths`), 충돌이 없다. **대상 경로에 직접 `>` 리다이렉트하지 않는다** — show가 실패해도 리다이렉트가 실행 전에 대상을 0바이트로 절단해 "관측 실패면 작업트리 불변"이라는 아래 계약을 깨기 때문이다(실측: 이 컴퓨터에서 실패하는 `git show > 파일`이 대상을 0바이트로 절단함을 재현). 임시 파일에 쓰고 show 성공 시에만 원자적 rename으로 대상에 놓는다.

**실패를 둘로 가른다 — 확인된 부재와 관측 실패.** `fetch`·`show`는 브랜치·경로가 진짜 없을 때도, 허브 접근이 일시적으로 실패할 때(네트워크·데몬 경합·IO)도 비영으로 끝난다 — 실측: 부재 브랜치 fetch도 일시 실패도 exit 128이라 종료 코드만으로는 못 가른다. **`show`의 exit 128도 경로 부재와 일시 실패를 겸하므로 그것으로 가르지 않는다.** 뭉개서 둘 다 "부재"로 만들면 진행 중 task의 report가 네트워크 한 번에 사라져 재배정·블로커 소음이 난다(6차의 M-3).

- **확인된 부재** — `git ls-remote <HUB> 'refs/heads/<BR>'`로 브랜치가 실제로 없음을 확증했거나(신규 task라 아직 push 전), fetch는 성공했는데 `git cat-file -e refs/remotes/hub/<BR>:<path>`가 비영이라 그 커밋 트리에 경로가 없음을 확증했을 때. 두 확증은 show의 exit 코드와 독립이다. 이때만 **작업트리의 report 파일을 지운다.** 그러지 않으면 유령이 남는다 — 이전 순회·마일스톤 커밋이 남긴 낡은 파일. `recover`는 파일이 **없을 때만** `(None, False)`(부재)를 반환하고, 빈·깨진 파일은 `(None, True)`(무효)로, 낡은 파일은 옛 status로 본다(실측: `recover._read_canonical_report`, frontmatter 부재는 파싱 실패다). 삭제 후에야 "부재 = `(None, False)`"가 참이 된다.
- **관측 실패** — 브랜치가 존재하고 경로도 트리에 있는데(ls-remote·cat-file은 부재를 확증하지 못했는데) fetch·show가 실패한 경우. **작업트리를 건드리지 않는다.** 허브 pre-receive가 삭제를 막으므로(실측: `hub.py`가 zero-SHA를 거부) 기존 task 브랜치는 정상 위상에서 사라지지 않는다 — 따라서 존재하는 브랜치의 materialize 실패는 사실상 일시 오류다. `observe()`는 이 task의 Observation을 만들지 않고 **관측 불가**를 신호하고, 호출자는 이번 주기를 건너뛴다(다음 fetch에 자가 복구). 반복되면 호출자가 블로커로 올린다(재전송 상한과 같은 자리, §4.1).

**materialize는 milestone commit에 선행하며, 그 선행을 절차가 강제한다(§7.4).** 반려·수용 커밋은 그 시점 작업트리의 report를 스테이징하므로(실측: `commit.py`가 `report_path.exists()`일 때만 `report_dir/<task>.md`를 스테이징), 커밋이 박제하는 블롭은 *사람이 리뷰한 그* 허브 블롭이어야 한다. **6차는 이 순서를 서술로만 두어 무너졌다** — 실제 `axdt progress commit` 경로가 materialize를 부르지 않아, 커밋 시점 report가 부재·낡음이면 반려 커밋에 블롭이 안 실리거나 낡은 블롭이 박제됐고, `rework_pushed`가 그 위에서 오작동해 반려가 영구 미전달됐다. 7차는 §7.4 절차를 신설했으나 "락 안에서 materialize→사람 판단→커밋"을 한 임계구역이라 해 사람의 판단이 락 안에 못 들어가고 재자재화가 리뷰 안 한 블롭을 박제할 수 있었다(7차 C-1). 8차는 §7.4를 **사람 판단은 락 밖, 커밋 단계가 diff로 변경 task를 확정→재자재화→리뷰본과 대조(다르면 거부)**로 재서술하고, `commit`이 rejected 이벤트에도 report 블롭 실재를 요구하게 한다(§5) — 부재면 커밋을 거부해 블롭 없는 반려 커밋이 조용히 성립하지 못하게 한다.

#### 반려는 왜 상태만으로 판별되지 않는가

Maintainer가 반려하면 `progress`가 `rejected`가 된다. 그런데 Leader의 report는 여전히 `done`이다 — Leader가 아직 아무것도 하지 않았으므로.

Leader가 재작업을 마치고 report를 다시 push해도 `report`는 또 `done`이고, `progress`는 Maintainer가 수용을 판단하기 전까지 여전히 `rejected`다.

**두 상태의 관측이 완전히 같다**: `progress=rejected` · `report=done` · `IDLE`. 앞은 반려를 보내야 하고 뒤는 보내면 안 된다. `recover`는 이 task를 `in_rework`와 `pending_acceptance`에 **동시에** 넣는다(실측: `recover.py`).

**조상 관계로 풀 수 없다.** 반려 커밋은 호스트 `main`의 마일스톤 커밋이고, Leader의 report 커밋은 허브의 task 브랜치에 있다. `main`은 그 브랜치를 merge하지 않으며(반려는 merge가 아니다), `main` 갱신은 push가 아니라 허브 내부 `update-ref`로 일어난다(`ADR-0007`). **두 커밋은 어느 방향으로도 조상이 아니다.** `git merge-base --is-ancestor`는 정상 위상에서도 항상 거짓을 반환해, 재작업하지 않은 Leader를 "재작업 완료"로 오판하고 반려를 영영 전달하지 않는다.

**내용을 비교한다.** 반려 커밋은 `progress.md`와 **그 시점의 report 파일을 함께 담는다**(실측: `commit.py`가 `report_dir/<task>.md`를 스테이징한다).

```
reject_sha = 이 task를 rejected로 전이시킨 최신 마일스톤 커밋   (호스트 main)
rework_pushed = ( 자재화한 report 블롭  ≠  git show <reject_sha>:docs/interim/report/<task>.md )
```

반려 시점에 박제된 report와 지금 Leader가 push한 report가 **같으면** 아무것도 하지 않은 것이다 → 반려를 보낸다. **다르면** 반려 이후 손을 댄 것이다 → 재작업이 끝났으니 보내지 않는다.

비교 자체는 위상에 의존하지 않으므로 force-push·rebase·amend에도 흔들리지 않는다 — **단 그 전제는 위의 `+` fetch가 force-push를 실제로 가져오는 것이다.** `+`가 없으면 비교의 원료(자재화한 블롭)가 옛 상태에 묶여, 위상 독립인 비교가 낡은 값 위에서 돈다. 두 블롭 모두 호스트 저장소에서 읽는다.

**바이트 비교의 또 다른 전제 — `git add`가 report 바이트를 바꾸지 않는 것.** 이 비교는 "박제 블롭(커밋 인덱스) = 허브 블롭(원본)"이 바이트로 같음에 기댄다. 그런데 `git add`는 clean 필터를 적용한다 — 특히 `core.autocrlf`가 켜지면 CRLF report를 LF로 정규화해 인덱스 블롭이 허브 블롭과 달라진다(실측: 이 컴퓨터의 `core.autocrlf=true`에서 CRLF 블롭이 add 시 다른 blob id로 재인코딩됨을 재현). parser는 CRLF report를 허용하므로(실측: `table.py`) 이 경우가 실재할 수 있고, 그러면 재작업이 없어도 박제 블롭 ≠ 허브 블롭이 되어 `rework_pushed`가 영구 참, 반려가 영구 미전달된다(C-3). **막는 것은 둘이다**: (a) 저장소에 `docs/interim/report/*.md -text -filter -ident`를 `.gitattributes`로 두어 report 경로의 줄끝 정규화(`-text`)·clean/smudge 필터(`-filter`)·`$Id$` 치환(`-ident`)을 모두 끈다(Leader clone과 호스트 정본이 그 attribute를 공유하므로 양쪽 다 바이트를 보존한다). 이 `.gitattributes`는 **Leader가 provision되기 전에 base(main)에 커밋돼 있어야** clone에 실린다(배포 전제). (b) §7.4 커밋 경로가 스테이징 후 `git rev-parse :<path>`(인덱스 블롭 id)를 attest 해시와 대조해, `(a)`가 놓친 어떤 변환으로 인덱스가 재인코딩되든 `CommitRejected`로 시끄럽게 실패한다. (a)가 정상 경로를 항등으로 만들고 (b)가 그 항등을 원인 불문 기계 등급으로 보증한다 — `.gitattributes`가 아직 없는 부트스트랩 상태에서도 (b)가 조용한 유실을 시끄러운 실패로 강등한다.

경계 조건을 명시한다.

- **반려 커밋을 못 찾으면** `rework_pushed`를 정할 수 없다. 반려를 보내지 않고 **블로커**로 올린다(표의 행 8). Phase 4의 `format_milestone_message`가 구조적 메시지를 만들고 `rejected` task에는 사유를 반드시 넣으므로(실측: 없으면 `ValueError`) 보통은 찾힌다.
- **반려가 여러 번이면 최신 것**을 쓴다. 이전 반려는 이미 처리됐거나 최신 반려가 덮는다.
- **현재 자재화된 report가 부재면** 비교할 원료가 없다. `rework_pushed`를 `True`/`False`로 억지로 정하지 않고 `None`으로 두어 **블로커(행 8)**로 올린다. (7차 초안은 여기서 "지금도 없으면 `False`"라 적어 행 11로 반려를 보냈는데, 그것은 §5의 `Observation.rework_pushed` 계약과 어긋난다 — 부재는 비교 불가라 `None`이다. 8차에서 §5로 통일한다.)
- **반려 커밋 자체에 report 블롭이 없는 경우**는 정상 경로에서 발생하지 않는다 — §7.4의 rejected 블롭 게이트가 블롭 없는 반려 커밋을 `CommitRejected`로 막기 때문이다. 마이그레이션·수동 커밋으로 그런 커밋이 남았다면 `rework_pushed=None`으로 두어 행 8(블로커)로 올린다(과거 7차 초안이 이를 `True`로 두어 행 10→`None`으로 삼키던 것이 바로 B-1 증상이다).
- **Leader가 내용을 한 글자도 바꾸지 않고 재작업했다면** `rework_pushed = False`가 되어 반려가 한 번 더 간다. report는 Leader의 보고 채널이므로, 재작업했다면 최소한 `updated`가 바뀌어야 한다. 바뀌지 않았다면 재작업의 증거가 없는 것이고, 다시 반려하는 편이 옳다.

#### 배정은 반복될 수 있다 — 그 상한은 본 Phase가 정하지 않는다

Leader가 배정을 받아 `BUSY`가 됐다가 report를 쓰지 않고 `IDLE`로 돌아오면(포기·오류·컨텍스트 압축), 관측은 미착수와 구별되지 않는다. 표는 배정을 다시 만들고, 다음 주기에도, 그다음에도.

**Leader의 수신 확인이 유일한 정당한 기록이다.** 배정을 받으면 Leader는 가장 먼저 report를 `in-progress`로 쓰고 push한다. 그것이 도착하면(자재화하면) 관측이 바뀌어 배정이 멎는다. Leader 프롬프트가 이 순서를 강제한다.

수신 확인조차 못 하는 Leader에게는 배정이 반복된다. **재전송 자체는 해롭지 않다** — `IDLE`이고 report가 없는 Leader에게 배정이 다시 가면 최악의 결과는 plan을 다시 읽는 것이다. 해로운 것은 그것이 **영원히** 반복되는 것이다.

**그 상한을 `progress.md`에 적지 않는다.** 초안 하나는 배정 직후 Maintainer가 `progress`를 `todo` → `in-progress`로 올려 전달을 기록하게 했다. 세 가지 이유로 폐기한다.

- `rule-report-to-progress-authority`는 `progress.status`를 "Maintainer가 **수용한** 진실"로 정의하고, 권위가 report → progress 한 방향으로 흐르게 한다. report 없이 `in-progress`를 적는 것은 **권위 필드를 배달 플래그로 겸용하는 것**이다.
- Phase 4의 정합성 매트릭스가 그 조합을 이상으로 부른다. `schema.pair_severity(None, "in-progress") == "WARN"`이고(실측: `schema.py`의 공개 함수) `recover`가 `WARN`을 `needs_attention`에 넣으므로(실측), **정상적인 배정마다 Maintainer의 "주의 필요" 목록이 오염된다.**
- 어차피 원자적이지 않다. `inject()`가 반환한 뒤 기록 전에 죽으면 배정은 다시 나간다.

**상한은 루프를 가진 쪽이 정한다.** `needed_instruction()`은 "상태가 무엇을 요구하는가"만 답하는 순수 함수다. "계속 시도할 것인가"는 맥락을 가진 호출자가 답한다 — 상시 tmux 세션인 Maintainer는 자기 대화 맥락에 무엇을 몇 번 보냈는지 갖고 있고(`ADR-0001`), Phase 8의 오케스트레이션 루프는 장수 프로세스라 그 횟수를 메모리에 갖는다. 어느 쪽도 새 저장소가 아니다.

**본 Phase가 만드는 것 중 주입하는 것은 없다.** `axdt watcher tick`은 관측하고 보고할 뿐이고, `axdt leader assign`은 사람이 부른다. **따라서 본 Phase의 산출물만으로는 라이브락이 발생하지 않는다.** 라이브락 방지는 Phase 8의 책임으로 명시해 넘긴다(§11).

**표는 순서대로 평가하고 첫 일치가 이긴다. 그런데 그 순서를 가림 없이 짜는 것이 5차·6차가 반복해 실패한 지점이다.** 평면 우선순위표는 뒤 행의 조건이 앞 행의 부분집합이면 뒤 행이 영영 발화하지 않는다(가림). 5차는 `report=done` 행이 반려를 가렸고, 6차는 report 기반 행이 "progress 행 없음" 블로커를, 반려 행이 재작업 중 올라온 새 블로커를 가렸다. **그래서 7차는 표를 상호배타로 짠다** — `progress` 범주를 1차 키로 삼아 각 행의 조건이 앞 행의 배제를 전제로 정의역을 **분할**하게 한다. 겹치는 조건이 없으므로 어느 행도 다른 행을 가릴 수 없고, 마지막 catch-all이 전함수성을 준다.

분할의 뼈대는 이렇다. 세션이 `IDLE`이 아니면 세션으로 결정한다(행 1~4). `IDLE`이면 `progress` 범주로 가른다 — 종결·보류(행 5·6) → report 무효(행 7) → **반려**(행 8~11) → progress 행 없음(행 12·13) → 착수 상태(행 14~17) → 예상 못 한 조합의 catch-all(행 18).

**두 예외를 정직하게 둔다.** `progress`로 분할되는 네 구간(종결·보류 / 반려 / progress 행 없음 / 착수)은 서로 배타적인 `progress` 집합 위에 서므로(`{accepted·superseded·blocked·paused}` / `{rejected}` / `{행 없음}` / `{todo·in-progress·in-review}` — 실측: `schema.py`, 서로소·전수), **그 네 구간 사이의 순서는 결과를 바꾸지 않는다.** 그러나 **두 행은 구간 분할의 일원이 아니라 순서로 자리를 지킨다.**
- **무효 행(행 7)** — `progress`축이 아니라 `report`축 조건이라 여러 `progress` 값과 겹친다. 그 자리는 의도적이다: 종결·보류(행 5·6) **뒤**여야 이미 끝났거나 보류된 task의 깨진 report를 굳이 블로커로 올리지 않고, **그 밖 모든 IDLE 행(반려·행없음·착수) 앞**이어야 깨진 report 위에서 반려·수용·배정 판단이 돌지 않는다. 반려 뒤로 옮기면 `progress=rejected`·`report=무효`가 깨진 report 위에서 반려를 발송하고(행 11), 종결·보류 앞으로 옮기면 `progress=accepted`·`report=무효`가 블로커가 되며, **행없음 구간(행 12·13) 뒤로 옮기면** `(plan=없음, progress=행없음, report=무효)`가 행 13("배정할 것 없다", `None`)에 먼저 걸려 **깨진 고아 report가 무신호로 방치**된다(행 12·13의 `report` 열이 `—`=전정의역이라 무효 report와 겹친다). 즉 행 7은 종결·보류 뒤이면서 `report` 열이 `—`인 모든 행(반려·행없음)과 착수보다 앞이어야 한다. 이 경계 결과 — `(plan=없음, 행없음, 무효)→블로커` — 는 의도한 것이다: 깨진 report는 plan·progress 유무와 무관하게 데이터 무결성 문제라 표면화한다.
- **catch-all 행(행 18)** — 전열이 `—`(전정의역)이라 어느 `progress` 구간에도 속하지 않는다. **반드시 맨 마지막**이어야 한다. 앞으로 옮기면 모든 관측을 먼저 삼켜 다른 행이 전부 죽는다 — 예컨대 착수 블록(14~17)과 함께 반려 앞으로 옮기면 `progress=rejected`·`report=done`·`거짓`이 행 11(반려)에 닿기 전에 행 18에 걸려 블로커가 된다.

따라서 순서가 우선순위인 것은 **구간 안**, **무효 행의 위치**, **catch-all의 최후 위치**이고, `progress` 분할 네 구간 사이만 순서 독립이다. (행 1~4는 세션이 `IDLE`인지로 IDLE 구간 전체와 갈리므로 세션 접두로 자명하게 앞선다 — 행 7·18 외에 추가 순서 의존 행은 없다.)

`report`와 `progress`는 서로 다른 어휘를 갖는다(실측: `schema.py`) — `rejected`는 **progress에만**, `done`은 **report에만** 있다. 표는 이 실제 어휘로만 쓴다. `recover`가 `progress=rejected`·`report=done` task를 `in_rework`와 `pending_acceptance`에 **동시에** 넣는(실측: `recover.py`) 비배타성은, 표가 `progress` 범주로 먼저 갈라 흡수한다.

| # | plan | progress | report | rework_pushed | session | 지시 |
|---|---|---|---|---|---|---|
| 1 | — | — | — | — | `STARTING`·`BUSY` | 없음 — 일하고 있다 |
| 2 | — | — | — | — | `WAITING_INPUT` | 없음 — 사람의 결정 |
| 3 | — | — | — | — | `STOPPED` | 없음 — 죽음 확인됨. 재기동이 먼저 (§4.5·§7.3) |
| 4 | — | — | — | — | `ERROR` | **블로커** — §7.3이 `is_alive`로 죽음이면 재기동으로 먼저 가른다 |
| 5 | — | `accepted`·`superseded` | — | — | `IDLE` | 없음 — 끝 |
| 6 | — | `blocked`·`paused` | — | — | `IDLE` | 없음 — Maintainer가 보류했다 |
| 7 | — | — | 무효 | — | `IDLE` | 없음 — **블로커** (깨진 report 위에 판단하지 않는다) |
| 8 | — | `rejected` | — | `None` | `IDLE` | 없음 — **블로커** (반려 커밋 못 찾음 · 현재 report 부재 · 반려 커밋 트리에 블롭 없음) |
| 9 | — | `rejected` | `blocked`·`needs-spec`·`todo`·`in-progress` | 참 | `IDLE` | 없음 — **블로커** (새 블로커이거나 재작업 중 정지) |
| 10 | — | `rejected` | `done` | 참 | `IDLE` | 없음 — 재작업 완료. 수용 대기 |
| 11 | — | `rejected` | — | 거짓 | `IDLE` | **반려** |
| 12 | 있음 | 행 없음 | — | — | `IDLE` | 없음 — **블로커** (plan은 있는데 progress에 행이 없다) |
| 13 | 없음 | 행 없음 | — | — | `IDLE` | 없음 — 배정할 것이 없다 |
| 14 | — | `todo`·`in-progress`·`in-review` | `blocked`·`needs-spec` | — | `IDLE` | 없음 — Maintainer의 블로커 판단 차례 |
| 15 | — | `todo`·`in-progress`·`in-review` | `done` | — | `IDLE` | 없음 — Maintainer의 수용 판단 차례 |
| 16 | 있음 | `todo`·`in-progress` | 부재 | — | `IDLE` | **배정** |
| 17 | — | `todo`·`in-progress` | `todo`·`in-progress` | — | `IDLE` | 없음 — **블로커** (수신 확인 후 정지) |
| 18 | — | — | — | — | — | 없음 — **블로커** (예상 못 한 조합. 예: `in-review`인데 report가 부재·`todo`·`in-progress`) |

**행 7(무효)이 report 기반 판단을 앞선다.** `recover`가 부재(`report=None, report_invalid=False`)와 파손(`report=None, report_invalid=True`)을 구분하는데(실측: 그 구분을 위한 필드다), 깨진 report 위에서는 `rework_pushed`도 수용 판단도 신뢰할 수 없으므로 무효를 먼저 블로커로 올린다.

**반려 구간(행 8~11)은 5·6차가 무너진 자리다.** 반려의 정상 관측은 `progress=rejected`·`report=done`·`IDLE`이다 — `report`에 `rejected`가 없어(실측: `schema.py`의 `REPORT_STATUSES`) 재작업 전까지 report는 `done`에 머문다. 5차는 `report=done` 행이 이 관측을 먼저 잡아 반려를 죽였다. 7차는 `progress=rejected`를 하나의 구간으로 떼어 report 기반 행보다 앞에 두고, 안에서 `rework_pushed`로 가른다.
- 행 8 — `rework_pushed=None`. 세 경우다: 반려 커밋을 못 찾았거나(§4.1), **현재 자재화된 report가 부재**하거나, **반려 커밋을 찾았지만 그 커밋 트리에 report 블롭이 없다**(§5 `rework_pushed`가 이 셋을 `참`이 아니라 `None`으로 낸다). 어느 쪽도 비교 불가라 블로커다(현재 부재는 대개 일시적 fetch 실패이므로, §4.1의 materialize가 그것을 부재로 뭉개지 않고 블로커로 올린다).
- 행 9 — `참`인데 report가 완료(`done`)가 아니다. 블롭은 바뀌었지만 report가 `blocked`·`needs-spec`이면 재작업이 아니라 **Leader가 올린 새 블로커**이고(그것을 "재작업 끝"으로 흡수하면 블로커가 유실된다 — 6차의 M-4), `todo`·`in-progress`인데 `IDLE`이면 **재작업을 시작해 놓고 중간에 멈춘 것**이다(착수 구간의 행 17과 대칭 — 수신 확인 후 정지). 어느 쪽도 Maintainer가 봐야 하므로 블로커로 올린다. `rework_pushed=참` 하나로 뭉뚱그리지 않고 report 상태를 함께 본다.
- 행 10 — `참`이고 report가 `done`. 재작업이 완료됐으니 아무것도 하지 않고 Maintainer의 수용 판단을 기다린다. (report **부재**는 여기 오지 않는다 — 부재면 `rework_pushed=None`이라 행 8에서 이미 걸린다. `todo`·`in-progress`도 오지 않는다 — 행 9가 중간 정지로 앞서 잡는다. Codex 8차 지적: `참`+`todo`·`in-progress`를 `None`으로 삼키면 반려 후 재작업 중 정지가 침묵한다.)
- 행 11 — `거짓`. 반려 시점 블롭과 지금이 같다. 손대지 않았으므로 반려한다. **행 11은 plan을 요구하지 않는다** — 반려는 report와 커밋을 가리키지 plan을 가리키지 않는다.

**progress 행 없음(행 12·13)이 착수 상태 판단을 앞선다.** 6차는 report 기반 행(done/blocked)이 이 구조 검사를 가려, plan만 쓰고 progress 행을 빠뜨린 task가 report를 가지면 침묵으로 샜다(M-2). 7차는 `progress=None`(행 없음)을 독립 구간으로 떼어 report 기반 행(14·15) 앞에 둔다. plan이 있으면 블로커(행 12), 없으면 배정할 것이 없다(행 13). `reconstruct`가 `progress.md` 행만 순회하므로(실측) 행 없는 task는 요약에도 안 뜨는데, 행 12가 그 침묵을 블로커로 드러낸다.

**착수 구간(행 14~17)은 `progress ∈ {todo, in-progress, in-review}`이고 report가 무효가 아닌 나머지다.** report가 `blocked`·`needs-spec`이면 Maintainer의 블로커 판단(행 14), `done`이면 수용 판단(행 15)이다 — 여기 도달하면 `progress`는 `rejected`가 아님이 보장된다(반려 구간이 앞서 걸렀다). report가 부재이고 progress가 `todo`·`in-progress`이며 plan이 있으면 배정한다(행 16). progress도 report도 `todo`·`in-progress`이면 Leader가 수신 확인 후 멈춘 것이므로 블로커다(행 17). 그 밖(예: `in-review`인데 report 부재, 또는 progress 행은 있는데 plan 파일이 없음)은 **구간 밖의 catch-all(행 18)**이 블로커로 올린다 — 행 18은 착수 구간의 일원이 아니라 전정의역을 받는 최후 행이다.

**행 4(ERROR)는 `poll_state`의 실제 의미론에 정직하다.** `poll_state`의 `ERROR`는 살아 있는 세션의 화면 마커에서도(실측: `adapters/claude_code.py`의 `_ERROR_MARKERS`), **죽어서 비영 종료 코드로 끝난 세션에서도** 나온다(실측: `runner.py`가 `not is_alive()`에서 `exit_code() not in (None,0)`이면 `ERROR`). 그래서 표만으로는 둘을 못 가른다. §7.3은 이 표를 부르기 전에 `is_alive()`로 실제 죽음을 확인해, 죽었으면 재기동 경로로(§7.2), 살아 있으면 행 4의 블로커로 보낸다. 표를 단독으로 쓰는 호출자(Phase 8 등)에게 행 4는 안전한 backstop이다 — 죽은 세션을 블로커로 보내는 것은 조용히 무시하는 것보다 낫고, 재기동이 필요하면 그 호출자도 §7.3처럼 `is_alive`를 먼저 확인해야 한다. **행 3(STOPPED→`None`)은 이 backstop이 비대칭임을 드러낸다** — 행 4가 ERROR를 블로커로 올리는 것과 달리 STOPPED(정상 종료 사망)는 `None`(정상, 할 일 없음)이라, `is_alive` 관문 없이 표만 쓰는 소비자는 **깨끗이 죽은 Leader를 아무 신호 없이 방치**한다. §7.3 경로에서는 관문이 STOPPED를 표 앞에서 재기동으로 보내 문제없으나, Phase 8 계약은 "ERROR뿐 아니라 STOPPED도 `is_alive` 선행"을 명시해야 한다(§9로 넘기는 요구).

**행 18은 진단이지 무시가 아니다.** 여기 도달했다는 것은 관측이 예상 상태 공간 밖에 있다는 뜻이므로, 조합을 그대로 담아 블로커로 올린다.

**한 Leader는 한 task를 맡는다**(실측: `naming.py`의 identity 모델). 결정표가 task 단위인 것은 그 때문이다. 한 세션에 두 task를 주는 경우는 본 Phase가 정의하지 않는다 — 입력창이 하나뿐이므로 정의하려면 별도 설계가 필요하다.

**허브 위조는 이 오라클도 상속한다.** report는 Leader가 쓰고 push하며, 허브는 무인증이다(`rule-protected-paths`가 ref 위장 방지를 권고 등급으로 둔다). 오염된 Leader A가 B의 report를 `done`으로 위조하면 B로의 배정이 멎고 위조 report가 수용 대기에 앉는다. **최종 게이트가 사람의 수용 판단이므로 잘못된 코드가 main에 들어가지는 않지만**, 진행이 조용히 멈출 수 있다. 수용된 위험이며 Phase 3·6의 `pre-receive`가 좁힌다.

**Leader는 배정을 받으면 가장 먼저 report를 `in-progress`로 쓰고 push한다.** 이것이 수신 확인이고, Leader 프롬프트가 강제한다. 덕분에 "받은 적 없음"(`report` 없음)과 "받고 멈춤"(`report`가 `in-progress`인데 `IDLE`)이 **관측만으로 구별된다.** 앞은 배정을 (다시) 보내고, 뒤는 배정을 되풀이해도 소용없으므로 블로커로 올린다.

이 구별이 없으면 배정을 받고 아무 일도 못 한 Leader에게 영원히 같은 배정이 반복된다. 2차 개정본에는 그 구별이 없었다.

**주입자 크래시로 인한 유실이 사라진다.** 주입자가 어느 지점에서 죽든, 다음 주기에 같은 관측이 같은 지시를 다시 만든다. `SKIPPED`라는 결과가 없으므로 `SKIPPED`가 삼키던 지시도 없다. 이것은 *배달 기록을 두지 않기 때문에* 성립하며, 상태 마커의 정확도에 기대지 않는다.

**중복 실행은 `IDLE` 게이트가 줄인다.** 지시가 실제로 제출됐다면 Leader는 `IDLE`을 벗어나고, 그 상태에서는 아무것도 보내지 않는다. 다만 게이트의 신뢰도는 상태 마커의 신뢰도이고 그것은 아직 provisional이므로(실측: `PLATFORM_MATRIX`), **"막는다"가 아니라 "줄인다"**로 적는다. §8.3이 확정하기 전까지 이 문장은 조건부다.

**반려는 사유 커밋을 라이브 조회로 찾는다.** `progress`가 `rejected`라는 것만으로는 메시지를 만들 수 없다 — 본문이 사유가 담긴 커밋을 가리켜야 하는데 `TaskState`에는 그 sha가 없다(실측). Phase 4의 `format_milestone_message`가 구조적 메시지를 만들고 `rejected` task에는 사유를 반드시 넣으므로(실측: 없으면 `ValueError`), `git log`로 그 task를 `rejected`로 전이시킨 최신 마일스톤 커밋을 찾을 수 있다. 찾지 못하면 반려를 보내지 않고 블로커로 올린다.

**언제 그만둘지는 Maintainer가 판단한다.** "같은 배정을 세 번 보냈다"는 것은 세어야 알 수 있고, 세려면 저장소가 필요하다 — `ADR-0002`가 막는 바로 그것이다. 셀 필요가 없다. Maintainer는 상시 tmux 세션이고(`ADR-0001`) 자기 대화 맥락에 무엇을 몇 번 보냈는지 가지고 있다. **수렴 판정은 "상태가 무엇을 요구하는가"만 답하고, "계속 시도할 것인가"는 맥락을 가진 Maintainer가 답한다.** `axdt watcher tick`은 주입하지 않으므로 이 판단이 필요 없다.

**토큰은 남기되 오라클이 아니다.** 메시지 앞머리의 `[axdt:assign:<task>:<hash8>]`는 사람이 로그를 읽을 때의 표식이고 테스트가 렌더링을 고정하는 수단이다. **어떤 분기도 토큰의 로그 존재 여부를 보지 않는다.** 따라서 캡처 로그는 원래 역할(상태 마커 판정용 transcript)로 돌아가고, 보존 의무도 적대적 쓰기 표면도 없다.

**자유 텍스트 주입(`maintainer send`·`leader send`)에는 멱등이 없다.** 수렴시킬 상태가 없기 때문이다. 사람이 조작하는 디버깅 경로이므로 사람이 책임진다.

#### 상태 게이트

`runner.poll_state()`가 `IDLE`일 때만 보낸다.

| 상태 | 처리 |
|---|---|
| `IDLE` | 주입한다. 제출 증거 관측 여부에 따라 `SENT` 또는 `UNCONFIRMED` |
| `BUSY` | 보내지 않고 `DEFERRED`를 반환한다. 다시 시도할 시점은 호출자가 정한다 |
| `WAITING_INPUT` | 보내지 않고 `NEEDS_HUMAN`을 반환한다. 사람의 결정이 필요하므로 블로커로 올린다(Phase 7에서 메신저로 승격) |
| `STARTING` | 보내지 않고 `DEFERRED`를 반환한다. 대기는 호출자의 몫이다(`wait_until_idle`) |
| `ERROR`·`STOPPED` | 보내지 않고 `UNAVAILABLE`을 반환한다. **재기동은 실사 후에만**(§4.5) |

**기존 `AgentRunner.send_prompt()`를 쓰지 않는다.** 그 함수는 `IDLE`과 `WAITING_INPUT`을 둘 다 받는다(실측: `INPUT_ACCEPTING`). 주입은 `IDLE` 전용 경로를 새로 둔다.

`BUSY`인 세션에 프롬프트를 밀어넣으면 무슨 일이 벌어지는지는 **측정 대상**이다. 초안은 "조용히 사라진다"고 단정했으나 근거가 없었고, 큐에 쌓일 가능성이 있다. `IDLE` 게이트의 방어적 가치는 그와 무관하게 유지한다 — 상태를 알고 보내는 편이 모르고 보내는 편보다 낫다.

#### 메시지 형식 — 단일행, 참조 중심

Phase 4가 명시적으로 본 Phase에 넘긴 산출물이다("지시 전달과 반려 통보의 send-keys 메시지 포맷"·"반려 근거 자체의 형식화").

**메시지는 한 줄이고 탭도 없다.** 개행이나 **탭**이 있으면 `tmux.send_text()`가 `send-keys`가 아니라 `paste-buffer` 경로를 타고(실측: `tmux.py`가 둘 다에 paste-buffer를 쓴다), 붙여넣기가 TUI에서 자리표시자로 접힐 수 있다. 상세 내용은 이미 파일에 있으므로 메시지는 그것을 가리키기만 한다. `note` 자유 텍스트에 탭이 섞이지 않게 하는 것은 호출자 책임이다.

```
[axdt:assign:w1.t1-auth-login:a3f9c2e1] task 배정. docs/interim/plan/task/w1.t1-auth-login.md 를 읽고 착수하라.
[axdt:reject:w1.t1-auth-login:3fa1c0de] report 반려. 커밋 9336a25 의 메시지에서 사유를 확인하고 재작업하라.
```

`hash8` = `sha256("<kind>|<task>|<body>")`의 앞 8자. **구분자를 넣는다** — 없이 이으면 slug가 숫자로 끝나는 task에서 경계가 모호해진다. 이 값은 사람이 로그에서 메시지를 식별하는 표식이지 멱등 키가 아니다.

목표와 완료 조건은 plan 파일에 있고, 반려 사유는 Phase 4가 정한 대로 `rejected` 전이의 마일스톤 커밋 메시지에 있다. 본 절은 **전달 형식**만 정하고 durable 기록은 Phase 4 소관이다.

`kind`는 `assign`·`reject`·`note` 셋이다. `note`는 자유 텍스트 주입용이고 `task` 자리에 `-`를 쓴다.

**자유 텍스트가 상태 마커 문자열을 품으면 안 된다.** 어댑터의 `detect_state`는 transcript에서 `Error:` 같은 문자열을 찾는다(실측: `adapters/claude_code.py`). 그 문구가 에코되면 상태 판정이 오염된다. `note` 주입의 호출자 책임으로 명시한다.

#### 전송의 원자성 — 입력창은 공유 자원이다

`format_prompt`가 텍스트 끝에 개행을 붙이고(실측: `text + "\n"`, docstring에 "including the submit newline"), 개행이 있으면 `send_text`가 `paste-buffer` 경로를 탄다(실측). bracketed-paste 하에서 붙여넣어진 개행이 제출로 해석되는지는 `PLATFORM_MATRIX.md`가 스스로 미확정으로 표시한 항목이다. **입력 상자에 타이핑된 것과 프롬프트가 제출된 것은 다른 사건이다.**

멱등을 상태 수렴으로 옮겼으므로 이 구분이 더 이상 유실을 만들지는 않는다. 그러나 **오염은 만든다.** 세션의 입력창은 하나뿐인 공유 자원이고, 타이핑은 상태 마커를 바꾸지 않으므로 타이핑 중인 세션도 `IDLE`로 보인다.

- 주입자 A가 본문을 타이핑하고 제출 전에 죽으면, 본문이 입력창에 **남는다.** 다음 주입자 B의 본문이 그 뒤에 이어 붙고, B의 Enter가 `A본문B본문`을 한 줄로 제출한다.
- 크래시가 없어도 같다. A가 타이핑하고 B가 게이트를 통과해(둘 다 `IDLE`로 본다) 끼어들면 같은 접합이 일어난다.

셋으로 닫는다.

**첫째, 타이핑과 제출을 분리한다.** 본문(개행 없는 단일행)을 `send-keys -l`로 보내고 제출을 별도 키 이벤트로 보낸다. `format_prompt`는 제출 개행을 붙이지 않고, `SessionBackend`에 `submit()`을 추가한다. 제출이 독립 사건이어야 관측할 수 있다.

**둘째, 타이핑 전에 입력창을 비운다.** 이전 주입자의 잔류물을 지우는 유일한 방법이다.

여기에 위험이 있다. **입력창을 비우는 키는 `IDLE` 밖에서 다른 뜻을 갖는다.** `Esc`는 이 TUI들에서 생성 인터럽트이자 다이얼로그 닫기를 겸한다. 게이트를 통과한 뒤 타이핑 전에 세션이 `WAITING_INPUT`으로 넘어갔다면, 우리가 보내는 삭제 키와 뒤이은 Enter는 **권한 프롬프트에 대한 응답**이 된다 — 의도치 않은 승인이다.

그래서 세 가지를 정한다.

- 삭제 키는 `Esc`를 쓰지 않는다. 줄 삭제 의미가 고정된 `Ctrl-U`를 기본으로 하고, 실제 키와 **그 키가 `IDLE` 밖에서 무해한지**를 §8.3에서 측정한다.
- 삭제 키 직전에 상태를 **다시 폴링한다.** `IDLE`이 아니면 아무것도 보내지 않고 그 상태의 결과를 반환한다.
- 그래도 창은 남는다. `poll_state()`는 캡처 꼬리의 마커 추론이라 낡을 수 있고(실측: `runner.py`의 `TAIL_WINDOW` 절단), 락은 다른 주입자를 배제할 뿐 **에이전트 자신의 전이를 막지 못한다.** 이것을 수용된 잔여 위험으로 명시한다.

**셋째, 락이 제출까지 덮는다.** 보유 구간은 첫 `poll_state()` 게이트부터 `submit()` 반환까지다. 2차 개정본은 "토큰이 로그에 나타날 때까지"라고 썼는데, 그러면 제출이 락 밖이라 위의 접합이 그대로 일어나고, 게다가 CLI가 에코하지 않으면 **전역 락을 쥔 채 영원히 회전**한다. 로그를 기다리는 단계 자체를 없앴으므로 두 문제가 함께 사라진다. 락 획득에는 상한을 두고, 초과하면 `DEFERRED`를 반환한다.

#### 제출 증거는 통제 흐름이 아니라 계측이다

`inject()`는 `submit()` 후 상한 `confirm_timeout_s` 동안 **`IDLE`에서의 이탈**을 관측한다.

| 관측 | 결과 |
|---|---|
| `BUSY` 또는 `WAITING_INPUT`으로 전이 | `SENT` |
| `ERROR`·`STOPPED`로 전이 | `UNAVAILABLE` — 세션이 죽었다 |
| 상한까지 `IDLE` 유지 | `UNCONFIRMED` |

**증거를 `BUSY` 하나로 좁히지 않는다.** 제출 직후 첫 행동이 권한 프롬프트면 세션은 `BUSY`를 건너뛰고 곧장 `WAITING_INPUT`으로 간다. 그것도 제출의 증거다.

이 오라클은 **"`IDLE`인 에이전트는 입력 없이 `IDLE`을 벗어나지 않는다"** 는 미측정 전제 위에 있고, 상태 마커 자체도 provisional이다(실측). 그래서 §8.3의 측정 항목이다.

**그럼에도 오라클의 오류가 시스템을 망가뜨리지 않는다.** 통제 흐름을 결정하는 것은 `SENT`/`UNCONFIRMED`가 아니라 **다음 주기의 관측**이기 때문이다.

- 위양성 `SENT`(제출 안 됐는데 됐다고 봄) → **아무 상태도 바뀌지 않는다.** 다음 주기 관측이 같은 지시(배정 또는 반려)를 다시 낸다. 유실 없이 수렴한다. (배정을 `progress`에 기록하는 경로는 폐기했으므로, 여기서 `progress`가 오르지 않는다 — 그 기록은 `rule-report-to-progress-authority` 위반이었다.)
- 위음성 `UNCONFIRMED`(제출됐는데 못 봄) → 지시가 실제로 닿았다면 Leader의 행동이 관측을 바꾸고(예: report가 `in-progress`로 나타남), 닿지 않았다면 다음 주기가 다시 낸다. 어느 쪽도 유실이 없다.

`SENT`와 `UNCONFIRMED`의 차이는 **로그에 남길 진단 정보**이지 분기가 아니다. 이것이 수렴 재정의가 준 여유다 — 오라클이 틀려도 상태가 바로잡는다.

**따라서 `UNCONFIRMED`에 자동 재시도도, 횟수 세기도 없다.** 셀 자리가 없고(`ADR-0002`), 셀 필요도 없다.

#### 권한 프롬프트

초안은 "컨테이너가 인터넷에 연결돼 있으므로 승인 우회 플래그를 쓰지 않는다"고 논증하면서, 동시에 범위 제한 없는 `Bash`를 사전 승인했다. 임의 셸은 임의 쓰기이자 임의 네트워크 송신이므로, 우회 플래그가 열었을 위험 대부분이 그대로 열려 있었다. **논거가 서지 않았다.**

정확한 서술은 이렇다.

- **Docker 컨테이너가 파일시스템 위험을 흡수한다.** workspace만 마운트하고 `--user`로 권한을 낮춘다(실측: `container.run_args`). 임의 셸이 저지를 수 있는 최악은 자기 clone을 망가뜨리는 것이고, 호스트 파일과 다른 Leader의 작업에는 닿지 않는다.
- **남는 위험은 나가는 방향의 유출이다.** 컨테이너에서 임의 주소로 전송할 수 있다.
- **에이전트 CLI는 API를 호출해야 살아 있으므로 네트워크를 완전히 끊을 수 없다.**

따라서 승인 우회 플래그(`--dangerously-skip-permissions`, `--dangerously-bypass-approvals-and-sandbox`)를 쓰지 않는다. 대신 셋을 조합한다.

1. **권한 모드** `--permission-mode dontAsk` — 허용 목록의 규칙과 읽기 전용 셸 명령만 실행하고, 나머지는 묻지 않고 거부한다(문서). 우회 플래그를 켜지 않고도 `WAITING_INPUT` 정지를 없앤다.
2. **범위 허용** — `Bash(git *)`, `Bash(pytest *)`, `Bash(axdt-subagent *)`. 범위 문법은 문서로 확인됐다(`*` 앞의 공백이 접두사 일치를 켠다).
3. **거부 목록** — `--disallowedTools`로 `Bash(curl *)`, `Bash(wget *)`, `WebFetch`.

Codex 쪽은 `-s workspace-write` 샌드박스와 `.rules` 실행 정책이 같은 역할을 한다.

**3층이 유출을 막는다고 말하면 거짓이다.** 허용된 `Bash(git *)`가 `git push <임의 URL>`을 포함하고, `Bash(pytest *)`가 임의 파이썬을 실행한다. 거부 목록은 **사고성 유출을 줄일 뿐**이고, 의도적 유출은 Phase 3의 egress 허용목록이 들어오기 전까지 열려 있다. 이것을 수용된 위험으로 명시한다 — 근거는 컨테이너 안에서 도는 것이 우리가 프롬프트를 쓴 에이전트이지 적대적 코드가 아니라는 것이고, 이 전제가 깨지면(예: 신뢰할 수 없는 코드를 읽는 task) 그 task는 Phase 3 하드닝 전까지 돌리지 않는다.

**egress를 허용 목록으로 좁히는 것**(API 도메인과 허브만)을 Phase 3 백로그로 올린다. 위 세 층은 그 하드닝에 의존하지 않으므로 하드닝이 늦어져도 지금 수준이 내려가지는 않지만, 지금 수준이 "유출 차단"은 아니다.

`WAITING_INPUT` 분기는 그래도 유지한다. 관측할 수 있어야 무엇이 막혔는지 안다.

#### 신뢰 상태를 이미지에 굽는다

컨테이너 HOME은 `/tmp/axdt-home`이고 매번 비어 있다(실측: `config.CONTAINER_HOME`, `container.run_args`의 `-e HOME=...`). 그대로 두면 Leader가 신뢰 확인·온보딩·로그인 프롬프트에서 영구 정지한다.

이미지 빌드 시점에 다음을 넣는다.

- **Claude Code**: `~/.claude.json`의 `projects["<컨테이너 안 절대경로>"].hasTrustDialogAccepted: true`. 키가 컨테이너 안 경로이므로 `config.CONTAINER_WORKDIR`(`/work`)로 고정할 수 있다(실측: 바인드 마운트 대상이 상수).
- **Codex**: `config.toml`의 `[projects.'/work'] trust_level = "trusted"`.
- **온보딩 완료 표시** — 신뢰 다이얼로그와 별개의 최초 실행 안내가 있다. 실제 키 이름은 §8.3에서 측정한다.
- 자격증명은 굽지 않는다. `ANTHROPIC_API_KEY`를 `docker run -e`로 주입한다(이미지에 넣으면 이미지가 곧 자격증명이 된다).

**주의 두 가지.**

`container.run_args`는 `--user {uid}:{gid}`로 호출자의 uid를 넘긴다(실측). 빌드 시점에 uid를 모르므로 `/tmp/axdt-home`은 **임의 uid가 쓸 수 있어야** 한다(`chmod 0777`, 혹은 sticky bit). 굽는 파일도 world-readable이어야 한다.

`/tmp`가 이미지 레이어로 남는지, 런타임이 tmpfs로 덮는지는 확인해야 한다. 덮이면 구운 내용이 사라지고 원래 문제로 돌아온다. `HOME`을 `/tmp` 밖(`/axdt-home` 등)으로 옮기는 것이 대안이며, `config.CONTAINER_HOME` 변경이므로 Phase 3 코드를 건드린다. **§8.3 측정 항목이고, 결과에 따라 Phase 3 수정이 딸려온다.**

### 4.2 Leader → Maintainer 상향

`docs/interim/report/<task>.md`가 유일한 상향 채널이다(`ADR-0003`). 포맷·네이밍·상태 어휘·전이표는 Phase 1과 Phase 4가 확정했고 본 Phase는 `## 후속 제안` 절만 추가한다(§2.6).

Leader는 report를 쓰고 허브로 push하며, Maintainer는 허브에서 읽는다. **컨테이너 파일시스템을 호스트가 직접 읽지 않는다** — push된 것만 신뢰한다(§4.5).

Maintainer의 수용은 Phase 4의 `commit`이 수행하고, 수용 판단 자체는 도구가 아니라 Maintainer가 한다(`rule-report-to-progress-authority`).

### 4.3 Leader의 sub-agent 중계

Leader는 Developer·Reviewer·Tester를 호출하고 결과를 받는 허브다(`rule-subagent-no-direct-communication`).

```
Leader → Developer  : 구현 지시
Developer → Leader  : 변경된 코드
Leader → Reviewer   : 그 변경 (Leader가 전달)
Reviewer → Leader   : 리뷰 결과
Leader → Developer  : 수정 지시 (Leader가 중계)
```

sub-agent 사이에 화살표가 없다. **이 격리의 근거는 플랫폼마다 다르다.**

- **Claude Code**: 네이티브 sub-agent 모델이 보장한다. sub-agent는 자신을 호출한 세션에만 응답하며 서로를 볼 수 없다.
- **Codex**: 네이티브 sub-agent가 없다. AXDT의 래퍼 스크립트가 각 호출을 독립 프로세스로 띄우고 표준 출력만 Leader에게 돌려준다(§2.3.3). 프로세스 경계가 격리를 만들지만, 그것을 만드는 주체는 플랫폼이 아니라 AXDT다.

두 경우 모두, sub-agent에게 다른 sub-agent를 호출할 도구를 주지 않는다. Codex 쪽은 `.rules`가 `axdt-subagent` 실행을 sub-agent 프로파일에서 거부한다.

### 4.4 Leader 간 조율

Leader는 다른 Leader와 직접 통신하지 않는다(`rule-leader-coordination-via-maintainer`). 의존이 생기면 자기 report의 `## 블로커` 절에, 새 작업이 필요하면 `## 후속 제안` 절에 적는다. Maintainer가 읽어 판단한 뒤 관련 Leader에 §4.1의 규약으로 주입한다. 본 Phase는 이 경로에 새 메커니즘을 추가하지 않는다.

### 4.5 실패와 복구

**Leader 세션 사망**(`ERROR`·`STOPPED`)

**`poll_state()`의 `ERROR`만으로 재기동하지 않는다.** 그 값은 transcript에서 `"Error:"`·`"fatal:"` 문자열을 찾아 나오므로(실측: `adapters/claude_code.py`의 `_ERROR_MARKERS`), 테스트 실패 출력 한 줄이면 멀쩡히 일하는 Leader가 `ERROR`로 보인다. 코드 작업 task에서 그런 줄은 일상이다.

재기동 전에 **프로세스의 실제 죽음을 확인한다** — `is_alive()`가 거짓이거나, `attach()`가 실패하고 `post_mortem()`이 종료 코드를 돌려줄 때만. 살아 있는데 `ERROR` 마커가 보이면 그것은 재기동 대상이 아니라 **블로커**다. §2.4가 Watcher에 건 하한선과 같은 규칙이며, 주입·수렴·본 절의 모든 경로에 적용된다.

죽은 세션을 걷어내고 같은 workspace 위에 다시 띄운다. **현재 코드로는 양쪽 끝이 모두 막혀 있다.**

- `down()`은 세션을 정지한 뒤 `workspace.teardown()`을 불러 workspace를 통째로 지우고, 미push 커밋이 있으면 지우는 대신 `RuntimeError`를 던진다(실측: `leader.py`, `workspace.py`).
- `up()`은 **무조건** `workspace.provision()`을 부르고, `provision()`은 workspace가 이미 있으면 `force` 없이 `FileExistsError`를 던진다(실측: `leader.py:30`, `workspace.py:33-35`). docstring이 스스로 "멱등 아님"이라고 적었다.

2차 개정본은 `down(keep_workspace=True)`만 추가하고 `up()` 쪽을 놓쳤다. 그러면 재기동은 1단계를 통과하고 **2단계에서 죽는다.** `provision(force=True)`로 우회하면 내부에서 `teardown()`을 부르므로 workspace를 지운다 — 아래의 "미커밋 작업은 잃지 않는다"와 정면 충돌한다.

양쪽을 함께 고친다.

- `down(root, i, *, force=False, keep_workspace=False)` — `keep_workspace=True`면 `stop()`만 하고 `teardown`을 건너뛴다.
- `up(root, i, *, reuse_workspace=False, ...)` — `reuse_workspace=True`면 `provision()`을 건너뛰고, workspace가 실재하며 기대한 작업 브랜치에 있는지만 검증한다. 없으면 `FileNotFoundError`.
- `restart(root, i)` — 위 둘을 한 함수로 묶는다. 호출자가 짝을 틀리게 맞출 수 없게 한다.

**`reuse_workspace=True`일 때 보상 정리를 하지 않는다.** 현재 `up()`은 `start()`가 실패하면 `workspace.teardown(root, i, force=True)`로 되돌린다(실측: `leader.py`). `force=True`는 미push 커밋 검사를 **우회한다**(실측: `workspace.py`). 방금 만든 workspace를 지우는 것은 원자성 근사로 옳지만, 재기동 경로에서는 그 workspace에 **잃어서는 안 되는 미커밋 작업이 들어 있다.** 포트 점유나 tmux 창 잔존 같은 일시적 start 실패가 그것을 지운다. `reuse_workspace=True`면 예외를 그대로 올리고 workspace는 손대지 않는다.

**미커밋 작업은 잃지 않는다.** workspace는 호스트 디렉터리를 바인드 마운트한 것이므로(실측: `-v {host_workdir}:{CONTAINER_WORKDIR}`), 컨테이너가 죽어도 파일은 호스트에 그대로 있다. 잃는 것은 **에이전트의 대화 맥락**이고, 그래서 재기동한 Leader는 `progress.md`와 자기 workspace의 git 상태에서 스스로를 복구해야 한다. Leader 프롬프트가 이 경계를 명시한다: 세션은 언제든 재시작될 수 있으니 진행 상황을 대화에만 두지 말고 커밋과 report에 남겨라.

Maintainer가 신뢰하는 상태는 여전히 **허브에 push된 report와 커밋**뿐이다(§4.2). 이것은 손실 경계가 아니라 권위 경계다 — 호스트는 컨테이너 파일시스템을 읽지 않는다.

**주입 실패**: 다음 주기의 관측이 지시의 필요 여부를 다시 판정한다(§4.1). 재기동 여부와 무관하게 수렴한다.

**동시 실행**: 두 종류의 락을 **분리**한다. 하나로 합치면 tick이 자기 자신을 막는다.

- **cron overlap 락** — cron이 `flock -n {lockfile} {watcher_cmd}`로 tick을 감싸(실측: `cron.py`) 겹친 tick을 막는다. 이 파일을 프로젝트 락과 **같게 두지 않는다.** 같게 두면 래퍼가 쥔 락을 자식 tick이 다시 잡지 못한다 — `flock(2)`는 열린 파일 서술자(OFD) 단위라 별도 open으로 얻은 fd의 요청이 이미 상속한 fd의 락에 거부된다(문서). **5차 개정본이 무너진 자리다.** cron overlap 락은 `<root>/.axdt/cron.lock`으로 두고(`cron.install`의 기존 `lockfile` 인자로 전달 — `cron.py`는 손대지 않는다), tick 프로세스는 이 락을 **다시 잡지 않는다.**
- **프로젝트 락** — `<root>/.axdt/lock`. Watcher tick·`maintainer up/down`·`leader up/down/restart`·주입·**`progress status`**(짧은 리뷰 세션, materialize가 작업트리를 쓰므로)·**`progress commit`**이 프로세스 내부에서 잡는다. cron overlap 락과 다른 파일이므로 tick이 자기 래퍼와 충돌하지 않는다. Leader 생애주기 조작은 캡처 로그를 절단하고 창을 걷어내므로(실측: `start_capture`), 같은 Leader에 대한 주입과 겹치면 죽은 창에 키를 쏘게 된다. `progress commit`을 포함하는 이유는, 반려·수용 커밋이 스테이징하는 report 파일을 주입 경로의 materialize가 같은 순간 덮어쓰기 때문이다(§4.1) — 락 밖이면 커밋이 리뷰하지 않은 블롭을 박제한다(실측: `cli.py`의 `progress commit`에 현재 락이 없다). 주입의 락 보유 구간은 §4.1·§7.3이 정한다.

**프로젝트 락은 프로젝트당 하나다.** Leader별로 쪼개면 무관한 Leader들이 병렬로 움직이지만, `progress.md`는 프로젝트 단위 단일 파일이고 report 자재화가 그 작업트리를 건드린다(§4.1). 두 주입자가 서로 다른 Leader를 다루면서 같은 작업트리를 갱신하면 경쟁한다. 이미지 빌드 같은 긴 작업이 락을 오래 쥐는 것은 실측된 병목이 아니므로, **단순한 쪽을 택하고 병목이 관측되면 그때 쪼갠다.**

**락 획득은 상한을 둔 논블로킹이고, 실패는 물러섬이다.** 프로젝트 락을 잡는 모든 경로는 못 잡으면 무한 대기하지 않는다 — 주입은 `DEFERRED`를 반환하고(§5), tick은 이번 회차를 건너뛰며(다음 cron 주기에 재시도, cron overlap 락이 겹침을 이미 막는다), `progress commit`은 사람에게 "락 사용 중"을 알리고 종료한다. 주입이 락을 쥔 채 `wait_until_idle(timeout)`을 도는 동안(§7.3)이나 `leader up`이 이미지를 빌드하는 동안(수 분) 다른 경로가 기다리게 되지만, 논블로킹이라 교착이 아니라 물러섬으로 나타난다. 상한값은 실측된 병목이 아니므로 라이브 운용에서 조정한다.

**락과 이름공간은 호스트에 AXDT 프로젝트가 하나임을 전제한다.** 컨테이너 이름(`axdt-<식별자>`)과 tmux 세션(`axdt`)이 전역이고 root 성분이 없으므로(실측: `naming.py`·`tmux.py`), 프로젝트 락은 root별이어도 그것이 직렬화하려는 대상(공유 tmux 세션·전역 docker 이름공간)은 전역이다. 한 호스트에서 두 프로젝트를 돌리면 `list_leaders`가 서로의 Leader를 긁고 같은 식별자가 충돌한다. 다중 프로젝트 동거는 Phase 3의 이름공간에 root 성분을 넣어야 풀리며 본 Phase 범위 밖이다(§11 수용된 위험).

---

## 5. 모듈 계약

```python
# WIP/axdt/roles/spec.py  (순수)
class RoleKind(Enum):
    SESSION = "session"; SUBAGENT = "subagent"

class Capability(Enum):
    """플랫폼 중립 능력 등급. 어댑터가 각자의 인자로 번역한다(§2.3.1)."""
    READ_ONLY = "read-only"
    WRITE_WORKSPACE = "write-workspace"
    HOST_CONTROL = "host-control"

class Enforcement(Enum):
    """쓰기 제한이 실제로 무엇에 의해 지켜지는가(§2.3.2).
    능력(capability)이 아니라 writable_paths에 대한 등급이다."""
    MECHANICAL = "mechanical"   # 도구 부재·샌드박스
    GATED = "gated"             # 승인 게이트가 거부
    ADVISORY = "advisory"       # 프롬프트가 지시, 상위 주체의 리뷰가 잡음
    ABSENT = "absent"           # 기계도 게이트도 잡을 상위 주체도 없다

@dataclass(frozen=True)
class RoleSpec:
    name: str                       # leader|developer|reviewer|tester|maintainer
    kind: RoleKind
    capability: Capability
    enforcement: Enforcement
    rule_refs: tuple[str, ...]      # docs/sot/rule/ 의 id — 실재 검사 대상(§8)
    system_prompt: str
    model_hint: str | None          # 어댑터가 --model / -m 으로 전달
    writable_paths: tuple[str, ...] # 완전 경로. rule-role-responsibilities 표와 등가 대조(§8.2)

ROLES: Mapping[str, RoleSpec]       # 5종. watcher는 없다 — §2.4
SUBAGENT_ROLES: tuple[RoleSpec, ...]

# WIP/axdt/roles/prompts/<role>.md   시스템 프롬프트 본문 (spec.py가 읽어들임)
```

`ROLES`에 `watcher`가 없다. `RoleSpec`은 `kind`와 `system_prompt`를 요구하는데 본 Phase의 Watcher는 LLM이 아니고(§2.4) 세션도 sub-agent도 아니다. 없는 값을 지어내 채우느니 표에서 빼고, `§3`의 역할표에 비-`RoleSpec` 항목으로 적는다.

```python
# WIP/axdt/agent_runner/adapters/base.py  (확장)
class PlatformAdapter(ABC):
    # 기존: config_dir, format_prompt, detect_state
    @abstractmethod
    def capability_args(self, cap: Capability) -> list[str]:
        """능력 등급 → 플랫폼 인자(§2.3.1)."""

    @abstractmethod
    def prepare_subagents(self, workdir: Path, roles: Sequence[RoleSpec]) -> list[str]:
        """SUBAGENT 역할을 이 플랫폼 형식으로 준비하고, 세션에 실을 argv를 반환한다.
        Claude Code: --agents <json> 반환.
        Codex: 프로파일·프롬프트·rules를 workdir에 물질화하고 빈 리스트 반환
               (호출은 이미지에 심긴 axdt-subagent 래퍼가 한다, §2.3.3)."""

    @abstractmethod
    def build_session_command(self, role: RoleSpec, workdir: Path,
                              subagent_args: Sequence[str] = ()) -> list[str]:
        """SESSION 역할의 실행 argv — capability·system_prompt·model·subagents 포함."""

```

비대화형 1회 실행(`claude -p` / `codex exec`)을 감싸는 어댑터 메서드는 두지 않는다. 유일한 소비자가 될 뻔한 Watcher의 설계가 확정되지 않았고, 유력 후보 흐름에서는 그 호출이 필요 없다(§2.4). 필요해지면 Watcher 작업이 계약에 추가한다.

기존 `build_launch_command(workdir)`는 `build_session_command`로 대체된다 — 역할을 모르는 실행은 더 이상 없다. `AgentRunner.start_session(workdir, env)`이 내부에서 그것을 호출하므로(실측: `runner.py`), **`start_session(role, workdir, env)`으로 시그니처를 바꾸고** 어댑터 테스트·runner 테스트·`PLATFORM_MATRIX.md`를 함께 옮긴다. 공유 계약 변경이므로 소비자를 모두 갱신한다.

```python
# WIP/axdt/agent_runner/backend.py  (기존 ABC에 추가)
class SessionBackend(ABC):
    # 기존: start, send_text, read_new_output, is_alive, exit_code, last_error, stop

    @abstractmethod
    def send_key(self, key: str) -> None:
        """이름 붙은 키를 보낸다("Enter", "C-u"). 텍스트가 아니라 키 이벤트다.
        tmux 백엔드는 send-keys -t <win> <key>로 옮긴다 — **리터럴 -l을 쓰지 않는다.**
        기존 send_text는 send-keys -l로 문자열을 그대로 보내지만(실측: tmux.py),
        'Enter'·'C-u'는 키 이름이라 -l로 나가면 문자 그대로 타이핑된다."""

    @classmethod
    def attach(cls, *args, **kwargs) -> "SessionBackend":
        """이미 떠 있는 세션에 라이브 조회로 재결합한다(§2.5).
        붙을 대상이 없으면 NotStarted를 던진다.
        기본 구현은 NotImplementedError — 재부착 개념이 없는 backend가 있다."""

    @classmethod
    def post_mortem(cls, *args, **kwargs) -> tuple[int | None, str | None]:
        """죽은 세션의 종료코드와 마지막 오류를 조회한다.
        attach가 실패한 뒤 호출되므로 인스턴스가 없다 — classmethod여야 한다.
        **컨테이너가 실행 중이면(창만 사라진 반쪽 상태) 종료코드 대신
        (None, 'half-state: container alive')를 돌려준다** — 산 세션을 사망으로
        오판해 재기동하지 않도록(§2.5). 기본 구현은 NotImplementedError."""
```

`attach`·`post_mortem`을 `@abstractmethod`로 두지 않는다. 두면 `FakeBackend`가 즉시 깨지고(실측: 둘 다 없음), Fake는 프로세스 밖 상태가 없어 재부착도 사후 진단도 의미를 갖지 않는다. 기본 구현이 `NotImplementedError`를 던지고, 지원하는 backend가 덮어쓴다.

`post_mortem`이 `classmethod`인 이유는 §2.5가 요구한 그대로다 — `attach()`가 실패한 뒤에 부르는 함수이므로 붙은 인스턴스가 없다. 2차 개정본은 §2.5에 자유함수로, §5에 인스턴스 메서드로 적어 자기모순이었다.

**`submit()`·`clear_input()`은 backend가 아니라 runner에 둔다.** *어떤 키인가*는 플랫폼이 알고(`Ctrl-U`인가), *어떻게 보내는가*는 substrate가 안다(tmux `send-keys`). backend에 두면 substrate가 플랫폼을 알아야 한다. 그래서 backend는 이름 붙은 키를 보내는 `send_key`만 갖고, 어댑터가 키 이름을 주고, 둘을 합성하는 runner가 `submit()`·`clear_input()`을 노출한다. `FakeBackend`는 `send_key`만 구현하면 된다.

**`format_prompt`와 `send_prompt`를 함께 옮긴다.** `format_prompt`가 제출 개행을 떼면(docstring "including the submit newline" 삭제), `send_prompt`는 `send_text(format_prompt(text))`만 하므로(실측: `runner.py`) **영원히 제출하지 않는 함수가 된다.** `send_prompt`도 `submit()`을 부르게 고친다.

**그러면서 `send_prompt`의 게이트를 `IDLE` 단독으로 좁힌다.** 지금은 `INPUT_ACCEPTING = {IDLE, WAITING_INPUT}`을 받는데(실측: `runner.py`), 제출을 붙이는 순간 **`WAITING_INPUT`에 걸린 세션에 Enter를 눌러 권한 프롬프트를 승인하게 된다.** §4.1이 `clear_input` 때문에 세 문단을 들여 막은 바로 그 사고를, 이 함수가 뒷문으로 다시 연다. 권한 프롬프트에 답하는 것은 별도 동작이어야 하며 본 Phase에서 만들지 않는다(Phase 7).

`axdt maintainer send`·`leader send`의 자유 텍스트도 `inject()`를 거친다. `send_prompt`를 직접 부르는 CLI 경로를 두지 않는다.

```python
# WIP/axdt/agent_runner/adapters/base.py  (추가)
class PlatformAdapter(ABC):
    def submit_key(self) -> str: return "Enter"
    def clear_key(self) -> str: return "C-u"   # Esc 금지 — §4.1. 실제 값은 §8.3 측정
```

```python
# WIP/axdt/agent_runner/runner.py  (추가·변경)
class AgentRunner:
    @classmethod
    def attach(cls, adapter: PlatformAdapter, backend: SessionBackend) -> "AgentRunner":
        """attach된 backend 위에 runner를 구성한다. 캡처 로그의 마지막
        TAIL_WINDOW 바이트를 transcript로 시드하고 오프셋을 파일 끝에 둔다."""

    def submit(self) -> None:      # backend.send_key(adapter.submit_key())
    def clear_input(self) -> None: # backend.send_key(adapter.clear_key())

    def send_when_idle(self, text: str) -> bool:
        """직전 재폴링 → IDLE이면 clear_input → send_text → submit(§4.1).
        기존 send_prompt는 WAITING_INPUT도 받으므로(실측: INPUT_ACCEPTING)
        주입은 이 경로를 쓴다."""
```

##### 공유 계약 변경의 소비자 (전부 옮긴다)

| 변경 | 깨지는 곳 |
|---|---|
| `format_prompt`가 개행을 뗌 | `agent_runner/tests/test_adapters.py`(개행 기대값), `agent_runner/tests/test_runner.py`(`backend.sent == ["a\n","b\n"]`), `agent_runner/README.md`, `PLATFORM_MATRIX.md` |
| `PlatformAdapter`에 추상 3종 추가, `build_launch_command` 대체 | `adapters/claude_code.py`, `adapters/codex.py`, **`test_adapters.py`의 `BareAdapter`** — `build_launch_command`만 구현하므로 인스턴스화 불가가 된다 |
| `SessionBackend`에 `send_key` 추가 | `agent_runner/backend.py`의 `FakeBackend`, `infra/backend.py`의 `TmuxDockerBackend` |
| `infra/backend.py`의 인라인 ABC 제거 | `infra/tests/test_backend.py`의 `from axdt.infra.backend import SessionBackend` — 재수출하거나 import를 옮긴다 |
| `leader.up()`에 `platform` 필수, `PLACEHOLDER` 제거 | `infra/tests/test_leader.py` **6개 중 5개** — 전부 `up(tmp_path, i)`를 platform 없이 부르고, `env` fixture가 어댑터·`ROLES`를 모킹하지 않는다 |
| `cli.py`의 `leader up`에 `--platform` | `infra/tests/test_cli.py` — `--platform` 없이 호출한다 |
| `send_prompt`의 게이트를 `IDLE` 단독으로 좁힘 + `submit()` 호출 | `agent_runner/tests/test_runner.py`의 `test_send_prompt_accepted_in_idle_and_waiting_input`(실측: `WAITING_INPUT` 전송을 성공으로 기대) — `IDLE` 전용으로 갱신하고, 제출이 `submit()`으로 분리됨을 반영한다 |
| `progress commit`이 프로젝트 락을 잡음, cron은 별도 overlap 락 | `cli.py`의 `progress commit` 경로(실측: 현재 락 없음)에 프로젝트 락을 두르고, `cron.install` 호출부가 `lockfile=<root>/.axdt/cron.lock`을 넘긴다(`cron.py` 자체는 무변경) |

`--platform`은 **선택 인자에 기본값 `claude-code`** 로 둔다. 필수로 만들면 기존 CLI 호출이 전부 깨지고, D4가 요구하는 것은 "고를 수 있음"이지 "매번 적음"이 아니다.

```python
# WIP/axdt/protocol/message.py
KINDS = ("assign", "reject", "note")

def token(kind: str, task: str, body: str) -> str:
    """[axdt:<kind>:<task>:<hash8>] — 사람이 읽는 표식. 멱등 키가 아니다(§4.1)."""

def render_assign(task: str, plan: Path) -> str: ...          # 단일행
def render_reject(task: str, reason_commit: str) -> str: ...  # 단일행
def render_note(text: str) -> str: ...                        # 자유 텍스트, task="-"
```

```python
# WIP/axdt/protocol/inject.py
class InjectResult(Enum):
    SENT = "sent"                  # 제출 후 IDLE 이탈 관측
    UNCONFIRMED = "unconfirmed"    # 제출했으나 증거 미관측. 계측일 뿐 분기 아님(§4.1)
    DEFERRED = "deferred"          # BUSY·STARTING, 또는 락 획득 실패
    UNAVAILABLE = "unavailable"    # ERROR·STOPPED. 재기동이 먼저
    NEEDS_HUMAN = "needs_human"    # WAITING_INPUT. 승인이 걸려 있다

def inject(lock: ProjectLock, runner: AgentRunner, message: str, *,
           confirm_timeout_s: float) -> InjectResult:
    """poll_state 게이트 → 재폴링 → clear_input → send_text(본문) → submit → 이탈 관측.
    락을 잡지 않고 **이미 잡힌 것을 받는다** — 관측부터 제출까지가 한 임계구역이고,
    안에서 다시 잡으면 교착하거나 TOCTOU가 열린다(§7.3).
    캡처 로그를 읽지 않는다 — 멱등은 이 층에 없다(§4.1)."""
```

`SKIPPED`가 없다. `already_sent`도 없다. 멱등은 아래 수렴 층이 갖는다.

```python
# WIP/axdt/protocol/converge.py
@dataclass(frozen=True)
class Observation:
    task: str
    plan_exists: bool
    progress: str | None       # progress.md 행. 행이 없으면 None
    report: str | None         # recover.TaskState.report
    report_invalid: bool
    rework_pushed: bool | None # progress != rejected 면 None.
                               # progress == rejected인데 (a) 반려 커밋을 못 찾거나
                               # (b) 현재 자재화 report가 부재하거나 (c) 반려 커밋을
                               # 찾았지만 그 커밋 트리에 report 블롭이 없어 비교 불가면
                               # None (행 8). 세 경우 모두 '박제와 다름=참'으로 오판 금지.
    session: AgentState

def materialize_report(root: Path, task: str) -> Literal["ok", "absent", "unavailable"]:
    """허브 task 브랜치의 report 블롭을 작업트리에 자재화한다(§4.1). 결과를 셋으로 가른다.
    git fetch <허브경로> '+refs/heads/<BR>:refs/remotes/hub/<BR>' → git show > 임시파일
    → 성공 시에만 원자적 rename으로 대상 경로에 놓는다.
    - '+': force-push된 재작업을 버리지 않는다(강제 표식이 없으면 non-FF 거부, 실측: hub.py).
    - 명명 원격이 아니라 허브 경로: root 저장소에는 hub 원격이 없다(실측: workspace.py).
    - **원자적 쓰기**: `git show > 대상파일`을 직접 쓰지 않는다 — show가 실패해도 리다이렉트가
      실행 전에 대상을 0바이트로 절단해 'unavailable=작업트리 불변' 계약을 깬다(실측: 이 컴퓨터에서
      실패하는 show가 대상을 0바이트로 절단함을 재현). 임시 파일에 쓰고 show 성공 시에만 os.replace로
      rename한다. 임시 파일은 **대상과 같은 디렉터리**에 만든다 — 다른 파일시스템이면 rename이
      EXDEV로 실패하므로(호스트=Linux/WSL2 전제) /tmp에 만들어 작업트리로 옮기지 않는다.
    - 'ok': fetch 성공 + 경로가 트리에 존재(git cat-file -e refs/remotes/hub/<BR>:<path>로 확인)
      + show 성공. 임시파일을 원자적으로 대상에 놓는다.
    - 'absent': git ls-remote로 브랜치 부재를 확증했거나, fetch는 성공했는데 그 커밋 트리에
      경로가 없음(cat-file -e가 비영). 이때만 작업트리 파일을 **삭제**해 recover가
      (None,False)=부재를 보게 한다. 빈·낡은 파일은 무효(행 7)나 오판된 완료가 되므로 반드시
      지운다. 경로 부재는 show의 exit 128로 가르지 않는다 — 일시 실패도 exit 128이라 겹친다.
    - 'unavailable': 브랜치는 있는데 fetch가 실패(일시 오류). 작업트리를 건드리지 않는다.
      부재 브랜치도 일시 실패도 exit 128이라(실측) 종료코드로는 못 가르므로 ls-remote로 부재를,
      fetch 성공 후 cat-file로 경로 존재를 각각 확증하고, 그 확증에 실패한 것만 unavailable로
      둔다. 뭉개면 진행 중 report가 네트워크 한 번에 사라진다(6차의 M-3).
    **ls-remote의 부재 판정은 종료 코드가 아니라 출력으로 한다**(실측: 부재 브랜치 ls-remote는
    exit 0에 빈 출력, 접근 실패는 비영) — exit 0을 "존재"로 읽으면 부재를 놓친다.
    fetch는 작업트리를 갱신하지 않으므로 이것 없이는 recover가 낡은 파일을 읽는다."""

def probe_report_blob(root: Path, task: str) -> str | Literal["absent", "unavailable"]:
    """허브 task 브랜치 report 블롭의 git object-id만 읽어 온다 — **작업트리를 쓰지 않는다**(§7.4).
    git fetch <허브경로> '+refs/heads/<BR>:refs/remotes/hub/<BR>'
      → git rev-parse refs/remotes/hub/<BR>:<path>  (블롭 object-id, 파일 미기록)
    - object-id(str): 블롭 존재. §7.4 커밋 경로가 이 id를 사람의 attest 해시와 대조한다.
      대조를 통과하면 그 **object-id의 블롭을 내용 주소로 써 넣고**(git cat-file blob <id>,
      재fetch 없음) 스테이징한다 — materialize_report(성공 시 무조건 덮고 재fetch함)는
      대조용으로도 쓰기용으로도 쓰지 않는다(8차 M-1). object-id로 쓰므로 probe~쓰기 사이에
      허브가 바뀌어도 정확히 attest한 블롭이 박제된다.
    - 'absent': ls-remote로 브랜치 부재 확증(빈 출력), 또는 fetch 성공했는데 cat-file -e가 경로 부재.
    - 'unavailable': 브랜치는 있는데 fetch 실패(일시 오류). materialize_report와 같은 오라클로 가른다.
    **rev-parse는 반드시 종료 코드로 성공을 판정한다** — 실패 시(부재 등) exit 128이면서도
    stdout에 리터럴 인자를 에코하므로(실측), exit 미검사로 stdout만 읽으면 가짜 '해시'가 나온다.
    object-id는 내용 주소(SHA)라, 같은 내용은 같은 id·다른 내용은 다른 id다 — 바이트 동일성 대조를
    구성적으로 준다. status가 출력하는 해시도 같은 rev-parse 값이며, 같은 종료 코드 규율을 따른다."""

def observe(root: Path, task: str, session: AgentState) -> Observation | None:
    """materialize_report → recover.reconstruct → plan 존재 → rework_pushed.
    프로젝트 락 안에서 돌고 milestone commit에 선행한다 — 커밋이 자재화한 블롭을
    박제하기 때문이다(§4.1·§4.5·§7.4).
    materialize가 'unavailable'이면 신뢰할 Observation을 만들 수 없으므로 **None을
    반환한다** — 호출자는 이번 주기를 건너뛰고(다음 fetch에 자가 복구), 반복되면
    블로커로 올린다. 낡은 블롭으로 판단하느니 미룬다.
    progress 행이 없는 task는 reconstruct에 없으므로 progress=None으로 두고, report는
    자재화 후 직접 읽는다(행 12가 plan 유무로 블로커를 내지만 Observation은 일관되게
    채운다). 이를 위해 recover가 canonical report 읽기의 공개 접근자를 노출한다 —
    현재 _read_canonical_report는 비공개다.
    progress.md 자체가 파손돼 reconstruct가 ProgressFormatError를 던지면(실측: recover.py·
    table.py) None으로 뭉개지 않고 전파한다 — None은 '일시적 관측 불가라 이번만 건너뜀'인데
    파손은 그것과 달리 사람이 봐야 할 블로커이므로, 호출자가 관측 불가와 구별해 올린다."""

# 결정표의 출력은 세 갈래다. "보낼 것 없음"과 "사람을 불러야 함"은 다르다.
@dataclass(frozen=True)
class Instruction: message: str          # 배정 또는 반려
@dataclass(frozen=True)
class Blocker:     reason: str; obs: Observation
Decision = Instruction | Blocker | None  # None = 정상이고 할 일 없음

def needed_instruction(obs: Observation) -> Decision:
    """§4.1 결정표. 마지막 catch-all 덕에 구성상 전함수다."""

def rejecting_commit(repo: Path, task: str) -> str | None:
    """이 task를 rejected로 전이시킨 최신 마일스톤 커밋 sha. git log 라이브 조회.
    format_milestone_message는 두 형식을 낸다(실측: commit.py) — 단일 이벤트는
    subject `chore(progress): <task> <before>-><after>`(화살표 공백 없음), 배치는
    subject `batch N events` + 본문 `- <task>: <before> -> <after>`(공백 있음).
    파서는 (i) 두 형식 모두, (ii) after == 'rejected'인 전이만(재개 rejected->in-progress
    제외), (iii) task id 정확 앵커(`w1.t1-x`가 `w1.t10-x`에 걸리지 않게), (iv) 자유
    텍스트 `Reason:`·배치의 `Gates:` 하이픈 줄 배제(형태 앵커 `- <task>: <s> -> rejected`로
    자연 배제된다), (v) before 토큰이 `∅`일 수 있음을 허용한다 — 신규 행이 곧장 rejected면
    `<task> ∅->rejected`가 된다(실측: commit.py의 `_before_repr`). 여럿이면 최신을 쓴다.
    못 찾으면 None → Observation.rework_pushed = None → 행 8(블로커)."""

def rework_pushed(repo: Path, task: str, reject_sha: str) -> bool | None:
    """자재화한 report 블롭이 반려 커밋에 박제된 블롭과 다른가(§4.1).
    조상 관계로 풀 수 없다 — main과 task 브랜치는 어느 방향으로도 조상이 아니다.
    전제: 현재 report가 자재화되어 있다(observe가 'unavailable'이면 여기 오지 않는다).
    반환은 bool | None이다 — **반려 커밋 트리에 report 블롭이 없으면(git show
    <reject_sha>:<path> 실패) True가 아니라 None을 돌려준다**(→ 행 8 블로커). 이를 True로
    두면 §4.1이 이름 붙여 경고한 B-1 증상(반려가 재작업 완료로 오판돼 미전달)이 재발한다.
    현재 report가 확인된 부재인 경우도 observe가 이 함수를 부르지 않고 rework_pushed=None으로
    둔다(행 8) — 부재를 '박제와 다름=재작업'으로 오판하지 않기 위해서다."""

# commit 계약 변경(Phase 4): 반려에도 블롭 실재 게이트를 둔다.
# 현재 milestone_commit은 report를 exists()일 때만 스테이징하고(실측: commit.py),
# 과claim 검사(블롭 실재·status==done)는 accepted 이벤트에만 있다(실측: commit.py).
# rejected 이벤트에도 "report 블롭이 스테이징됐는가"를 요구해, 부재면 CommitRejected.
# 이 게이트는 report '실재'만 검사한다 — '낡음'·'리뷰 안 함'은 못 잡는다. 마일스톤 커밋이
# report를 작업트리에 추적 파일로 남기므로, 첫 회차 이후 흔한 오류는 부재가 아니라 낡은
# 파일의 잔존이다. 낡음/경합은 §7.4의 절차가 막는다 — 커밋 경로가 허브 블롭 object-id를
# 읽어(probe_report_blob) 사람이 넘긴 attest 해시와 대조하고, 다르거나 attest가 없으면
# CommitRejected로 거부한다. 즉 부재는 이 게이트가, 낡음/경합/리뷰스킵은 §7.4의 attest
# 대조가 방어한다. 블롭 없는·낡은·리뷰 안 한 반려 커밋이 rework_pushed 기준을 망치는 것을
# 둘이 함께 막는다.
#
# 스테이징 후 최종 대조(C-3): milestone_commit이 attest 해시 맵을 인자로 받는다 —
# 시그니처가 milestone_commit(repo, rejection_reasons, extra_paths, gates, reviewed=None)로
# 바뀌어, reviewed는 {task: attest_hash}이다(실측: 현재 시그니처엔 없다, commit.py:246).
# git add 뒤·git commit 전(과claim 검사와 같은 자리)에, 각 수용·반려 task의 인덱스 블롭 id
# (git rev-parse :<path>)가 reviewed[task]와 다르면 _unstage() 후 CommitRejected(과claim·
# ValueError 경로와 대칭, commit.py:335·342). git add의 clean 필터(autocrlf 등)가 report
# 바이트를 재인코딩하면 박제 블롭 ≠ 허브 블롭이 되어 rework_pushed가 영구 참이 되기 때문이다
# (§4.1·§7.4). 정상 경로는 .gitattributes의 `docs/interim/report/*.md -text`가 정규화를
# 꺼 항등이므로 이 대조는 통과한다. 검사는 반드시 커밋 전이어야 봉인이다(커밋 후면 반쪽 봉인).
```

**`Decision`이 세 갈래인 이유.** 2차~4차 개정본은 반환값을 `str | None`으로 두었는데, 그러면 표의 "없음 — 블로커"와 "없음 — 일하고 있다"가 **같은 값**이 된다. "실패가 관측 가능한 블로커가 된다"는 §4.1의 약속을 이행할 표면이 없었다. `Blocker`는 사유와 관측을 함께 실어 호출자가 사람에게 올릴 수 있게 한다(Phase 7이 메신저로 승격). `recover`의 `needs_attention`이 일부를 잡지만 전부는 아니다 — 예컨대 행 17(`report=in-progress`·`progress=in-progress`)는 정합성 매트릭스에서 `None`이라(실측: `schema.pair_severity`) 거기 잡히지 않는다. 세션 상태를 함께 보아야만 알 수 있는 이상이기 때문이다.

```python
# WIP/axdt/infra/backend.py
class TmuxHostBackend(SessionBackend):
    """컨테이너 없이 호스트 tmux 윈도우에서 세션을 구동한다(Maintainer).
    윈도우 이름은 상수 'axdt-maintainer', 캡처 로그는 capture_dir/maintainer.log."""

class TmuxDockerBackend(SessionBackend):
    # 추가: exit_code()    — docker inspect -f '{{.State.ExitCode}}'
    #       last_error()   — start/IO 실패 메시지
    #       send_key(key)  — tmux send-keys -t <win> <key>
    #       attach()       — tmux.resolve_window + container.is_running 라이브 조회.
    #       post_mortem()  — classmethod. attach 실패 후에 부른다

def list_leaders(root: Path) -> list[naming.Identifier]:
    """알려진 Leader를 라이브 조회로 열거한다. 상태 저장소가 없으므로 필수다.
    **죽은 것도 포함한다** — `docker ps -a`(종료된 컨테이너는 --rm이 없어 잔존한다,
    실측: container.run_args)와 tmux 윈도우의 합집합. 살아 있는 것만 세면
    watcher tick이 정작 보고해야 할 죽은 세션을 못 본다.
    **이름공간이 전역이라 root로 필터할 수 없다** — 컨테이너 `axdt-<id>`·tmux 세션
    `axdt`에 root 성분이 없다(실측: naming.py·tmux.py). 본 Phase는 호스트에 AXDT
    프로젝트 하나를 전제한다(§4.5·§11). 다중 프로젝트는 Phase 3 이름공간 변경이 필요하다."""
```

**플랫폼 식별자는 저장되지 않으므로 매번 전달해야 한다.** `attach`·`restart`·`inject`는 모두 어댑터를 필요로 하는데, 상태 저장소가 없고(`ADR-0002`) workspace는 평범한 clone이며 컨테이너 이미지는 하나뿐이다(실측: `container.py`의 단일 이미지). 어댑터 선택은 런타임 argv에만 존재한다. 따라서 `leader send/assign/reject/restart`와 `maintainer send`가 모두 `--platform`을 받고, 기본값은 `claude-code`다. `restart(root, i, *, platform)`도 같다.

컨테이너의 실행 명령에서 되읽는 라이브 조회(`docker inspect`의 `Cmd`)도 `ADR-0002`에 부합하는 대안이지만, 명령줄에서 플랫폼을 역추론하는 것이 안정적인지는 확인하지 않았다. **측정 대상**으로 두고 지금은 명시 전달을 쓴다.

```python
# WIP/axdt/infra/leader.py  (변경)
def up(root, i, *, platform: str = "claude-code", reuse_workspace: bool = False, ...) -> TmuxDockerBackend:
    """reuse_workspace=True면 provision()을 건너뛰고 workspace 실재·브랜치만 검증한다.
    provision()은 멱등이 아니라 기존 workspace에 FileExistsError를 던진다(실측).
    PLACEHOLDER를 제거하고 세션 명령을 어댑터로 조립한다:
        sub_args = adapter.prepare_subagents(cwd, SUBAGENT_ROLES)
        argv     = adapter.build_session_command(ROLES["leader"], cwd, sub_args)
    platform 인자가 필요한 이유는 어댑터를 고르기 위해서다(D4). 현재 up()에는 없다."""

def down(root, i, *, force: bool = False, keep_workspace: bool = False) -> None:
    """keep_workspace=True면 stop()만 하고 teardown을 건너뛴다."""

def restart(root, i, *, platform: str = "claude-code") -> TmuxDockerBackend:
    """down(keep_workspace=True) → up(reuse_workspace=True). 짝을 강제한다(§4.5).
    reuse_workspace=True이므로 start 실패 시 보상 teardown을 하지 않는다.
    호출 전에 프로세스의 실제 죽음을 확인해야 한다 — 마커 ERROR는 근거가 아니다(§4.5)."""
```

`PLACEHOLDER` 제거는 `infra/tests/test_leader.py`의 `test_up_uses_placeholder_command_by_default`를 깨뜨린다. `up()`의 시그니처 변경은 `cli.py`의 `leader up` 파서를 함께 바꾼다.

---

## 6. CLI 확장 (`cli.py`)

```
axdt maintainer up [--platform claude-code|codex]   호스트 tmux에 Maintainer 세션 기동
axdt maintainer down                                 세션 정리
axdt maintainer send <text>                          note 주입 (수동 조작·디버깅용)
axdt leader up <identifier> --platform <p>           workspace provision + 세션 기동
axdt leader send <identifier> <text>                 attach 후 note 주입
axdt leader assign <identifier>                      plan을 읽어 배정 메시지 생성·주입
axdt leader reject <identifier> --commit <sha>       반려 사유가 담긴 커밋을 가리킨다
axdt leader restart <identifier>                     down(keep_workspace) → up(reuse_workspace)
axdt watcher tick                                    cron 진입점 (§2.4의 최소 Watcher)
axdt roles show [<role>]                             역할 선언 덤프
axdt roles check                                     §8 계약 검사를 수동 실행
```

`leader up`에 `--platform`이 생긴다. 현재는 없고(실측: `WIP/axdt/cli.py`), 어댑터를 고를 수 없으면 `build_session_command`를 부를 수 없다. task별 플랫폼 선택은 D4가 정한 요구사항이다.

**기존 `axdt tmux send --submit`을 새 제출 규약으로 옮긴다.** 지금은 `text + "\n"`을 `send_text`에 넘기므로(실측: `cli.py`) paste-buffer 경로를 타고, 제출 여부가 §4.1이 없애기로 한 바로 그 미측정 동작에 걸린다. `send_key(adapter.submit_key())`로 바꾼다. 그러지 않으면 제출 규약이 둘로 갈린다.

`assign`·`reject`는 §4.1의 수렴 판정을 먼저 거친다. 지시가 필요 없으면 아무것도 보내지 않고 그 사실을 출력한다. 강제로 보내려면 `send`로 `note`를 쓴다 — 그것은 사람의 책임이다.

`axdt watcher tick`이 `cron.install(watcher_cmd=...)`의 대상이다(실측: Phase 3의 `cron.install`이 명령 문자열을 요구한다). **LLM을 부르지 않고, 아무것도 죽이지 않고, `docs/` 아래 어떤 파일도 쓰지 않는다.** 프로젝트 락(`<root>/.axdt/lock`)을 프로세스 내부에서 잡는다 — cron이 감싸는 overlap 락(`<root>/.axdt/cron.lock`)과 **별개 파일**이라 자기 래퍼와 충돌하지 않는다(§4.5). 그다음 `list_leaders()`로 Leader를 라이브 조회하고, 각각에 `attach`를 시도한다. 붙지 못하면 `post_mortem()`으로 종료코드를 얻되, `post_mortem`이 "실행 중"을 돌려주면 사망이 아니라 이상으로 보고한다(§2.5). 결과는 **stdout으로 출력하고 cron 로그가 받는다.** 죽은 세션이 있으면 비영(非零) 종료코드로 알린다.

진단 출력을 `docs/interim/`에 쓰지 않는 이유는 쓸 자리가 없기 때문이다. `progress.md`는 Maintainer 단독 작성이고(`rule-progress-single-writer`), report는 Leader의 자기보고 파일이다. Watcher가 합법적으로 쓸 경로가 없으므로 **쓰지 않는다.** 재기동·압축·판단은 하지 않는다 — 그것을 누가 어떤 근거로 하는지가 §2.4의 별도 작업이 답할 질문이다.

---

## 7. 절차

**락은 절차 진입 시 한 번 잡는다.** `inject()`가 자기 안에서 같은 락을 다시 잡으면, 비재진입 파일락에서는 교착하고 재진입 락에서는 관측과 주입 사이가 락 밖으로 새어 TOCTOU가 된다. 따라서 `inject()`는 **이미 락을 쥔 호출자로부터 락 핸들을 받는다.** 관측(4단계)부터 제출(6단계)까지가 한 임계구역이어야 한다 — 그 사이에 Leader가 재기동되면 죽은 창에 키를 쏜다.

### 7.1 Leader 기동
1. Maintainer가 `docs/interim/plan/task/<task>.md`를 쓴다.
2. `leader.up(root, i, platform=...)` — workspace provision → `prepare_subagents` → 컨테이너·tmux 기동.
3. `wait_until_idle(timeout)` 후 `axdt leader assign <identifier>`.

### 7.2 Leader 재기동 (세션 사망)
1. `leader.restart(root, i)` — 내부적으로 `down(keep_workspace=True)` → `up(reuse_workspace=True)`.
   - `down`이 `teardown`을 건너뛰므로 미push 커밋이 있어도 던지지 않고 workspace도 지우지 않는다.
   - `up`이 `provision`을 건너뛴다. 건너뛰지 않으면 `FileExistsError`로 죽는다(실측: `provision`은 멱등이 아니다).
2. 재기동된 Leader는 대화 맥락 없이 시작한다. 자기 workspace의 git 상태와 `progress.md`에서 스스로를 복구한다. 미커밋 파일은 바인드 마운트라 그대로 있다.
3. 다시 주입할 지시를 기억할 필요가 없다. 다음 수렴 판정이 관측에서 도출한다(§4.1).

### 7.3 Leader에 지시 주입 (다른 프로세스에서)
0. 프로젝트 락(`<root>/.axdt/lock`)을 잡는다. 아래 전부가 한 임계구역이다.
1. `be = TmuxDockerBackend.attach(i, root)` — `resolve_window`와 `container.is_running`을 **직접** 조회한다. backend는 플랫폼을 모르므로 여기 `platform`을 넘기지 않는다(플랫폼은 2단계 어댑터로 간다). 인스턴스 `status()`를 쓰지 않는다(§2.5: 새 인스턴스에서는 라이브 조회 전에 `NOT_STARTED`를 반환한다). 붙지 못하면 `post_mortem(i, root)`로 사인을 얻어 세 갈래로 가른다(§2.5) — **종료 코드가 실린 정상 사망**이면 §7.2 재기동으로, **"실행 중"(half-state)**이면 재기동 아닌 블로커로, **"gone"(창·컨테이너 모두 없음)**이면 이미 정리된 상태이므로 재기동하지 않고 정리됨으로 보고한다(§7.2로 넘기지 않는다 — 의도적으로 내려 둔 Leader를 되살리지 않는다). "gone"에도 재기동이 필요한 상황이면 workspace가 없어 `restart`의 `up(reuse_workspace=True)`가 `FileNotFoundError`로 정직하게 멈춘다.
2. `runner = AgentRunner.attach(adapter, be)` — 어댑터는 `platform`으로 고른다.
3. `st = runner.wait_until_idle(timeout)` — attach 직후의 첫 `poll_state()`는 마커가 시드 창 밖일 수 있어 신뢰하지 않는다(§2.5). `IDLE`이 아닌 채 시간이 다하면 상태를 가른다:
   - `ERROR`·`STOPPED` → `is_alive()`로 실제 죽음을 확인한다(§4.5). 죽었으면 §7.2 재기동으로, **살아 있는데 마커가 `ERROR`면 블로커로** 올린다(재기동 아님). 이 확인이 결정표에 `ERROR`를 넘기기 전의 관문이다.
   - `BUSY`·`STARTING` → `DEFERRED`. `WAITING_INPUT` → `NEEDS_HUMAN`. 주입하지 않는다.
4. `obs = converge.observe(root, task, runner.poll_state())` — **fetch와 report 자재화가 여기 들어 있다.** materialize가 milestone commit에 선행하도록 이 임계구역 안에서 돈다(§4.1). **`observe`가 `None`(관측 불가 — 일시적 fetch 실패)이면 `DEFERRED`로 물러선다** — 낡은 관측으로 지시를 만들지 않는다. 다음 주기가 재시도한다.
5. `d = converge.needed_instruction(obs)`.
   - `None` → 보낼 것이 없다. 끝.
   - `Blocker` → 사람에게 올린다(Phase 7). 주입하지 않는다.
   - `Instruction` → 6번으로.
6. `res = inject(lock, runner, d.message, confirm_timeout_s=...)`.
7. `UNCONFIRMED`는 진단 로그에만 남긴다. 다음 주기의 관측이 필요한 지시를 다시 도출한다. 재시도 상한은 호출자의 몫이다(§4.1).

### 7.4 Maintainer의 수용/반려 (마일스톤 커밋)

6차가 무너진 자리이고, 7·8차가 그것을 고치려다 두 번 **새 자리를 열었다.** 6차는 "materialize는 커밋에 선행한다"는 §4.1의 불변식을 **실행하는 절차 없이 서술로만** 두어, `axdt progress commit`이 허브 fetch 없이 작업트리에 이미 있는 report만 스테이징하므로(실측: `commit.py`가 `report_path.exists()`일 때만) 커밋 시점 report가 부재·낡음이면 블롭이 안 실려 반려가 영구 미전달됐다. 7차 초안은 이를 "락 안에서 materialize→사람 판단→편집→커밋을 한 임계구역"으로 못박았는데, **그 임계구역은 실현 불가능하다.** `commit.py`는 판단도 progress.md 편집도 하지 않고 "호출자가 이미 반영해 뒀다"고 가정하므로(실측: `commit.py:20`·`254`), 사람의 판단·편집 시간이 프로젝트 락(flock) 안에 들어갈 방법이 없다(Codex C-1). 8차는 판단을 락 밖으로 빼고 "작업트리에 남은 자재화본"을 리뷰본으로 삼아 커밋이 재자재화본과 대조하게 했으나, **그 리뷰본이 공유 가변 파일이라 판단 창(락 밖) 동안 다른 materialize 경로가 덮어쓴다** — §7.3 주입의 `observe()`가 지시 필요 여부와 무관하게 그 task의 report를 재자재화하고(§5), 무인자 `progress status` 재실행도 같은 파일을 갱신하며, §4.5는 이미 "다중 주입자가 같은 작업트리 report를 경쟁적으로 덮는" 동시성 모델을 전제한다. 그 결과 사람이 R1을 리뷰하고 커밋 전에 파일이 R2로 덮이면 커밋이 R2==R2로 통과해 **리뷰 안 한 R2가 박제·수용된다**(세 모델 만장일치 치명). 9차는 리뷰 기준을 **덮일 수 있는 파일에서, 사람이 명령줄로 옮기는 내용 해시(attest)로** 옮겨 이 창을 닫는다.

**핵심: 사람의 판단은 락 밖에서, 락은 "재fetch→해시 대조→스테이징→커밋"의 짧은 기계 구간만 감싼다. 커밋이 박제하는 블롭은 반드시 사람이 attest한 그 블롭이며, 그 기준은 작업트리 파일이 아니라 사람이 넘긴 해시다.**

절차는 세 걸음이고 진입점이 둘이다.

1. **리뷰 (`axdt progress status <task…>`, 짧은 락 세션).** 대상 task의 report를 허브에서 fresh하게 materialize하고(§4.1의 원자적 쓰기), `recover.reconstruct`로 상태와 함께 **각 task의 report 블롭 내용 해시(git object-id, 예: `git rev-parse refs/remotes/hub/<BR>:<path>`)를 출력한** 뒤 **락을 놓는다.** 사람이 판단하는 것은 이 자재화본이고, 그 정체성은 출력된 해시로 고정된다. materialize가 `unavailable`(일시적 fetch 실패)이거나 `absent`인 task는 해시 대신 그 상태를 표시한다 — attest 해시가 없으면 그 task는 이번 커밋 대상이 못 되고, 다음 회차가 재시도한다(안전 방향). 범위: **모집합은 작업본 `progress.md`의 행(신규 행 포함) ∪ 명시 인자**이고, 거기에 **HEAD 기준 종결 필터**를 씌운다 — `HEAD의 progress.md`에서 `accepted`·`superseded`인 task는 인자로 명시해도 materialize하지 않는다(이미 커밋된 report를 재자재화·삭제하지 않기 위해). 인자가 없으면 그 모집합의 비-종결 전부를, 인자가 있으면 그 안에서 좁혀 materialize한다. **모집합을 HEAD가 아니라 작업본 행으로 잡는 이유**: `∅→rejected`처럼 HEAD에 행이 없는 신규 task(실측: `rejecting_commit` 파서가 `∅` before를 지원)도 사람이 작업본에 행을 넣거나 인자로 명시하면 리뷰 대상이 되어 해시를 얻을 수 있어야 하기 때문이다 — HEAD 행만 열거하면 그 task가 스코프 밖이라 attest 해시를 못 얻어 커밋이 막다른 길이 된다. 종결 여부만 HEAD로 판정하므로, 수용으로 *편집 중*(작업본은 accepted, HEAD는 아직 비-종결)인 task는 스코프에 남아 재실행 루프가 생기지 않는다(실측: 현재 `cli.py`의 `progress status`는 task 인자도 materialize도 없이 `recover.reconstruct` 직행 — 인자·materialize·해시 출력을 더한다).
2. **판단·편집 (락 없음).** 사람이 1의 자재화본을 보고 수용·반려를 정하고, `progress.md`를 갱신한다(수용→`accepted`, 반려→`rejected`+사유). 자기가 리뷰한 report의 해시를 기억해 둔다. 여기에 락을 쥐지 않는다 — 판단은 얼마든 길 수 있다.
3. **커밋 (`axdt progress commit --reviewed <task>=<hash> …`, 프로젝트 락 안).** 아래 전부가 한 임계구역이고, 사람의 판단이 여기 들어오지 않으므로 짧다.
   - **diff로 변경 task를 확정한다.** `base`(HEAD progress.md)와 편집된 작업트리 progress.md를 비교해 상태가 바뀐 task 집합을 얻는다(실측: `commit.diff_progress`). "materialize할 대상"이 사람의 편집 *결과*로 정해지므로 닭-달걀이 사라진다.
   - **그 task 중 수용(→`accepted`)·반려(→`rejected`)는 report 블롭에 의존하므로 attest 해시와 허브를 대조한다**(그 밖 전이 `blocked`·`paused`·`superseded`는 블롭 게이트가 없다). 배치(여러 task 동시 수용·반려)에서는 **모든 대상 task의 대조를 먼저 마치고 전부 통과한 뒤에 쓰기·커밋한다** — 한 task가 실패하면 아무 것도 쓰지 않아 부분 쓰기가 남지 않는다. **diff의 수용·반려 집합에 없는 task의 `--reviewed`는 오류로 거부한다**(오타·잘못 붙인 attest를 조용히 무시하지 않는다). 각 대상 task에 대해:
     - `--reviewed <task>=<hash>` **attest가 없으면** → `CommitRejected`("리뷰를 먼저 하라 — `progress status <task>`로 해시를 확인하라"). 리뷰를 건너뛴 커밋을 막는다.
     - 허브 task 브랜치를 fetch하고 **읽기 전용으로 report 블롭의 object-id만 얻는다**(`git rev-parse refs/remotes/hub/<BR>:<path>` — 작업트리를 쓰지 않는다, §5의 `probe_report_blob`). 확인된 부재면 → `CommitRejected`("report가 허브에 없다 — 없는 report는 수용·반려할 수 없다"). 일시적 fetch 실패면 → 이번 회차를 미룬다(낡은 판단 금지).
     - 그 object-id가 **attest 해시와 다르면** → `CommitRejected`("리뷰 후 report가 바뀌었다 — `progress status <task>`로 새 해시를 확인하고 다시 판단하라"). 리뷰 이후 Leader가 새 report를 push한 경우다. **기준이 작업트리 파일이 아니라 사람이 넘긴 해시이므로, 판단 창 동안 다른 경로가 작업트리 파일을 덮었든 무관하다** — 이것이 8차 치명을 닫는 지점이다.
     - object-id가 attest 해시와 **같으면** → **그 object-id의 블롭을 내용 주소로 그대로 써 넣는다**(`git cat-file blob <id> > 임시파일` → 원자적 rename). `materialize_report`로 **재fetch하지 않는다** — probe의 fetch와 재fetch 사이에 Leader가 또 push하면 재fetch가 attest와 다른 블롭을 쓸 수 있기 때문이다(락은 다른 axdt 프로세스만 막지 컨테이너 안 Leader의 허브 push는 막지 못한다). object-id로 쓰면 그 사이 허브가 어떻게 바뀌든 정확히 attest한 그 블롭이 박제된다. 이 순서(대조 먼저, 쓰기 나중)라 커밋이 대조 전에 작업트리를 덮는 일도 없다.
   - `commit.milestone_commit`을 부른다. 이 함수는 `git add`(스테이징) → 검사 → `git commit`을 한 단위로 하며(실측: `commit.py`가 `git add`·과claim 검사·`git commit`을 차례로 수행), 방금 놓은 report가 작업트리에 있으므로 스테이징된다. 두 검사를 **`git add` 뒤·`git commit` 전**에 둔다(과claim 검사와 같은 자리, 실패 시 `_unstage()` 후 `CommitRejected`):
     - **rejected 블롭 실재**: `commit`은 rejected 이벤트에도 report 블롭 실재를 요구한다(§5) — 수용의 과claim 검사(실측: `commit.py`가 `accepted`에만 블롭·`done`을 확인)를 반려에도 대칭으로 두어, 블롭 없는 반려 커밋이 조용히 성립하지 못하게 한다.
     - **인덱스 블롭 = attest (C-3 봉인)**: `git add`는 clean 필터(특히 `core.autocrlf` 줄끝 정규화)를 적용할 수 있어, `cat-file`로 쓴 바이트와 인덱스에 담긴 블롭이 달라질 수 있다. 각 수용·반려 task에 대해 `git rev-parse :<path>`(인덱스 블롭 id)가 attest 해시와 **다르면 `_unstage()` 후 `CommitRejected`**("스테이징이 report를 재인코딩했다 — `.gitattributes`로 report 경로를 `-text` 처리하라"). 이 검사는 반드시 `git commit` **전**이어야 봉인이다 — 커밋 뒤면 재인코딩된 블롭이 이미 박제된 반쪽 봉인이 된다. 정상 경로에서는 아래 `.gitattributes`가 정규화를 끄므로 항등이고, 이 한 줄이 기계 등급으로 "인덱스 블롭 = attest 블롭 = 사람이 리뷰한 블롭"을 보증한다. 이것 없이는 CRLF report(parser가 허용, 실측: `table.py`)가 정규화돼 박제 블롭 ≠ 허브 블롭이 되고, `rework_pushed`가 매 주기 참이 되어 반려가 영구 미전달된다(C-3, byte-오라클의 잠복 취약점). 이를 위해 `milestone_commit`은 수용·반려 task의 attest 해시 맵을 인자로 받는다(§5 계약 변경).
   - **락을 놓는다.**

이 절차가 세 리뷰의 지적을 닫는다. 사람의 판단이 락 밖이므로 "판단이 임계구역에 못 들어간다"가 풀리고(7차 Codex C-1), diff가 편집 결과로 변경 task를 확정하므로 순서의 닭-달걀이 풀리며(7차 Fable M-C), **대조 기준이 덮일 수 있는 작업트리 파일이 아니라 사람이 명령줄로 넘긴 해시이므로, 판단 창 동안 §7.3 주입·status 재실행이 작업트리 report를 덮어도 커밋은 여전히 "사람이 attest한 블롭"과 허브를 대조한다**(8차 만장일치 치명). 해시가 사람의 명령 인자로만 흐르므로 `ADR-0002`(무 저장소)와 충돌하지 않는다. 대조는 git object-id(내용 주소)라 바이트 동일성을 구성적으로 보장한다. 리뷰를 건너뛰면 attest가 없어 거부되고, 리뷰 후 Leader가 바꾸면 해시 불일치로 거부된다. **수용된 한계**: 사람이 리뷰하지 않고 현재 허브 해시를 그대로 attest하면 통과한다 — 메커니즘은 "커밋 블롭 = attest 블롭"을 보장할 뿐 사람의 실제 열람을 강제하지 못한다(최종 게이트가 사람의 정직한 판단이라는 §4.1 전제와 같은 수준의 신뢰다).

주입 경로(§7.3)와 이 커밋 경로는 **다른 진입점**이다(`axdt leader assign` 계열 ↔ `axdt progress status`+`progress commit`). 전자는 Maintainer→Leader 하향 지시, 후자는 상향 판정이다. **현재 `cli.py`의 `progress commit`은 락도 materialize도 대조도 없이 `milestone_commit` 직행이므로(실측: `cli.py:143`~`166`, 인자는 `--reason`·`--gate`·`--dry-run`뿐), 락·재fetch·`--reviewed` attest 대조를 더하는 것이 본 절차의 구현이다.** `progress status`에는 task 인자·materialize·해시 출력을 더한다(실측: `cli.py:133`~`140`).

---

## 8. 검증 전략

### 8.1 배선 회귀 테스트 (`FakeBackend`, CI)

초안은 이것을 "세로축 한 바퀴 검증"이라 불렀다. **과장이었다.** 가짜 백엔드 위에서 "Leader가 report를 쓴다"는 부분은 테스트 코드가 직접 파일을 써 넣는 것이므로, 확인되는 것은 모듈 경계의 호출 순서·타입·거부 범위뿐이다. 실제 전달 의미론과 상태 마커 정확도는 이 층이 잡지 못한다.

정직한 이름은 **배선 회귀 테스트**다. 그 이름으로 다음을 고정한다.

- `inject()` 상태별 분기 5종. `SKIPPED`는 존재하지 않는다.
- **`needed_instruction()`의 전함수성과 상호배타성** — 모든 (plan × progress 9종 × report {부재,무효,5종} × rework × session 6종) 조합에 정의된 결과가 있고, 고정 평가 순서에서 첫 일치가 유일하다(각 행 조건이 앞 행 배제 하에 정의역을 좁힌다). **`progress` 분할 네 구간(종결·보류/반려/행없음/착수=행 14~17) 사이는 재정렬해도 결과가 같음**을 고정하되, **두 행은 순서 의존임**을 함께 고정한다: (a) **무효 행(행 7)** — `report`축 조건이라 종결·보류 뒤, 그리고 `report` 열이 `—`인 모든 구간(반려·행없음)과 착수 앞이 아닌 곳으로 옮기면 결과가 바뀐다. 반례 셋: `rejected`·무효를 반려 뒤로 옮기면 반려 발송, `accepted`·무효를 종결·보류 앞으로 옮기면 블로커, **`(plan=없음, 행없음, 무효)`를 행없음 뒤로 옮기면 행 13이 삼켜 `None`(고아 깨진 report 무신호 방치)**. (b) **catch-all 행(행 18)** — 전정의역을 받으므로 맨 마지막이 아니면 다른 행을 삼킨다(반례: 착수 블록과 함께 반려 앞으로 옮기면 `rejected`·`done`·`거짓`이 행 11 대신 행 18에 걸려 블로커가 된다). 즉 "행 7·18을 뺀 네 구간 재정렬 불변" + "행 7 위치 고정(종결·보류 뒤, 반려·행없음·착수 앞)" + "행 18 최후 고정"의 세 성질로 나눠 검증한다(재정렬 불변을 행 7이나 18까지 포함해 주장하면 테스트가 거짓이 된다).
  - `report_invalid=True`가 report 기반 판단을 앞서 블로커가 되는 것 (행 7). "report 부재"로 뭉개지지 않는다.
  - **반려 구간(행 8~11)이 report 기반 행(행 14·15)보다 먼저 평가되는 것** — `progress=rejected`·`report=done`·`IDLE`이 행 15("수용 판단")에 가리지 않고 반려 구간에 도달해 반려를 낸다(행 11). 5차 치명의 회귀.
  - **재작업 중 새 블로커·중간 정지가 가려지지 않는 것** — `progress=rejected`·`rework_pushed=참`·`report=blocked`(새 블로커)가, 그리고 `report=todo`·`in-progress`(재작업 중 정지, 행 17과 대칭)가 **행 9(블로커)**를 내고 행 10(수용 대기 `None`)에 가리지 않는 것. 6차 M-4 + Codex 8차 지적의 회귀. 오직 `report=done`만 행 10(`None`)이다.
  - `rework_pushed=참`·`report=done` → `None`(행 10), `거짓` → 반려(행 11), 반려 커밋 못 찾음·현재 부재·**반려 커밋 트리에 블롭 없음** → `None` → 블로커(행 8). `rework_pushed`의 반환이 `bool | None`이라 세 번째 사유(반려 커밋 블롭 부재)를 `참`이 아니라 `None`으로 내는 것(음성 테스트: `참`이면 B-1 재발).
  - **progress 행 없음이 report 기반 행에 가려지지 않는 것** — `progress=None`·`report=done`·plan 있음이 행 15에 가리지 않고 행 12(블로커)를 내는 것. 6차 M-2의 회귀.
  - `progress=blocked`·`paused`에 plan이 남아 있어도 배정이 나가지 않는 것 (행 6).
  - `progress=todo`·`in-progress` · report 부재 · plan 있음 → 배정 (행 16).
  - `progress`·`report` 둘 다 `in-progress` → `Blocker` (행 17). `schema.pair_severity`는 이 조합을 `None`으로 두므로(실측) `recover`만으로는 잡히지 않는다.
  - `session=ERROR` → `Blocker` (행 4), `session=STOPPED` → `None` (행 3). 표만으로는 crash와 마커를 못 가르므로, §7.3의 `is_alive` 관문이 죽음을 재기동으로 먼저 보내는 것도 함께 고정한다(M-1).
  - 행 18 catch-all이 예상 못 한 조합(예: `in-review`·report 부재)을 `None`이 아니라 `Blocker`로 올리는 것.
  - `Blocker`와 `None`이 구별되는 것 — 반환 타입이 세 갈래인 이유다.
- **주입자 크래시 후 수렴** — `send_text` 후, `submit()` 후, 증거 관측 전 각 지점에서 죽였을 때, 다음 `needed_instruction()`이 관측만으로 옳은 지시를 다시 만들어 내는 것. 이것이 유실 구멍의 회귀 테스트이며, 2차 개정본의 토큰 오라클로는 **작성 자체가 불가능했다.**
- **배정 재전송이 수렴하는 것** — 배정 후 Leader가 수신 확인(`report=in-progress`)을 push하면 다음 주기가 배정을 멈춘다(관측이 바뀐다). 확인 못 하고 report가 여전히 부재면 다음 주기가 **다시 배정**한다(라이브락 아님 — 재전송은 무해하고 상한은 호출자 몫이다, §4.1). report가 `in-progress`로 **존재하는데** 멈춘 경우만 블로커다(행 17). *배정을 `progress`에 기록해 라이브락을 막는 경로는 없다 — 폐기됐다.*
- `observe()`가 `reconstruct` 전에 허브 fetch를 하는 것. fetch를 빼면 완료된 task에 배정이 재발화하는 것(음성 테스트). **refspec에 `+`가 있어 force-push된 report를 가져오는 것** — `+`를 빼면 amend·force-push한 재작업이 반영되지 않아 `rework_pushed`가 `거짓`에 묶이는 것(음성 테스트, 치명 3의 회귀).
- **`materialize_report`가 확인된 부재와 관측 실패를 가르는 것** — `git ls-remote`로 브랜치 부재를 확증한 경우만 작업트리 report를 지워 `recover`가 `(None,False)`를 보게 하고(치명 2의 회귀), 브랜치는 있는데 fetch가 실패(일시 오류)하면 지우지 않고 `observe`가 `None`(관측 불가)을 반환해 그 주기를 건너뛰는 것(6차 M-3의 회귀). 지우면 진행 중 report가 네트워크 한 번에 사라진다.
- **커밋 경로가 attest 대조를 선행하고 그 통과 블롭을 박제하는 것(§7.4, 6차 B-1 치명의 회귀)** — 수용/반려의 커밋 단계(`progress commit`)가 락 안에서 허브 블롭 object-id를 읽어 attest 해시와 대조하고, 통과한 object-id의 블롭을 `cat-file`로 써 넣은 뒤(재fetch 없음) `milestone_commit`을 불러 그 블롭을 박제하는 것. 대조·박제를 빼면 반려 커밋에 블롭이 없어 다음 주기의 `rework_pushed`가 `참`(재작업 끝)으로 오판해 반려가 미전달되는 것(음성 테스트). 그리고 **`commit`이 rejected 이벤트에도 report 블롭 실재를 요구해**, 블롭 없는 반려 커밋이 조용히 성립하지 않고 `CommitRejected`가 되는 것(수용의 과claim 대칭). **스테이징 후 인덱스 블롭 id가 attest와 다르면 `CommitRejected`인 것(C-3의 회귀)** — `core.autocrlf=true`에서 CRLF report를 add하면 인덱스가 재인코딩돼 박제 블롭 ≠ 허브 블롭이 되고, 이 최종 대조가 없으면 `rework_pushed`가 영구 참이 되어 반려가 미전달되는 것(음성 테스트: `.gitattributes`의 `-text` 없이 CRLF report로 재현).
- **§7.4의 판단-락밖 / diff-선행 / attest-대조(7차 C-1·8차 C-2 치명의 회귀)** — (a) 사람의 판단·`progress.md` 편집이 프로젝트 락 밖에서 일어나고 락은 재fetch→대조→커밋의 짧은 구간만 감싸는 것. (b) 커밋 단계가 편집된 progress.md의 diff로 변경 task를 확정한 뒤 그 task만 대조하는 것(닭-달걀 없음). (c) **`--reviewed <task>=<hash>` attest가 없으면 `CommitRejected`(리뷰 스킵 차단)**, **허브 블롭 object-id가 attest 해시와 다르면 `CommitRejected`(리뷰 후 변경)**로 거부하는 것 — 핵심 음성 테스트: **판단 창 동안 다른 경로(§7.3 주입의 `observe` materialize, 또는 무인자 `progress status` 재실행)가 작업트리 report를 새 블롭으로 덮어도, 대조 기준이 작업트리 파일이 아니라 attest 해시이므로 리뷰 안 한 블롭이 박제·수용되지 않는 것**(8차 만장일치 치명 C-2의 회귀 — 대조를 작업트리 파일로 하면 이 테스트가 실패해야 한다). (d) 대조는 `probe_report_blob`의 읽기 전용 object-id로 하고, **통과 후 그 object-id의 블롭을 `cat-file`로 그대로 써 넣는 것**(재fetch 없음 — probe~쓰기 사이 Leader가 또 push해도 attest한 블롭이 박제되는 것, 음성 테스트; 대조 전 덮기 없음, 8차 M-1). (e) `progress status`가 대상 task를 materialize하고 그 블롭 해시를 출력하되, 모집합이 **작업본 행(신규 포함) ∪ 명시 인자**에 **HEAD 종결 필터**를 씌운 것이라 (ⅰ)수용 편집 중인 task가 재실행 시 빠지지 않고 (ⅱ)`∅→rejected` 신규 task도 명시하면 해시를 얻으며 (ⅲ)종결(`accepted`·`superseded`) task는 인자로 명시해도 재자재화·삭제하지 않는 것.
- **`rejecting_commit` 파서** — 단일 이벤트(`<task> <before>-><after>`, 공백 없음)와 배치(`- <task>: <before> -> <after>`, 공백 있음) 두 형식에서 `after==rejected`만 잡고, 재개(`rejected->in-progress`)·`Reason:` 줄·`w1.t10`류 접두 오매칭을 배제하는 것.
- **`post_mortem`이 실행 중 컨테이너를 사망으로 오판하지 않는 것** — 창만 사라지고 컨테이너가 살아 있으면 종료코드 대신 "실행 중"을 돌려주고, 호출자가 재기동이 아니라 블로커로 올리는 것(§2.5).
- `inject()`가 `clear_input` → `send_text` → `submit` 순서로 부르고, 그 직전에 상태를 재폴링하는 것. 재폴링이 `IDLE`이 아니면 **아무 키도 보내지 않는 것** — 권한 프롬프트를 조작하지 않는다.
- 잔류물이 있는 입력창에 주입해도 접합이 일어나지 않는 것.
- 락이 `submit()` 반환까지 유지되는 것. 락 획득 실패 시 `DEFERRED`.
- 제출 증거가 `BUSY`와 `WAITING_INPUT` **양쪽**으로 성립하고, 관측 창 안의 `ERROR`·`STOPPED`가 `UNAVAILABLE`이 되는 것.
- `attach()`가 라이브 조회 결과에 따라 재결합하거나 `NotStarted`를 던지는 것. 실패 후 `post_mortem()`이 classmethod로 호출 가능한 것.
- `poll_state()`가 `exit_code`·`last_error` 조합으로 `ERROR`와 `STOPPED`를 가르는 것 — **두 백엔드 모두에서**.
- `capability_args`·`prepare_subagents`·`build_session_command`가 어댑터별로 기대한 argv(및 파일)를 내는 것.
- 메시지 렌더링과 토큰 계산. 렌더링 결과에 개행이 없는 것(§4.1이 요구하는 단일행).
- `leader.down(keep_workspace=True)`가 workspace를 남기고, 미push 커밋이 있어도 던지지 않는 것.
- **`leader.restart()`가 실제로 완주하는 것.** `up(reuse_workspace=True)`가 `provision`을 건너뛰지 않으면 여기서 `FileExistsError`로 실패한다 — 2차 개정본의 절차를 잡았을 테스트다.
- **`up(reuse_workspace=True)`의 `start()` 실패가 workspace를 지우지 않는 것.** 보상 `teardown(force=True)`가 살아 있으면 미커밋 작업이 사라진다(§4.5).
- `send_prompt()`가 `submit()`을 부르는 것(개행 제거 후의 회귀).

### 8.2 계약 검사 (CI)

이원 정의원이 어긋나지 않게 한다.

- `RoleSpec.rule_refs`의 모든 id가 `docs/sot/rule/`에 실재한다.
- `RoleSpec.writable_paths` **=** `rule-role-responsibilities`의 역할 표가 그 역할에 적은 경로 glob 집합. 그 표가 단일 명세이므로 포함(⊆)이 아니라 등가다(§2.2).
- `capability == READ_ONLY` ⇒ `writable_paths == ()`.
- `ROLES`의 키 집합이 그 rule 문서의 역할 id 열과 정확히 일치한다(한쪽에만 있는 역할이 없다). **Watcher는 rule 문서 표에 행을 두지 않거나 id 열을 비운다** — `RoleSpec`이 아니므로 대조 대상이 아니고, id를 주면 이 검사가 켜지자마자 실패한다. (`rule-role-responsibilities`는 행을 두지 않는 방식을 택했다.)
- 오라클은 **역할 축 rule 문서 하나뿐이다.** `rule-protected-paths`(경로 축)를 파싱하지 않는다. 두 문서의 겹침은 사용자 게이트 PR에서 사람이 대조한다(§2.2).

`Enforcement` 값은 이 검사의 대조 대상이 아니다. rule 문서의 강제 등급 칸(`측정 대상`)과 코드의 `enforcement` 필드(보수적 서술값 `GATED`)는 규약상 다른 표현을 쓰므로 값 대조를 하지 않고, 계약 검사는 역할 id·쓰기 경로만 대조한다(`rule-role-responsibilities` 각주 ⁴). 그 강제 등급이 **참인지**는 §8.3만 답할 수 있다.

### 8.3 라이브 측정 (착수 게이트)

CI에 넣지 않는 별도 스크립트(`WIP/axdt/agent_runner/tests/live_probe.py`). 초안은 이를 선택 사항으로 뒀으나, 아래 항목들이 어댑터 구현의 분기를 결정하므로 게이트로 승격한다.

**게이트는 두 단계다.** 뒷 단계 항목들이 본 Phase가 *만드는* 컨테이너 이미지를 전제하므로, 하나로 묶으면 순환한다.

##### 8.3a — 구현 착수 전 (맨몸 CLI로 측정)

> **재-시퀀싱 (실측 반영).** §8.3a를 실제 호스트에서 착수한 결과, 항목별 판정 이전에 상태판정 자체가 현재 CLI(claude 2.1.209)에서 성립하지 않음을 실측했다 — provisional 화면 마커가 낡았고, "누적 스트림 꼬리 부분문자열" 판정 모델이 전체화면 재도색 TUI에 부적합하다. 대안으로 CLI 훅 기반 상태 방출이 성립함을 실증했다 — claude 2.1.209는 SessionStart→IDLE·UserPromptSubmit→BUSY·Stop→IDLE 세 전이를 모두 실측했고, codex 0.144.4는 UserPromptSubmit→BUSY만 실측(SessionStart·Stop은 미확정)이다. `detect_state`/`poll_state`는 Phase 5 소유 공유 계약이므로(§9) 재설계는 Phase 5가 수행하고, 그 훅 기반 판정기가 아래 항목 1~10 완료의 선행이 된다 — 항목 전부가 초기 IDLE 게이트(`wait_until_idle`)를 전제하기 때문이다. 아래 항목들의 화면 마커 전제(특히 항목 2·4)는 훅 이벤트→상태 계약으로 대체되므로, 항목별 판정은 Phase 5가 재정의한 그 계약 위에서 수행한다. per-item 판정과 그에 딸린 어댑터 argv·강제 등급 동결은 Phase 5 판정기 이후로 이월한다. 상세: `WIP/handoff-state-detection-redesign.md`.

1. **`IDLE`인 에이전트가 입력 없이 `IDLE`을 벗어나는가.** 벗어난다면 §4.1의 제출 증거(`IDLE` 이탈)가 위양성을 낸다.
2. `IDLE`/`BUSY`/`WAITING_INPUT`/`ERROR` 출력 마커 (`PLATFORM_MATRIX.md`의 기존 provisional 행). 마커의 신뢰도가 곧 `SENT`의 신뢰도다.
3. **입력창을 비우는 키가 무엇이고, `IDLE` 밖에서 무해한가.** `Ctrl-U`가 줄을 지우는가. 그 키가 `WAITING_INPUT`(권한 프롬프트)에서 승인·거부·인터럽트로 해석되지 않는가. `clear_input()`이 여기 달려 있고, 틀리면 우리가 권한 다이얼로그를 대신 누른다(§4.1).
4. 타이핑만 하고 제출하지 않았을 때 상태 마커가 `IDLE`에 머무는가. 머물지 않으면 게이트가 오작동한다.
5. 긴 단일행이 TUI에서 접히거나 수평 스크롤되는가. 접히면 메시지 형식을 다시 본다.
6. `--permission-mode dontAsk`에서 허용 목록 밖 명령이 `WAITING_INPUT` 없이 거부되는가.
7. `capability_args`가 실제로 쓰기를 막는가 — `READ_ONLY` 역할로 파일 쓰기를 시도해 거부를 확인한다. 결과에 따라 §3의 강제 등급이 **게이트**에 머무는지 **기계**로 올라가는지 정해진다.
8. `BUSY` 세션에 주입하면 큐에 쌓이는가 버려지는가.
9. Codex Maintainer의 `HOST_CONTROL` 번역(`-s danger-full-access` + 승인 정책)이 실제로 호스트 제어를 주는가. 주지 않으면 `maintainer up --platform codex`를 본 Phase에서 뺀다.
10. Codex에 `/compact`·`/context`·`/btw` 대응 명령이 있는가 (Watcher 별도 작업의 입력). Claude Code `/btw`의 "읽되 쓰지 않는다" 의미론도 함께 확인한다.

##### 8.3b — 이미지 빌드 후, Leader 첫 기동 전

11. 컨테이너 이미지에 구운 신뢰·온보딩 설정으로 Leader가 프롬프트 없이 `IDLE`에 도달하는가. **온보딩 완료를 표시하는 실제 키 이름**을 여기서 확정한다.
12. `/tmp`가 런타임에 tmpfs로 덮이는가. 덮이면 `config.CONTAINER_HOME`을 `/tmp` 밖으로 옮기고 Phase 3 코드를 고친다(§4.1).
13. 임의 uid로 컨테이너를 띄웠을 때 구운 HOME이 읽고 쓰이는가(`--user`가 호출자 uid를 넘긴다).

측정 결과로 `PLATFORM_MATRIX.md`의 provisional 행을 확정으로 바꾸고, **확정 시점의 CLI 버전을 함께 기록한다.** 측정된 버전과 실행 시점 버전이 다르면 `live_probe`를 다시 통과할 때까지 경고한다 — 여기서 확정하는 것 대부분이 CLI의 미문서화 동작이므로, 버전이 올라가면 근거가 사라진다.

---

## 9. 교차-Phase 인터페이스

| 상대 | 본 Phase가 소비 | 본 Phase가 제공 |
|---|---|---|
| Phase 3 | `TmuxDockerBackend`, `container.run_args`, `cron.install`, `leader.up/down`, `tmux.*` | `PLACEHOLDER` 제거, `TmuxHostBackend`, `attach`/`post_mortem`, `exit_code`/`last_error`, `up(reuse_workspace=)`·`down(keep_workspace=)`·`restart()`, `list_leaders()`, `axdt watcher tick`, 프로젝트 스코프 락, 이미지에 굽는 신뢰 설정 |
| Phase 4 | 상태 어휘·전이표, `commit`, **`recover.reconstruct`(수렴 판정의 관측원)** | `## 후속 제안` 절, 배정·반려 메시지 형식(Phase 4가 넘긴 숙제) |
| Phase 5 | `AgentRunner`, `PlatformAdapter`, `AgentState`, `FakeBackend`, `SessionBackend` ABC | 어댑터 추상 3종 + `submit_key`/`clear_key`, backend `send_key`, runner `submit()`/`clear_input()`/`attach()`, `format_prompt`·`send_prompt` 변경, `start_session(role, ...)` 시그니처 변경, `PLATFORM_MATRIX` 확정 |
| Phase 7 | — | `WAITING_INPUT`·`Blocker`를 메신저로 승격할 지점, 권한 프롬프트 응답 경로 |
| Phase 8 | — | 오케스트레이션 루프가 호출할 `needed_instruction`·`inject`·`leader.up/restart` |

`infra/backend.py`가 `SessionBackend` ABC를 인라인 정의한 것은 Phase 5가 main에 없던 시점의 임시 조치다. 본 Phase에서 `agent_runner`의 ABC를 import하도록 통합하되, **§2.5의 세 단계를 그 순서대로** 밟는다.

**상태판정 재설계는 Phase 5로 이월한다.** §8.3a 실측이 provisional 마커와 "스트림 꼬리 부분문자열" 판정 모델이 현재 CLI에 부적합함을 밝혔다. 훅 기반 상태 방출로의 `detect_state`/`poll_state` 재설계를 Phase 5(공유 계약 소유)에 넘기며, 그 결과 §8.3a 항목 1~10의 per-item 완료가 Phase 5 판정기 이후로 재-시퀀싱된다(§8.3a 주). 인계 문서: `WIP/handoff-state-detection-redesign.md`.

---

## 10. SoT 변경 (사용자 게이트 PR)

rule 2종을 신설한다. 구현 브랜치와 분리해 `sot/<slug>` 브랜치로 발의한다(`rule-sot-change-user-gate`).

| 신설 rule | 담는 것 |
|---|---|
| `rule-role-responsibilities` | §3의 역할 표 — 책임 경계·실행 위치·능력 등급·쓰기 권한·**강제 등급**. 기계가 읽을 역할 id 열을 포함한다 |
| `rule-prompt-injection` | §4.1의 주입 규약 — `IDLE` 한정, 멱등, 상태별 분기, 메시지 형식. 범위는 **세션 주입 일반**이므로 Watcher→Maintainer 주입도 포함한다 |

**두 rule의 발의 시점이 다르다.**

`rule-role-responsibilities`는 §8.2 계약 검사의 오라클이므로 구현이 그것 없이는 검사를 켤 수 없다. 먼저 발의하되, 강제 등급 열에는 측정되지 않은 값을 참으로 적지 않는다 — 해당 칸을 `측정 대상`으로 두고, §8.3 통과 후 별도 PR로 확정값을 채운다. 쓰기 경로와 역할 id 열은 측정과 무관하므로 처음부터 확정으로 적는다.

`rule-prompt-injection`은 §8.3 이후다. 이 rule이 동결하는 것 대부분(에코 여부, `BUSY` 전이의 신뢰도, `BUSY` 주입 거동)이 측정으로만 참이 되므로, 먼저 발의하면 검증되지 않은 규약을 권위본에 굳히게 된다.

`rule-role-responsibilities`는 **역할 → 쓰기 경로의 단일 명세**다(§2.2). 기계가 읽을 역할 id 열과 경로 glob 열을 갖는다. `rule-protected-paths`는 경로 축 규칙으로 남고 파싱 대상이 아니다. 두 문서가 겹치는 부분은 사용자 게이트 PR에서 사람이 대조하며, 겹칠 때 더 제한적인 쪽이 이긴다는 우선순위는 `rule-role-responsibilities`가 자기 문서에 명시한다.

---

## 11. 결정 지점

**확정**
- 역할 5종(`ROLES`)의 역할 id·kind·실행 위치·능력 등급·쓰기 경로 (§3). Watcher는 `RoleSpec`이 아니다. **강제 등급은 구조로 확정된 것(Maintainer=부재·Leader=게이트+허브·Developer/Tester=권고)만 확정이며, Reviewer의 실효 강제 등급(게이트↔기계)은 §8.3a 항목 7의 측정 대상이라 Phase 5 판정기 이후로 이월한다(§8.3a 주·§10)**
- 역할 선언의 이원 분리와, 그것이 닿지 않는 회색지대의 명시 (§2.2)
- `Capability` 3등급(호스트 제어 포함), 등급의 플랫폼 간 비등가를 `PLATFORM_MATRIX`에 기록 (§2.3.1)
- 강제 등급 4분류 — 기계 / 게이트 / 권고 / **부재** (§2.3.2)
- Codex sub-agent = AXDT 래퍼 스크립트, 명령줄 소유권을 AXDT가 갖는다 (§2.3.3)
- `attach`·`post_mortem` 경로와 백엔드 계약 통합의 3단계 (§2.5)
- **멱등은 메시지 단위가 아니라 상태 수렴이다.** "이 지시를 보냈던가"가 아니라 "이 지시가 지금도 필요한가"를 묻는다. 관측원은 `recover.reconstruct` + plan 존재 + git 블롭 비교 + 세션 상태이고, 새 저장소도 토큰 조회도 없다 (§4.1)
- **결정표는 `progress` 범주를 1차 키로 하는 상호배타 구조로 짠다.** `progress`로 분할되는 네 구간(종결·보류 / 반려 / 행 없음 / 착수=행 14~17)은 서로 배타적이라 그들 사이 가림이 구조적으로 없다. **단 두 행은 구간 분할의 일원이 아니라 순서로 자리를 지킨다** — **무효 행(행 7)**은 `report`축 조건이라 종결·보류 뒤이면서 `report` 열이 `—`인 모든 구간(반려·행없음)과 착수 앞에, **catch-all 행(행 18)**은 전정의역을 받으므로 맨 마지막에 고정한다(둘 중 어느 것을 옮겨도 결과가 바뀐다 — 8차 M-A, 10차 완성). 평면 우선순위표는 재정렬마다 가림을 낳았고(5차: `report=done`이 반려를, 6차: report 행이 "행 없음"을·반려 행이 새 블로커를), 이 구조는 그 가림을 네 구간에 대해 없애되 행 7·18은 위치로 방어한다 (§4.1)
- **`needed_instruction`의 반환은 세 갈래다**: `Instruction` / `Blocker` / `None`. "보낼 것 없음"과 "사람을 불러야 함"은 다른 값이어야 한다 (§5)
- **반려는 상태만으로 판별되지 않고, 그 판별은 커밋 시점 박제에 의존한다.** `progress=rejected`·`report=done`은 "반려 직후"와 "재작업 완료"에서 똑같이 관측되고 조상 관계로 못 푼다. **반려 커밋에 박제된 report 블롭과 지금 report를 비교**하되, 그 박제가 옳으려면 **커밋 경로가 사람이 리뷰한 블롭을 박제해야 한다**(§7.4) — 6차는 이 선행이 서술뿐이라 블롭 없는·낡은 박제 위에서 반려가 영구 미전달됐고, 7차 절차는 사람의 판단을 락 안에 넣으려다 실현 불가능했으며, 8차는 리뷰본을 덮일 수 있는 작업트리 파일로 삼아 리뷰 안 한 블롭이 박제될 수 있었다. 9차는 리뷰(`progress status`)가 블롭 해시를 출력하고 커밋이 `--reviewed` attest 해시와 허브를 대조해 박제한다. `rework_pushed`가 참이어도 report가 완료(`done`)가 아니면(새 블로커 `blocked`·`needs-spec`, 또는 재작업 중 정지 `todo`·`in-progress`) 블로커로 올린다(6차 M-4 + Codex 8차) (§4.1, §7.4)
- **report는 fetch만으로 보이지 않고, 잘못 부르면 force-push를 버리며, 실패를 뭉개면 진행 중 report가 사라진다.** `recover`가 작업트리 파일을 읽으므로 허브 report 블롭을 작업트리로 **자재화**하되, refspec에 **`+`**를 붙이고(non-FF 거부 방지) 허브 **경로**에서 가져온다(root엔 hub 원격 없음). 실패는 둘로 가른다 — `git ls-remote`로 **확인된 부재**만 파일을 삭제해 부재로 만들고, **일시적 fetch 실패**는 작업트리를 두고 관측 불가로 건너뛴다(6차 M-3) (§4.1, §7.3, §7.4)
- **배정·반려의 재전송 상한은 본 Phase가 정하지 않는다.** 전달 기록을 `progress`에 적는 것은 `rule-report-to-progress-authority` 위반이고 Phase 4의 정합성 매트릭스를 오염시킨다. 상한은 맥락을 가진 호출자(Maintainer 세션, Phase 8 루프)의 몫이다. **본 Phase의 산출물 중 주입하는 것은 없으므로 라이브락이 발생하지 않는다** (§4.1)
- **마커에서 유래한 `ERROR`로 재기동하지 않는다.** `poll_state`의 `ERROR`는 살아 있는 마커에서도 crash 종료(비영 코드)에서도 나오므로(실측), 표만으로는 못 가른다. §7.3이 이 표를 부르기 전에 `is_alive`로 실제 죽음을 확인해 죽음이면 재기동으로, 살아 있는 마커면 **블로커**로 보낸다(결정표 행 4). Watcher·주입·수렴·§4.5 모든 경로에 적용된다 (§4.5, §7.3)
- **수용/반려는 사람의 판단을 락 밖에 두고, 커밋이 사람이 attest한 블롭을 박제하는 절차다(§7.4).** 리뷰(`progress status`, 짧은 락)가 대상 report를 자재화하고 그 블롭 해시(git object-id)를 출력해 사람에게 보이고, 사람은 락 없이 판단·`progress.md` 편집을 하며, 커밋(`progress commit --reviewed <task>=<hash>`, 락)은 편집 diff로 변경 task를 확정→허브 블롭 id를 읽어(`probe_report_blob`) **attest 해시와 대조(없거나 다르면 `CommitRejected`)**→통과 블롭을 놓고→`milestone_commit`을 한다. 7차는 사람의 판단을 락 안에 넣으려다 실현 불가능했고(7차 C-1), 8차는 리뷰본을 작업트리 파일로 삼았는데 그 파일이 판단 창 동안 §7.3 주입·status 재실행에 덮여 리뷰 안 한 블롭이 박제될 수 있었다(8차 만장일치 치명 C-2). 9차는 대조 기준을 덮일 수 있는 파일에서 **사람이 명령줄로 넘긴 해시**로 옮겨 창을 닫는다 — 해시가 명령 인자로만 흐르므로 `ADR-0002`(무 저장소)와 충돌하지 않는다. 10차는 `git add`의 줄끝 정규화가 박제 블롭을 허브 블롭과 달라지게 하는 잠복 취약점(C-3)을 `.gitattributes`의 `docs/interim/report/*.md -text` + 스테이징 후 인덱스 블롭 id ↔ attest 대조로 봉인한다. `progress status` 모집합은 작업본 행 ∪ 명시 인자에 HEAD 종결 필터다 (§4.1, §7.4)
- **프로젝트 락 획득은 상한을 둔 논블로킹이다.** 못 잡으면 무한 대기하지 않고 물러선다 — 주입은 `DEFERRED`, tick은 회차 건너뜀, `progress commit`은 알리고 종료 (§4.5)
- 주입은 `IDLE` 한정. 타이핑 직전에 재폴링하고, `clear_input` → `send_text` → `submit`을 한 락 안에서 한다. 삭제 키는 `Esc`가 아니다 — 권한 프롬프트를 대신 누르게 된다 (§4.1)
- 제출 증거는 **`IDLE` 이탈**(`BUSY` 또는 `WAITING_INPUT`). 이것은 **통제 흐름이 아니라 계측**이다. 오라클이 틀려도 다음 주기의 관측이 바로잡는다 (§4.1)
- 배정·반려·자유 텍스트 메시지는 단일행이고 파일·커밋을 가리킨다. 토큰은 사람이 읽는 표식일 뿐 오라클이 아니다 (§4.1)
- `send_prompt`의 게이트를 `IDLE` 단독으로 좁힌다. 제출을 붙인 채 `WAITING_INPUT`을 받으면 권한 프롬프트를 승인하게 된다 (§5)
- 플랫폼 식별자는 저장되지 않으므로 `attach`·`restart`·`inject` 경로가 매번 전달받는다 (§5)
- `writable_paths`의 단일 명세는 `rule-role-responsibilities` 하나다. `rule-protected-paths`는 파싱하지 않고, 겹침은 사람이 대조한다 (§2.2, §8.2)
- 승인 우회 플래그 대신 `dontAsk` + 범위 허용 + 거부 목록. **거부 목록은 유출을 막지 못하며 이는 수용된 위험이다** (§4.1)
- 신뢰·온보딩 상태는 이미지에 굽고, 자격증명은 환경변수로 주입한다 (§4.1)
- 재기동은 `restart()` = `down(keep_workspace=True)` → `up(reuse_workspace=True)`. **양쪽을 다 고쳐야 한다** — `up()`의 `provision()`도 기존 workspace에 fail-fast한다. 그리고 `reuse_workspace=True`에서는 **보상 `teardown(force=True)`를 하지 않는다** — 일시적 start 실패가 미커밋 작업을 지운다 (§4.5, §7.2)
- 락을 둘로 나눈다 — cron overlap 락(`<root>/.axdt/cron.lock`, cron이 감쌈)과 프로젝트 락(`<root>/.axdt/lock`). 같은 파일이면 tick이 자기 래퍼에 막힌다(`flock` OFD 단위). 프로젝트 락은 Watcher tick·maintainer·**leader 생애주기**·주입·**progress status/commit**이 프로세스 내부에서 잡는다. 프로젝트당 하나 (§4.5)
- 본 Phase의 Watcher는 `axdt watcher tick` 하나 — 생존 확인·사후 조회·stdout 진단. LLM도, 죽이는 권한도, **쓰는 파일도** 없다. 재기동 근거는 프로세스의 실제 죽음이며, **화면 마커에서 유래한 `ERROR`는 근거가 아니다** (§2.4, §6)
- plan 소유는 Maintainer 단독, report에 `## 후속 제안` 절 추가 (§2.6)
- 계약 검사는 등가(=) 관계, 오라클은 역할 축 rule 하나 (§8.2)
- 라이브 측정은 착수 게이트 (§8.3)

**별도 작업**
- Watcher 설계 전반 — 하한선, 폐기한 경로, 유력 후보 흐름, 답해야 할 질문 목록만 본 스펙에 남긴다 (§2.4)

**수용된 잔여 위험** — 설계로 닫지 않고 명시한다
- 락은 다른 주입자를 배제하지만 **에이전트 자신의 전이는 막지 못한다.** 재폴링과 게이트 사이의 창이 남고, `poll_state()`는 캡처 꼬리의 마커 추론이라 낡을 수 있다 (§4.1)
- 허브가 무인증이므로 오염된 Leader가 남의 report를 위조할 수 있다. 사람의 수용 게이트가 잘못된 코드를 막지만 진행이 조용히 멎을 수 있다 (§4.1)
- 거부 목록은 유출을 막지 못한다. Phase 3 egress 허용목록 전까지 열려 있다 (§4.1)
- 컨테이너·tmux 이름공간이 전역이라(root 성분 없음) 본 Phase는 호스트에 AXDT 프로젝트 하나를 전제한다. 다중 프로젝트 동거는 `list_leaders`가 서로를 긁고 식별자가 충돌하며, Phase 3 이름공간 변경이 필요하다 (§4.5, §5)

**측정이 정할 것** (§8.3) — 그 전에는 참으로 가정하지 않는다

*8.3a — 구현 착수 전*
- `IDLE`인 에이전트가 입력 없이 `IDLE`을 벗어나는가 (제출 증거 오라클의 전제)
- 입력창을 비우는 키가 무엇이고 **`IDLE` 밖에서 무해한가** (`clear_input()`이 권한 다이얼로그를 누르지 않아야 한다)
- 타이핑만 하고 제출하지 않은 세션이 `IDLE`로 보이는가 (게이트의 전제)
- `capability_args`가 실제로 쓰기를 막는가 (강제 등급이 게이트인가 기계인가)
- `dontAsk`에서 허용 목록 밖 명령이 `WAITING_INPUT` 없이 거부되는가
- Codex Maintainer의 `HOST_CONTROL` 번역이 성립하는가 (아니면 `--platform codex`를 뺀다)
- `BUSY` 세션 주입의 거동 (큐잉인가 유실인가)
- Codex의 `/compact`·`/context`·`/btw` 대응 명령 유무

*8.3b — 이미지 빌드 후, Leader 첫 기동 전*
- 이미지에 구운 설정으로 Leader가 프롬프트 없이 `IDLE`에 도달하는가, 온보딩 키의 실제 이름은 무엇인가
- `/tmp`가 tmpfs로 덮이는가 (덮이면 `CONTAINER_HOME` 이동 → Phase 3 수정)
- 임의 uid로 구운 HOME이 읽고 쓰이는가

**넘김**
- 누가 언제 어떤 task를 띄우고 wave를 닫는가 → Phase 8. 본 Phase는 그 루프가 부를 `needed_instruction`·`inject`를 만든다
- **재전송 상한(라이브락 방지)** → Phase 8. 장수 루프가 메모리에 횟수를 갖는다. 본 Phase의 산출물은 주입하지 않으므로 안전하다
- `WAITING_INPUT`·`Blocker`가 사람에게 닿는 경로, 권한 프롬프트 응답 → Phase 7
- 컨테이너 egress 허용 목록 → Phase 3 백로그. **본 설계의 유출 위험은 이것으로만 닫힌다**
- Maintainer 분해 노동의 context 부담 → Phase 8 (소유권 이동 없이 다룬다)
