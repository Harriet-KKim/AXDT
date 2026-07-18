# Phase 6 강제 증분 — SoT 완료 강제(머지 컨트롤러) 설계

> 상태: **revised** — Codex+Fable 2차 리뷰 + GitHub 라이브 실증(2026-07-09) + 3차 다중 모델 리뷰 반영(2026-07-13: 승인 키 취득·룰셋 감시·산출물 쓰기 통제·명단 계약·강제-필수 경로 분기·신선성 논증·변조 (가) 폐기·정규화 단일 구현) + Phase 3 회신(`WIP/handoff-phase6-enforcement-response.md`, `phase3-followup`/`f4ace7f`) 흡수(2026-07-13: 강제-필수 경로를 `axdt-critical-paths` 블록 단일 입력으로·코드오너 검토 비필수·게이트 코드 경로 추가를 활성화 전제조건으로) + 구현 리뷰 반영(2026-07-14: digest 규약 v2 경계보존 length-prefix 직렬화·항목11 문언을 §3 "동일 comment_id 중복=결정값 무관 RED"로 정합·강제-필수 분기 not dismissed 명시) + 2키 정합(2026-07-17: 규칙 정본(`ADR-0014`·`ADR-0015`)의 2키 모델 통합 — 단일 판정 키 → 판정 키 4성분 + 완전성 스윕 키 신설, ② 산출물 둘(정합성·완전성)·두 키 삼자 대조·§2.6 fail-closed 목록 두 키 일반화·§3 계약 개정) + 실행부 구현·다중 리뷰 반영(2026-07-18: 실행부(포트·컨트롤러) 구현 후 Codex+Fable 5라운드 수렴, 두 스펙 결정 반영 — base SHA는 라이브 머지 커밋 SHA로(§2.9), `sot/*` force-push·삭제 차단 RS-C 신설로 read-set ABA 창 방어(§2.8·§4.1·`ADR-0009` 결정 8 개정)). 확정 후 writing-plans로 구현(별도, Sonnet 위임). 확정 전까지 구현 금지.
> 상위: `ADR-0009`(강제 증분 결정) · `ADR-0010`(호스트 추상화, (b) 클라이언트) · `ADR-0007`(층 강제, proposed).
> 권위 규칙: `docs/sot/rule/sot-readiness.md`(완료 정의·판정 키·강제 매핑) · 스킬 `sot-readiness-review`(② 검토 축·감사 로그).
> 규칙 참조는 **조항 이름**으로 한다(줄 번호 `§n`은 규칙이 개정되면 깨진다).
> 범위: **GitHub 전용**. GitLab/Forgejo 강제는 별도 멀티호스트 Phase. 라이브 호스트 검증은 Phase 9.

---

## 1. 목표와 비목표

### 목표
- `rule-sot-readiness`가 정의한 완료 강제(**① 형식 ∧ ② 검토 ∧ ③ 승인**)를 **GitHub에서 실제로 막는 메커니즘**을 설계한다.
- 강제 계산을 **호스트 무관 순수 게이트 코어**로 두고 결정적으로 테스트한다(라이브 호스트 불필요).
- 호스트 채널(사용자 결정)·권한 확인·승인 이벤트·② 검토 CI·머지 실행을 **주입되는 포트 + 선언적 설정**으로 분리한다.
- 초기 마이그레이션 스윕과 fail-closed 롤아웃을 설계한다.

### 비목표 (이 증분에서 하지 않음)
- **GitLab/Forgejo 강제** — 별도 멀티호스트 Phase. 3-호스트 매트릭스(§4.3)는 그 Phase의 선행 스케치.
- **라이브 호스트 검증** — `gh api` 스키마·워크플로 실체는 provisional. Phase 9 도그푸딩에서 확정.
- **② 검토 판정 로직 자체** — 무엇이 finding인지는 스킬 `sot-readiness-review`와 규칙이 정한다. 여기서는 그 **산출물의 형식과 게이트의 소비**만 다룬다.
- **트리거 상태 머신(일시정지·재개)** — Phase 8.
- **컨트롤러의 배포·호스팅** — 어디서 도는지, 어떻게 깨어나는지는 후속. 여기서는 계약과 불변식만.
- **구현·구현 플랜** — 설계 확정·다중모델 리뷰 후 별도(Sonnet 위임).

---

## 2. 핵심 설계 결정

### 2.1 구조 — 순수 코어 + 주입 포트, 쓰기 포트는 머지 실행
강제 계산(`①∧②∧③`)은 호스트 지식이 없는 순수 함수 `evaluate_gate`에 둔다. 호스트 접점만 `GateHostPorts`로 주입한다 — **`GateInputs`를 채우는 읽기 5개**(착지 두 키 계산·PR 메타데이터·CI 산출물 둘·채널 결정·승인 이벤트) + **룰셋 구성 점검**(GateInputs를 채우지 않는 머지 직전 관문) + **머지 실행**. 결정권자 명단은 호스트가 아니라 컨트롤러 도메인 구성으로 주입한다(§2.7). (b)의 `GitHostClient = adapter + backend` 분리를 계승한다.

`ADR-0009`의 (가) 필수 검사 오버레이와 달리, 쓰기 포트는 **검사 상태 게시가 아니라 머지 실행**이다. 게이트가 초록이라는 사실을 호스트에 남기고 호스트가 그것을 강제하는 대신, 컨트롤러가 초록일 때에만 스스로 머지한다.

### 2.2 두 판정 키(정합성·완전성)와 완전 결속 키
`rule-sot-readiness`는 ②를 **입력이 다른 두 갈래 검토**로 나누고 각기 다른 키에 결속한다(규칙 §② "결속 키와 무효화"). 이 스펙은 그 두 키를 게이트 입력으로 삼는다. 성분 정의·정규화·직렬화 규약은 규칙이 정본이고, 게이트는 두 키를 **불투명 값으로 비교만** 한다.
- **판정 키**(정합성·공백) = **네 성분** `(SoT 트리 해시 + 적용 rule 지문 + review_policy_epoch + rule catalog manifest digest)`. 정합성·공백 판정·각 finding·사용자 수용/기각을 결속한다(규칙 §② 판정 키).
- **완전성 스윕 키**(선언 완전성) = **세 성분** `(projection 트리 해시 + 활성 rule 카탈로그 입력 digest + review_policy_epoch)`. 선언 완전성 검사를 결속한다. `projection 트리 해시`·`review_policy_epoch`는 판정 키와 같은 입력에서 나오나 활성 카탈로그 입력 digest가 달라 **별개 합성 키**다(규칙 §② 완전성 스윕 키).
- 두 키 모두 **제안된 머지 결과 상태**에서 계산한다. 검사 코드·정책 자체만 신뢰 base에서 읽는다(`rule-protected-paths`). "머지 결과에서 계산"(무엇을 적용하는가)과 "base에서 읽음"(검사 코드)을 혼동하지 않는다.
- **완전 결속 키** = `해당 검토의 키(판정 키 또는 완전성 스윕 키) + (F-n + 내용 digest)`. finding 단위 사용자 표시·대조 키. 표시는 **자기 검토의 키에만** 결속한다 — 정합성 finding은 판정 키에, 완전성 finding은 완전성 스윕 키에 결속하며, 다른 검토의 키 변화가 이 표시를 교차 무효화하지 않는다(규칙 §②). **내용 digest = (검토 축 + 참조 문서·항목 ID + 심각도 + 설명 본문)을 정규화한 해시**.
- **정규화는 유니코드 NFC → 개행 LF 통일 → 앞뒤 공백 제거·연속 공백 축약 → 참조 정렬로 고정한다.** 마크다운 구조는 정규화하지 않는다 — "무엇이 같은 마크다운인가"가 정의되지 않아 결정성을 해치고, 구현 부담만 크다(규칙 ②의 결속 키 조항과 일치). 연속 공백 축약이 전역이라 개행 뒤 들여쓰기 깊이는 소실된다(코드블록 4칸과 문단 1칸이 같은 digest로 접힌다) — 마크다운 구조 비정규화의 감수된 귀결이다.
- 게이트 코어는 두 키·digest를 **비교만** 한다(계산은 ② CI와 컨트롤러의 몫). 다만 digest **정규화 함수**는 결정적이라 순수 코어에 두고 함께 테스트한다.
- **정규화는 단일 구현이다.** `sot_gate.keys.normalize_finding_digest` 하나를 ② 검토 CI와 컨트롤러가 **똑같이 import**한다(두 구현 금지 — 규칙 ②의 "검사기가 단일 구현으로 고정" 조항). 산출 쪽과 대조 쪽이 다른 구현을 쓰면 같은 finding이 다른 digest를 얻어 유효한 사용자 결정이 미대조로 떨어진다(fail-closed라 안전하나 운영 마찰). 연속 공백 축약의 대상은 **스페이스·탭만**이며, 개행은 앞 단계의 LF 통일로 보존한다(개행은 축약하지 않는다).

### 2.3 두 키가 각각 세 지점(착지·검토·승인)에서 일치해야 한다
컨트롤러는 머지 직전에 **착지 두 키**(`landing_judgment` 판정 키·`landing_completeness` 완전성 스윕 키)를 제안된 머지 결과에서 직접 계산한다. 게이트는 **두 키 각각**에 대해 아래 셋이 모두 같을 때만 초록이다.

- 판정 키: `landing_judgment` = `consistency_artifact.judgment`(정합성 CI가 판정한 상태) = `approval.approved_judgment`(사용자가 승인한 상태).
- 완전성 스윕 키: `landing_completeness` = `completeness_artifact.sweep_key`(완전성 CI가 판정한 상태) = `approval.approved_completeness`.

승인이 걸린 두 키는 **승인 시점 상태에 고정**하며 평가 시점에 재계산하지 않는다. 재계산하면 base 전진으로 rule 지문·카탈로그가 바뀌었을 때 낡은 승인이 새 상태의 승인으로 되살아난다(규칙 ③의 승인 유효 조항 위반). base가 전진했다면 PR을 갱신해 재승인받아야 한다.

**승인 두 키(`approved_judgment`·`approved_completeness`)의 취득.** GitHub 승인 리뷰 객체는 승인자·시각·head `commit_id`만 싣고 **승인 시점의 base를 기록하지 않는다**. 두 키의 성분(트리 해시·rule 지문·`review_policy_epoch`·카탈로그 manifest·활성 카탈로그 입력 digest)은 제안된 머지 결과 = `merge(승인 시점 base, review.commit_id)`에서 계산되므로, 호스트 데이터만으로는 `approved_judgment`·`approved_completeness`를 재구성할 수 없다. **재계산으로 채우지 않는다** — 규칙 ③이 금한 동작이고, dismiss-stale 하에서 head가 불변이면 재계산값이 언제나 착지 두 키와 같아 검사가 공회전한다. 두 취득 경로 중 하나를 쓴다(구현 선택은 §8 provisional):
  - (ㄱ) **base 복원.** RS-A로 `main`은 컨트롤러 머지로만 전진하므로, 승인 시각의 base는 컨트롤러 감사 기록(§2.9)과 `main` first-parent 이력으로 결정적으로 복원한다 → `(approved_judgment, approved_completeness) = compute_landing(merge(base@승인시각, review.commit_id))`(한 번의 착지 계산이 두 키를 함께 낸다).
  - (ㄴ) **구조화 스탬프.** 승인 리뷰 본문에 **두 키를 모두** 명시한 기계판독 스탬프를 요구하고(결정 코멘트와 같은 방식), 두 키 스탬프가 없는 승인은 무효로 한다.

### 2.4 무엇이 머지를 여는가 — 컨트롤러의 머지 전 판정
- **`main` 갱신 권한은 컨트롤러 신원 하나로 제한한다.** 필수 검사(required check)를 강제 수단으로 쓰지 않는다.
- `②검토`는 판정이 아니라 **두 신뢰 산출물**을 낸다 — **정합성 산출물**(판정 키 + open blocking 각 `(F-n + 내용 digest)` + `format_ok`①형식 결과; verdict `review_clear`/`review_blocked`)과 **완전성 산출물**(완전성 스윕 키 + open blocking 각 `(F-n + 내용 digest)`; verdict `completeness_clear`/`completeness_blocked`). 두 산출물 모두 사용자 결정은 싣지 않는다.
- 컨트롤러가 머지 직전에 **그 두 산출물** + 채널 결정 + 승인 이벤트로 `①∧②(정합성∧완전성)∧③`를 계산하고, 초록이면 머지 API를 호출한다.
- **데드락이 생기지 않는다.** 두 검토가 `review_blocked`/`completeness_blocked`여도 남은 blocking이 전부 accepted/rejected면 게이트는 초록이다. **두 산출물 중 하나라도** 없거나 기형이면 게이트가 fail-closed로 붉으므로 두 검토는 전이적으로 필수다.
- `①형식`은 게이트가 `consistency_artifact.format_ok`로 흡수한다(형식 결과는 정합성 산출물에만 실린다).

### 2.5 머지 전역 직렬화와 신선성 불변식
- 컨트롤러는 **한 번에 하나의 머지만** 수행한다(전역 직렬화).
- 머지 직전에 모든 입력을 **다시 읽고 다시 계산**한다. 이전 평가 결과를 재사용해 머지하지 않는다.
- 불변식: **착지 두 키에 대해 신선한 평가 없이 머지되는 경로는 없다.**
- 따라서 코멘트 편집·삭제, 승인 취소, 권한 변경, base 전진을 이벤트로 좇아 이전 판정을 무효화할 필요가 없다. 그런 이벤트는 **머지 전 사람이 보는 표시**를 갱신하는 용도로만 규범화한다.
- **base 부동은 호스트 거부가 아니라 RS-A 배타성 + 전역 직렬화가 보장한다.** `main`을 갱신할 수 있는 신원은 컨트롤러뿐이고(RS-A), 컨트롤러는 직렬화 잠금 안에서 재평가→머지를 수행하므로 **잠금을 쥔 동안 base를 움직일 주체가 없다**. GitHub REST 머지 API에는 base를 고정하는 수단이 없다 — `sha`는 head 고정용이고, up-to-date 거부는 필수 검사(`required_status_checks`)를 켜야만 존재하는데 이 설계는 켜지 않는다. 그러니 "호스트가 base 전진을 거부한다"에 기대지 않는다(직렬화를 느슨하게 하면 오지 않을 거부에 기대게 된다).
- **head 이동은 계약이 막는다.** 평가와 머지 호출 사이에 PR 브랜치로 push가 들어오면 평가되지 않은 head가 착지할 수 있다. 컨트롤러는 **평가에 쓴 head SHA를 머지 API의 head 고정 파라미터(`sha`)로 전달**하고, 불일치로 거부되면 재평가부터 다시 한다. dismiss-stale이 승인을 지워 머지가 `405`로 튕기는 것은 보조 방어선일 뿐 이 계약을 대신하지 않는다.

### 2.6 fail-closed 목록 (§3 `evaluate_gate` 문서와 동일해야 한다)
아래는 fail-closed 판정 항목이다. **어느 분기에서 어떤 항목을 검사하는지는 아래 "분기는 셋이다"가 정한다** — SoT 검사는 1~11 전부, 강제-필수 경로는 1·3 + 결정권자 승인, 그 밖은 1만. 해당 분기에서 하나라도 성립하면 RED:

1. `pr_state != OPEN`
2. `head_ref`가 `^sot/[a-z0-9]+(?:-[a-z0-9]+)*$`에 맞지 않음
3. `head_repo != target_repo` (포크)
4. **두 산출물 중 하나라도** `None` — `consistency_artifact is None` 또는 `completeness_artifact is None` (산출물 없음·파싱 실패)
5. **어느 산출물이든** 불변식 위반 — 정합성 `review_clear != (open_blocking == ())` 또는 완전성 `completeness_clear != (open_blocking == ())`
6. `consistency_artifact.format_ok`가 거짓 (①형식은 정합성 산출물에만 실린다)
7. **어느 키든** 착지 키 불일치 — `consistency_artifact.judgment != landing_judgment` 또는 `completeness_artifact.sweep_key != landing_completeness`
8. **두 검토 중 어느 것이든** `open_blocking`에 유효 결정으로 닫히지 않은 것이 있음
9. 변조된 결정이 존재 (§2.7의 좁은 정의) — 두 검토 어느 쪽의 현재 유효본이든
10. 유효한 승인이 없음 — `approved_judgment != landing_judgment` 또는 `approved_completeness != landing_completeness`, 승인자가 admin 아님, 명단 밖, 기계 계정, 승인자 == PR 작성자, 또는 승인이 철회됨
11. **어느 검토든** 같은 완전 결속 키의 유효(대조 대상) 결정 중 **동일 `comment_id`**가 둘 이상 → (결정값이 같든 다르든) 미해결로 RED(결정론). 유효 후보로 한정하는 것은 미인가·자기결정·삭제 결정이 애초에 대조에 불참여하기 때문이며(§2.7 배제 규칙 — 이 필터로 결정권 없는 계정이 코멘트를 얹어 PR을 영구 차단하는 서비스 거부도 배제된다), 그 한정 안에서 동일 `comment_id` 중복은 정상 입력에선 나올 수 없고(호스트 코멘트마다 고유 id) 유효 입력 스트림의 이상(어댑터 중복 수집·중복 파싱)을 뜻하므로 결정적으로 fail-closed한다(§2.7)

> **진단 순서(모두 RED라 GREEN/RED 판정엔 무관, `reason` 문자열에만 영향).** SoT 분기에서 항목 4~7은 두 산출물에 대해 **항목 번호순**으로 검사하고, 블로킹 해소(항목 8·11·9)는 **산출물별로** 묶어 처리한다 — 정합성 산출물 먼저, 완전성 산출물 다음(§3 `evaluate_gate` docstring과 동일). 한 산출물 안에서는 항목 8(미대조)→11(동일 `comment_id` 중복)→9(변조) 순이며, **11이 9보다 앞서는 것은 변조 검사(항목 9)가 유일 winner(최대 `comment_id`)를 전제**하기 때문이다 — 중복 `comment_id`가 남아 있으면 winner가 유일하지 않다. 항목-우선(전역 8→9→…→11) 대신 이 순서를 택했고, 모든 항목이 RED라 판정은 바뀌지 않는다.

**분기는 셋이다** (판단은 모두 **제안된 머지 결과의 변경분**으로 하며 브랜치 이름·커밋 메시지로 하지 않는다):
- **(SoT) `touches_sot`가 참** — 위 1~11을 모두 검사한다.
- **(강제-필수 경로) `touches_enforcement_surface`가 참** — 강제 장치 자체를 바꾸는 PR이다(아래 목록). 형식·검토(①②)는 요구하지 않되(규칙의 pass-through 조항과 충돌 회피) 최소 관문을 건다: `pr_state == OPEN` ∧ `head_repo == target_repo`(포크 거부) ∧ **결정권자(admin ∧ 명단 ∧ 사람 계정 ∧ `approver != meta.author` ∧ 철회되지 않음) 승인 존재**. 자기승인 배제는 SoT 경로 항목 10과 대칭이다(게이트가 재확인; 호스트의 `require_last_push_approval`은 보조). 하나라도 어긋나면 RED. 이 분기가 있어야 ② 검토 CI·규칙 지문 원천을 무관문으로 갈아치우는 PR을 막는다.
- **(그 밖)** 둘 다 거짓이면 1번(`pr_state`)만 검사하고 GREEN(pass-through). 컨트롤러가 저장소의 모든 머지를 수행하므로 이 분기가 없으면 무관한 PR이 브랜치 이름 규약에 걸려 영구히 막힌다.

**강제-필수 경로 집합 — 권위 정의는 `rule-protected-paths`의 `axdt-critical-paths` 블록이다**(Phase 3 회신 §5.4로 확정). 게이트는 이 블록의 `critical <glob>` 줄을 **유일 입력**으로 읽어 `touches_enforcement_surface`를 판정한다 — 목록을 이 스펙에 복제하지 않는다(손사본 금지). glob 의미(`**`=구분자 포함 0+ 세그먼트, `*`=한 세그먼트 내)는 같은 파일의 task-push 블록(`axdt-protected-paths`) 정의가 정본이다. 등재 경로 전량은 `main`에 착지한 블록이 정본이다(참고용 사본을 이 스펙에 두지 않는다 — 손사본 금지). Phase 3가 `.github/workflows/**`를 handoff(`WIP/handoff-phase6-enforcement-critical-paths.md`) §2의 "② 검토 CI만"보다 **전체로 넓혔다**(보수적 확장 — 파일명 변경·신규 악성 워크플로에 강건, 변경 측 통보); ② CI 파일명 확정 시 좁힐 수 있다. 게이트·컨트롤러 코어 코드의 정식 이관 경로와 (저장소 안에 둘 경우) 결정권자 명단 경로는 확정 시 Phase 6가 변경 측으로서 블록에 추가·통보한다(§7 활성화 전제조건). 이 블록은 PR #17로 `main`에 착지해 권위 정의가 확정됐다(착지 완료 forward-ref 정리는 PR #18). 게이트의 세 번째 분기(포크 거부 + 결정권자 승인) 로직 자체는 이 조율과 독립으로 이 증분이 강제하며, 코드오너 검토를 필수 전제로 삼지 않는다(§4.1·§8).

### 2.7 호스트 채널과 결정권
- 사용자 결정(accepted/rejected)은 파일이 아니라 **그 PR의 구조화 코멘트**에 완전 결속 키를 참조해 남긴다(규칙: 파일 불신).
- **결정권 = 저장소 permission `admin` ∧ 지정 명단 등재 ∧ 사람 계정.** 이 논리곱은 **순수 코어가 계산한다** — 포트는 원시 사실만 넘긴다(계정별 `role_name`, 사람 계정 여부). 판정을 어댑터가 대신하면(bool 하나로 접으면) 결정권 규칙이 테스트로 고정되지 않고 어댑터로 샌다. 명단(`allowlist`)은 **컨트롤러 도메인(대상 저장소 밖)의 구성**이며 게이트에 주입된다(`GateInputs.allowlist`) — 저장소 안에 두면 §2.6의 강제-필수 경로가 되어 명단 변경 경로가 PR에 노출되므로 밖에 둔다. 명단 변경은 컨트롤러 감사 기록(§2.9)에 편입한다. `.github/CODEOWNERS`는 (다인 구성 전환 시 켜지는) 경로별 승인 강제 **2차 관문**이며 명단을 대체하지 못한다 — 현 1인 구성에선 비활성이고 1차 방어는 명단이다(§4.1). 기계 계정을 명단에서 제외하는 이유는, 사람이 자기 기계 계정으로 PR을 열고 사람 계정으로 수용하면 계정 이름 비교만으로 자기결정을 걸러내지 못하기 때문이다.
- 판별은 `role_name`으로 한다 — 레거시 `permission` 필드는 maintain을 write로, triage를 read로 뭉갠다.
- **권한 시점 = 평가 시점(현재 값).** 강등은 즉시 반영되고, 승격은 소급한다 — 지금 결정권자인 계정이 과거에 남긴 표시는 유효하다. 명단 등재가 결정권자의 명시적 행위이므로 소급 유효화를 의도된 동작으로 둔다. 컨트롤러가 머지 직전에 재평가하므로 여기서 "현재"는 언제나 착지 시점의 값이다.
- **자기결정 차단.** 결정·승인의 author가 PR author와 같으면 무효다.
- **append-only supersession.** 결정은 코멘트를 편집·삭제하지 않고 새 코멘트로만 번복한다. 같은 완전 결속 키에 유효 표시가 여럿이면 `comment_id`가 가장 큰 것이 이긴다.
- **변조(tampered)의 좁은 정의.** 아무 코멘트나 편집·삭제됐다고 붉히면, 낙서를 남겼다 지우는 것만으로 누구나 PR을 영구 차단할 수 있다(서비스 거부). 변조는 **현재 유효본으로 선택될 결정이 편집됨(`updated_at != created_at`)** 하나에만 적용한다. 그 외 코멘트의 편집·삭제는 게이트가 무시한다.
  - 삭제된 결정은 대조에서 빠지므로, 그것이 어떤 open blocking을 닫고 있었다면 그 blocking이 미대조가 되어 ②가 RED다(별도 변조 조항 없이 §2.6 항목 8로 잡힌다).
  - **폐기한 조항(초기 설계의 변조 (가) — "직전 초록 판정에 반영된 결정의 사후 편집·삭제").** 컨트롤러는 초록이면 같은 잠금 안에서 즉시 머지하고 머지되면 PR이 닫히므로, "초록 판정은 났으나 아직 머지되지 않아 다음 평가가 도는" 상태가 없다. 따라서 "직전 초록에 반영된 결정"을 지속해 다음 평가의 입력으로 되먹이는 경로가 설계상 없어(부작용 없는 `evaluate()` ∨ 머지 시에만 남기는 감사 기록 ∨ 머지 후 PR 종료), 이 조항은 발화 불가능했다. 삭제·편집의 실질 차단은 위 정의와 미대조 RED로 충분하다.

### 2.8 감사 이력 보존은 호스트가 강제한다
우회 불가 규칙 묶음(§4.1의 RS-B)이 허용 머지 방식을 merge commit으로 제한하고 `main`의 force-push·삭제를 차단한다. **컨트롤러가 올바른 머지 방식을 고르리라는 가정에 감사 이력을 얹지 않는다** — 컨트롤러 버그가 곧 이력 손실이 되면 안 된다. 컨트롤러의 방식 선택은 그 위의 보조 방어선이다. "Require linear history"는 머지 커밋을 금지하므로 켜지 않는다.

**`sot/*` 소스 브랜치의 force-push·삭제를 차단한다(RS-C, §4.1).** 당초 이 스펙과 `ADR-0009` 결정 8은 "`sot/*` 보호는 요구하지 않음"이었다 — merge commit이 승인 head를 `main` 이력에 부모로 보존하고 승인~머지 창은 dismiss-stale·head SHA 고정(§2.5)이 막으니 불필요하다는 근거였다. 그러나 그 근거는 **컨트롤러 자신의 read-set 도중 `sot/*`가 A→B→A로 롤백되는 창(ABA)을 저울에 넣지 않았다**(2026-07-18 개정, `ADR-0009` 결정 8 뒤집음): read-set 괄호치기는 앞뒤 head 표본이 같은지만 보므로, force-push로 head가 되돌아오면 앞뒤가 모두 A라 통과하나 중간 읽기가 B를 봐 미평가 내용이 착지할 이론적 경로가 남는다. 당초 우려했던 "제3 룰셋이 `sot/*` push까지 PR로 강제"는 **RS-B에 합칠 때만**의 문제이고, `non_fast_forward`+`deletion`만 담고 `pull_request` 룰이 없는 **독립 룰셋 RS-C**는 일반 fast-forward push를 막지 않아 에이전트 워크플로가 불변이다. RS-C가 `sot/*`를 단조 전진만 시키면 head가 이전 SHA로 되돌아올 수 없어 괄호치기가 완전해진다(ABA 창 닫힘). squash 방지는 별개 이유였고 `main` 룰셋의 `allowed_merge_methods`로 이관됐다.

실증: 저장소 전역 설정이 squash를 허용해도(`allow_squash_merge: true`) 룰셋의 `allowed_merge_methods: ["merge"]`가 squash 머지를 `405`로 거부했고, 그 룰셋을 지우자 통과했다. 머지 방식 강제의 주체는 룰셋이다.

### 2.9 컨트롤러 도메인의 불변 감사 기록
모든 머지의 `merged_by`가 컨트롤러이므로 호스트 이력만으로는 누가 무엇을 승인했는지 남지 않는다. 컨트롤러는 머지마다 착지 두 키(판정 키·완전성 스윕 키) · 반영된 결정 스냅샷(완전 결속 키·author·comment_id) · 승인 이벤트 · 그 머지의 base SHA를 자기 도메인에 **추가 전용**으로 기록한다. 이 기록은 대상 저장소 밖에 있으므로 PR이 위조할 수 없다. 이 기록과 `main` first-parent 이력이 임의 과거 승인 시각의 base를 결정적으로 복원하는 근거다(§2.3 (ㄱ) 승인 두 키 취득). 결정권자 명단의 변경도 같은 기록에 편입한다(§2.7).

**base SHA 취득(2026-07-18 결정).** 라이브 `merge_pull_request`가 GitHub 머지 API 응답의 **머지 커밋 SHA**를 반환하고 컨트롤러가 이를 기록한다 — 그 커밋의 first-parent가 곧 base SHA다. 새 포트를 더하지 않고 기존 머지 포트의 반환만 확장하며(반환형 None→SHA), 이 확장은 라이브 구현(Phase 9·§8)에서 적용한다. 이 증분(순수 코어 실행부)은 실제 머지를 하지 않으므로 `AuditRecord.base`에 `pr.base`(브랜치명)를 두고, 라이브에서 머지 커밋 SHA로 대체한다. 지금 별도 read 포트로 머지 전 `main` tip을 읽는 대안은 채택하지 않았다 — 동결 §3에 새 포트를 라이브 검증 전에 굳히고, 값도 "의도한 base"라 실제 착지본(머지 커밋의 first-parent)보다 권위가 약하다.

---

## 3. 인터페이스 contract (순수 코어)

```python
from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
# PullRequest, PullRequestState는 (b) git_host 통제 어휘 재사용(models/state).
# 공유 모델 PullRequest는 손대지 않는다 — 필요한 추가 정보는 전용 통로로 읽는다.

class GateStatus(Enum):
    GREEN = "green"                    # 머지해도 좋다
    RED = "red"                        # 막힘(fail-closed 포함)

class FindingDecision(Enum):
    ACCEPTED = "accepted"              # 위험 인지 후 수용
    REJECTED = "rejected"              # 오판

@dataclass(frozen=True)
class JudgmentKey:
    """정합성 판정 키 — 4성분(규칙 §② 판정 키). 게이트는 비교만(성분 계산은 ② CI·컨트롤러)."""
    tree_hash: str                     # (1) target-content projection 트리 해시
    rule_fingerprint: str              # (2) 적용 rule 지문
    review_policy_epoch: str           # (3) 검토 정책 epoch
    rule_catalog_manifest_digest: str  # (4) 규칙 카탈로그 manifest digest

@dataclass(frozen=True)
class CompletenessSweepKey:
    """선언 완전성 스윕 키 — 3성분(규칙 §② 완전성 스윕 키). 게이트는 비교만."""
    projection_tree_hash: str          # target-content projection 트리 해시(판정 키 (1)과 같은 입력)
    active_catalog_input_digest: str   # 활성 rule 카탈로그 본문 전량 digest(README·_TEMPLATE 제외)
    review_policy_epoch: str           # 검토 정책 epoch(판정 키 (3)과 같은 입력)

# 완전 결속 키가 결속하는 검토별 키 — 정합성이면 JudgmentKey, 완전성이면 CompletenessSweepKey
ReviewKey = "JudgmentKey | CompletenessSweepKey"

@dataclass(frozen=True)
class FullBindingKey:
    """해당 검토의 키(판정 키 또는 완전성 스윕 키) + (F-n + 내용 digest). finding 단위 대조 키.
    표시는 자기 검토의 키에만 결속한다 — 두 키 타입·값이 다르면 동등성이 성립하지 않아
    정합성 finding 결정이 완전성 finding을 닫지 못한다(교차 무효화 없음, 규칙 §②)."""
    review_key: "JudgmentKey | CompletenessSweepKey"
    finding_id: str                    # F-n
    content_digest: str                # 정규화 해시(§2.2)

@dataclass(frozen=True)
class BlockingFinding:
    """② CI 신뢰 산출물의 open blocking 하나."""
    key: FullBindingKey

@dataclass(frozen=True)
class ConsistencyArtifact:
    """정합성·공백 검토 CI 신뢰 산출물(판정 키에 결속). ①형식 결과를 함께 싣는다.
    불변식: review_clear == (open_blocking == ()). 위반 산출물은 기형이라 RED."""
    judgment: JudgmentKey
    format_ok: bool                    # ①형식 결과
    review_clear: bool                 # 정합성 open blocking 없음
    open_blocking: "tuple[BlockingFinding, ...]"

@dataclass(frozen=True)
class CompletenessArtifact:
    """선언 완전성 검토 CI 신뢰 산출물(완전성 스윕 키에 결속).
    불변식: completeness_clear == (open_blocking == ()). 위반 산출물은 기형이라 RED."""
    sweep_key: CompletenessSweepKey
    completeness_clear: bool           # 완전성 open blocking 없음
    open_blocking: "tuple[BlockingFinding, ...]"

@dataclass(frozen=True)
class ChannelDecision:
    """호스트 채널(PR 코멘트) 하나의 결정 표시(append-only)."""
    key: FullBindingKey
    decision: FindingDecision
    author: str
    comment_id: int                    # 스트림 순서 = comment_id (최신 유효본 승)
    created_at: str                    # ISO8601
    updated_at: str                    # created_at과 다르면 편집됨
    deleted: bool = False              # 삭제 감지
    author_role: str = ""              # 원시 사실: role_name(평가 시점 현재 값). admin 판정은 코어
    author_is_human: bool = False      # 원시 사실: 기계 계정 아님
    # 결정권(admin ∧ 명단 ∧ 사람)은 코어가 inputs.allowlist와 함께 계산한다(§2.7)

@dataclass(frozen=True)
class ApprovalEvent:
    """③ 승인 리뷰 하나. 판정은 게이트가 한다 — 어느 승인을 대표로 쓸지 포트가 고르지 않는다.
    ((b) ReviewSnapshot 선례를 복제. 단일 승인자 필드로 접으면 ③ 판정이 어댑터로 샌다.)"""
    approver: str
    approved_judgment: JudgmentKey     # 승인 시점 판정 키에 고정(재계산 금지, §2.3). 취득: §2.3 (ㄱ)/(ㄴ)
    approved_completeness: "CompletenessSweepKey"  # 승인 시점 완전성 스윕 키에 고정(재계산 금지, §2.3)
    seq: int                           # review id
    approver_role: str = ""            # 원시 사실: role_name(평가 시점 현재 값). admin 판정은 코어
    approver_is_human: bool = False    # 원시 사실: 기계 계정 아님
    dismissed: bool = False            # 호스트가 철회(dismiss-stale 등)
    # 결정권(admin ∧ 명단 ∧ 사람)은 코어가 inputs.allowlist와 함께 계산한다(§2.7)

@dataclass(frozen=True)
class PRMetadata:
    """전용 통로로 읽는 PR 메타데이터. 공유 모델 PullRequest에는 author가 없다."""
    author: str
    head_ref: str                      # PR 소스 브랜치
    head_repo: str                     # "owner/name" — 포크 판별
    head_sha: str                      # 평가 시점 head 커밋 SHA(스냅샷). 머지 head 고정용(§2.5)
    state: "PullRequestState"          # (b) 통제 어휘
    touches_sot: bool                  # 제안된 머지 결과가 SoT 트리를 바꾸는가(§2.6)
    touches_enforcement_surface: bool = False  # 강제-필수 경로를 바꾸는가(§2.6 세 번째 분기)

@dataclass(frozen=True)
class GateInputs:
    landing_judgment: JudgmentKey          # 착지 판정 키(§2.3)
    landing_completeness: "CompletenessSweepKey"  # 착지 완전성 스윕 키(§2.3)
    target_repo: str                       # "owner/name"
    allowlist: "frozenset[str]"            # 결정권자 명단(컨트롤러 도메인 구성, 저장소 밖·§2.7)
    meta: PRMetadata
    consistency_artifact: "ConsistencyArtifact | None"  # None = 정합성 산출물 없음(fail-closed)
    completeness_artifact: "CompletenessArtifact | None"  # None = 완전성 산출물 없음(fail-closed)
    decisions: "tuple[ChannelDecision, ...]"
    approvals: "tuple[ApprovalEvent, ...]"

@dataclass(frozen=True)
class GateOutcome:
    status: GateStatus
    reason: str                        # red 사유(진단; green이면 "")

SOT_BRANCH_RE = r"^sot/[a-z0-9]+(?:-[a-z0-9]+)*$"   # 규칙의 소스 브랜치 조항과 일치
DIGEST_ALGO = "sha256"
DIGEST_VERSION = 2                     # 정규화·직렬화 규약 버전 — 바뀌면 digest도 바뀜
#   v2: 각 필드·ref를 length-prefix로 경계 보존(v1의 단순 US(0x1f) join은 필드/ref 경계가 충돌).

def evaluate_gate(inputs: GateInputs) -> GateOutcome:
    """①∧②∧③를 착지 두 키(판정 키·완전성 스윕 키)에서 계산한다. 부작용 없음.

    사전 분기(§2.6):
      - meta.state != OPEN                     -> RED('pr not open')
      - meta.touches_sot                       -> 아래 SoT 검사(①②③ 전부)
      - meta.touches_enforcement_surface       -> 강제-필수 경로 검사(①② 없이):
           head_repo == target_repo ∧ (authorized(승인) ∧ approver != meta.author
           ∧ not dismissed)  아니면 RED
      - 그 밖                                   -> GREEN (pass-through)

    결정권(admin ∧ 명단 ∧ 사람)은 원시 사실로부터 코어가 계산한다:
      authorized(x) = (x.*_role == 'admin') ∧ (x.author/approver in inputs.allowlist)
                      ∧ x.*_is_human

    SoT 검사 — §2.6의 fail-closed 목록을 순서대로(두 산출물·두 키):
      ① = consistency_artifact.format_ok
      두 키 착지 일치 = consistency_artifact.judgment == landing_judgment
                      ∧ completeness_artifact.sweep_key == landing_completeness
      ② = (정합성) review_clear 또는 각 open_blocking이 유효 결정으로 닫힘
         ∧ (완전성) completeness_clear 또는 각 open_blocking이 유효 결정으로 닫힘
           유효 결정 = 완전 결속 키 일치 ∧ authorized(decision)
                      ∧ author != meta.author ∧ not deleted ∧ comment_id 최대
      ③ = 유효 승인 존재
           유효 승인 = approved_judgment == landing_judgment
                      ∧ approved_completeness == landing_completeness
                      ∧ authorized(approval) ∧ approver != meta.author ∧ not dismissed
      변조 = 두 검토 어느 쪽이든 현재 유효본으로 선택될 결정이 updated_at != created_at -> RED (§2.7)

    같은 완전 결속 키의 유효 후보 중 동일 comment_id가 둘 이상이면 미해결로 RED(결정론) — 두 검토 각각.
    """

def normalize_finding_digest(axis: str, refs: "tuple[str, ...]",
                             severity: str, body: str) -> str:
    """finding 내용 digest의 정규화 해시(§2.2). 결정적.
    유니코드 NFC -> 개행 LF 통일 -> 앞뒤 공백 제거·연속 공백 1칸 축약(대상은
    스페이스·탭만, 개행은 보존) -> refs 정렬(중복 제거) -> 각 필드·각 ref·refs 개수를
    length-prefix(<utf8 바이트 길이>0x1f<바이트>)로 경계 보존 직렬화
    (DIGEST_VERSION, axis, refs 개수+refs, severity, body) -> DIGEST_ALGO 해시.
    length-prefix라 필드/ref에 0x1f가 섞여도 경계가 이동하지 않는다(v2). refs 개수를
    실어 ()와 ("",)가 다른 digest를 낸다.
    마크다운 구조는 정규화하지 않는다(§2.2).
    ② 검토 CI와 컨트롤러가 **이 함수 하나를 똑같이 import**한다(단일 구현, 규칙 ②)."""

class GateHostPorts(ABC):
    """게이트가 호스트에서 읽고, 머지하는 것. GitHub 구현은 provisional(Phase 9 라이브)."""
    @abstractmethod
    def compute_landing_keys(self, pr: "PullRequest") -> "tuple[JudgmentKey, CompletenessSweepKey]":
        """제안된 머지 결과 상태에서 착지 두 키(판정 키 4성분·완전성 스윕 키 3성분)를 계산(§2.3)."""
    @abstractmethod
    def read_pr_metadata(self, pr: "PullRequest") -> "PRMetadata":
        """author·head_ref·head_repo·head_sha·state·touches_sot·touches_enforcement_surface.
        head_sha는 이 평가 스냅샷의 head 커밋(머지 head 고정용, §2.5). 두 touches_*는
        제안된 머지 결과 변경분으로 판정(§2.6). 공유 모델은 안 건드림."""
    @abstractmethod
    def read_ci_artifacts(self, pr: "PullRequest") -> "tuple[ConsistencyArtifact | None, CompletenessArtifact | None]":
        """②검토 CI의 두 신뢰 산출물(정합성·완전성). 각자 없거나 파싱 실패면 그 자리 None(fail-closed)."""
    @abstractmethod
    def read_channel_decisions(self, pr: "PullRequest") -> "tuple[ChannelDecision, ...]":
        """PR 구조화 코멘트(append-only) -> 결정들. 각 author의 **원시 사실**(현재 role_name,
        사람 계정 여부)과 편집·삭제 흔적(updated_at/deleted)을 채운다. 결정권 논리곱은
        코어가 inputs.allowlist와 함께 계산한다 — 포트가 admin∧명단∧사람을 접지 않는다(§2.7)."""
    @abstractmethod
    def read_approvals(self, pr: "PullRequest") -> "tuple[ApprovalEvent, ...]":
        """승인 리뷰 스트림 전체. approver의 원시 사실(role_name·사람 여부)을 채우고,
        approved_judgment·approved_completeness(두 키 모두)는 §2.3 (ㄱ) base 복원 또는
        (ㄴ) 구조화 스탬프로 취득한다(재계산 금지). 어느 승인이 유효한지는 게이트가 판정한다."""
    @abstractmethod
    def merge_pull_request(self, pr: "PullRequest", judgment: "JudgmentKey",
                           completeness: "CompletenessSweepKey", head_sha: str) -> None:
        """머지 커밋 방식으로 머지. judgment·completeness는 감사 기록용(착지 두 키). head_sha는 **평가에 쓴
        스냅샷값**(`inputs.meta.head_sha`)이며 머지 시점 재조회가 아니다 — 이를 머지 API의
        head 고정 파라미터(`sha`)로 전달한다. head가 그새 움직였으면 호스트가 거부하고,
        컨트롤러는 재평가부터 다시 한다(§2.5). base 부동은 RS-A 배타성+직렬화가 보장."""
    @abstractmethod
    def verify_ruleset_config(self) -> bool:
        """라이브 룰셋 구성이 선언 상태(RS-A/RS-B 분리·RS-B bypass 공백·필수 파라미터)와
        일치하는가(§4.1). 불일치면 False → 컨트롤러가 fail-closed로 머지 거부."""

class MergeController:
    """포트 + evaluate_gate 합성체. 전역 직렬화 하에 머지 직전 재평가 후 머지(§2.5).
    대상 저장소 밖에서 돌며, 머지 토큰은 여기에만 있다."""
    def __init__(self, ports: "GateHostPorts", target_repo: str,
                 allowlist: "frozenset[str]"): ...
    def evaluate(self, pr: "PullRequest") -> "GateOutcome":
        """읽기 포트 5개 + 주입된 allowlist로 GateInputs 구성 -> evaluate_gate.
        부작용 없음(표시 갱신용)."""
    def merge_if_green(self, pr: "PullRequest") -> "GateOutcome":
        """직렬화 잠금 획득 -> verify_ruleset_config(불일치면 fail-closed RED, §4.1)
        -> evaluate -> GREEN이면 merge_pull_request(착지 두 키 + 그 평가의 inputs.meta.head_sha를
        그대로 전달, 재조회 금지) -> 감사 기록(§2.9). RED면 머지하지 않는다.
        잠금 밖에서 계산한 결과·잠금 밖에서 읽은 head_sha는 재사용하지 않는다."""
```

### 동작 규약 (요약)
- `evaluate_gate`는 순수: 입력만으로 결과. 호스트 접근 없음.
- 세 분기(§2.6): SoT PR은 ①②③ 전부 / 강제-필수 경로 PR은 ①② 없이 포크 거부 + 결정권자 승인 / 그 밖은 열린 상태면 GREEN(pass-through).
- 결정권(admin ∧ 명단 ∧ 사람)은 **코어가 원시 사실 + `inputs.allowlist`로 계산**한다. 포트는 접지 않는다.
- ② 성립: **두 검토 각각** — 정합성은 `review_clear`(또는 각 `open_blocking`이 유효 결정으로 닫힘), 완전성은 `completeness_clear`(또는 각 `open_blocking`이 유효 결정으로 닫힘). 둘 중 하나라도 미성립이면 RED. 완전 결속 키는 자기 검토의 키(판정 키/완전성 스윕 키)에 결속하므로 정합성 결정이 완전성 finding을 닫지 못한다.
- 대조 제외: 결정권 미충족·자기결정·삭제된 결정.
- 변조는 §2.7의 좁은 정의(현재 유효본 편집)로만 판정한다. 무관한·삭제된 코멘트로 PR이 막히지 않는다.
- ③: 유효 승인이 하나라도 있으면 성립. `approved_judgment`·`approved_completeness`는 승인 시점 고정값이므로 착지 두 키(`landing_judgment`·`landing_completeness`)와 하나라도 다르면 재승인이 필요하다.
- `MergeController.merge_if_green`만 호스트를 바꾼다(머지 직전 `verify_ruleset_config` 통과 필수). 그 밖은 읽기·계산이다.

---

## 4. GitHub 강제 설정과 3-호스트 매트릭스

### 4.1 main 브랜치 룰셋 — 반드시 두 벌로 분리 (실증 확인)

> **불변식.** 두 룰셋을 하나로 합치면 안 된다. GitHub의 우회(bypass)는 **룰셋 단위**라, `update`를 통과시키려고 컨트롤러를 우회 신원으로 넣는 순간 같은 룰셋의 승인 요구까지 함께 건너뛴다. 실증에서 승인 0개인 PR이 그대로 머지됐다. 합쳐도 경고가 없으므로 컨트롤러가 구성을 감시한다(아래 **룰셋 구성 점검**).

**룰셋 구성 점검 (불변식 감시)**
- 룰셋은 admin이 PR 없이 웹 UI·API로 바꿀 수 있어 **PR 게이트 밖의 조용한 붕괴 지점**이다. 두 룰셋이 합쳐지거나 RS-B에 `bypass_actors`가 들어가면 ③이 경고 없이 사라진다(실증).
- 컨트롤러는 **기동 시와 매 머지의 직렬화 잠금 안에서** `verify_ruleset_config`(§3)로 라이브 룰셋을 선언 상태(`ENFORCEMENT_MATRIX`)와 대조한다: RS-A/RS-B가 분리돼 있고 · RS-B의 `bypass_actors == []`이며 · RS-B의 필수 파라미터(승인 수·dismiss-stale·`allowed_merge_methods`·`non_fast_forward`·`deletion`)가 존재하는가.
- 불일치면 **fail-closed로 머지를 거부**하고 경보·감사 기록을 남긴다. 컨트롤러의 직렬화 잠금은 **컨트롤러 자신의 평가~머지만** 직렬화한다 — 외부 admin이 UI·API로 룰셋을 바꾸는 것은 이 잠금이 막지 못하므로, 점검 통과 후 머지 착지 전에 구성이 약화되는 **TOCTOU 창은 잔여 위험**이다. 다음 머지의 점검이 이를 사후 검출한다. 이 창을 좁히려면 호스트 수준 보장(룰셋 변경 이벤트 감시·머지 직후 재확인)이 필요하다(§8).

**RS-A — 갱신 제한 (컨트롤러만 우회)**
- `rules: [{ "type": "update" }]`
- `bypass_actors: [{ actor_type: "User", actor_id: <컨트롤러>, bypass_mode: "always" }]`
- 효과: 컨트롤러 외 누구도 `main`을 갱신하지 못한다. 실증에서 저장소 소유자(admin)의 머지도 `Repository rule violations found — Cannot update this protected ref`로 거부됐다.

**RS-B — 승인·감사 (우회 신원 없음)**
- `rules: [{ "type": "pull_request", "parameters": { required_approving_review_count: 1, dismiss_stale_reviews_on_push: true, require_last_push_approval: true, allowed_merge_methods: ["merge"] } }]` — `require_code_owner_review`는 **현 1인 구성에선 켜지 않는다**(교착/공허, 아래 CODEOWNERS 항목). 다인 구성 전환 시 `true`로 켠다.
- `rules`에 `non_fast_forward`(force-push 차단), `deletion`(브랜치 삭제 차단) 추가.
- `bypass_actors: []`
- 효과: 컨트롤러도 승인 관문·머지 방식 제한에 걸린다. 실증에서 컨트롤러의 REST 머지가 `405 New changes require approval from someone other than the last pusher`로 거부됐다.
- **코드오너 검토(`require_code_owner_review`)는 이 증분의 필수 전제가 아니다**(Phase 3 회신 §5.3으로 검증 해소). 개인·public 저장소라 기능 제약은 없으나, 코드오너 = 소유자 = PR 작성자 1인인 현 구성에선 GitHub이 자기 PR의 코드오너 승인을 인정하지 않아 — 우회 허용하면 관문이 공허하고, 우회를 끄면 자기 PR을 자기가 승인 못 해 교착이다. 즉 **작성자 아닌 코드오너가 1인 이상 있을 때만**(코드오너 중 한 명의 승인으로 성립하므로 작성자 외 코드오너 계정이 하나만 있어도 된다 — 인용한 회신 §5.3은 이를 "리뷰어 2인 이상"으로 적었으나, GitHub은 코드오너 한 명의 승인으로 성립하므로 필요한 비작성자 코드오너는 1인이다. 본 스펙 수치가 정확하며 회신의 "2인"은 대체된다) 비공허하다. 따라서 강제-필수 경로 방어의 **1차는 게이트의 세 번째 분기(§2.6: 포크 거부 + 결정권자 명단 승인)**이고(이 증분이 독립 강제), 코드오너 검토는 다인 구성 전환 시 켜지는 **2차 관문**이다. `.github/CODEOWNERS` 파일·경로 커버리지는 Phase 3 데이터이며(회신 §5.1), 그 권위 커버리지 정의는 `axdt-critical-paths` 블록이다(§2.6). 실제 CODEOWNERS 파일 생성은 게이트 코드 정식 이관 + 다인 구성 전환 + 룰셋 활성화 시점으로 미룬다 — 실효 없는 파일이 주는 거짓 안전감을 피하기 위함이다(회신 §5.2). `.github/CODEOWNERS` 파일은 현재 어느 브랜치에도 없다(Phase 3 실측).
- ⚠ 승인은 PR 작성자가 아닌 사람이 해야 한다(`require_last_push_approval`). AXDT 운영 모델에서 SoT PR은 에이전트가 열고 사람이 승인하므로 성립한다. 사람이 직접 SoT PR을 열면 승인해 줄 다른 지정 승인자가 필요하다.

**RS-C — `sot/*` 소스 브랜치 단조 전진 (2026-07-18 신설, `ADR-0009` 결정 8 개정)**
- `rules: [{ "type": "non_fast_forward" }, { "type": "deletion" }]` — 대상 `sot/*`. **`pull_request` 룰은 담지 않는다** — PR을 강제하지 않아 에이전트의 일반 fast-forward push는 그대로 통과하고, force-push(history 재작성)·브랜치 삭제만 막는다.
- `bypass_actors: []`
- 효과: `sot/*` head가 이전 SHA로 되돌아올 수 없어(단조 전진) 컨트롤러 read-set의 **ABA 창이 닫히고**, read-set 괄호치기(§2.5·§2.8)가 완전해진다. RS-C 없이는 force-push 롤백 A→B→A가 괄호의 앞뒤 표본을 모두 A로 만들어 미평가 head 착지 경로가 남는다.
- **RS-B와 분리하는 이유**: RS-B의 `pull_request` 룰을 `sot/*`로 넓히면 `sot/*` push마다 PR을 강제해 에이전트 워크플로가 막힌다. RS-C는 `non_fast_forward`·`deletion`만 담아 이를 피한다.
- **⚠ 전제(활성화 전 확인)**: 에이전트가 `sot/*`에 rebase·amend(force-push)를 쓰지 않고 새 커밋만 얹어야 한다(fast-forward). 이 전제가 깨지면 RS-C 대신 §2.8의 (가) 대안(읽기를 head SHA에 결속하는 §3 계약 개정)으로 재검토한다.
- `verify_ruleset_config`는 기동·매 머지 점검에서 RS-C의 존재·`bypass_actors == []`도 대조한다(§3·라이브 §8).

**켜지 않는 것**
- `required_linear_history` — 머지 커밋을 금지하므로 감사 이력과 충돌.
- `merge_queue` — 개인 소유 저장소에서 룰 생성이 거부된다(실증 `422`, GraphQL `mergeQueue: null`). 직렬화는 컨트롤러가 한다(§2.5).
- 필수 검사(`required_status_checks`) — 강제 수단으로 쓰지 않는다(§2.4). ② 검토 CI의 산출물은 컨트롤러가 직접 읽는다.

**전제조건**
- 개인 소유 **private** 저장소 + 무료 플랜에서는 룰셋도 구식 브랜치 보호도 `403`으로 거부된다. AXDT 저장소는 공개로 전환해 이 전제를 충족했다(2026-07-09). private 유지가 필요해지면 GitHub Pro 이상.
- 공개 저장소는 포크 PR을 허용하므로 §2.6의 `head_repo != target_repo` 검사가 실전 방어가 된다.

### 4.2 ② 검토 CI 계약 (실체 provisional)
- 트리거: **각 키(판정 키·완전성 스윕 키)가 바뀔 때 그 키의 검토를 1회 실행**한다(규칙 ②의 키당 1회). 제안된 머지 결과에서 두 키를 계산해 **완료된 산출물이 없는 키의 검토만** 돈다 — 판정 키는 SoT 트리·적용 rule 지문·`review_policy_epoch`·카탈로그 manifest 변경에, 완전성 스윕 키는 projection 트리·활성 카탈로그 입력 digest·epoch 변경에 바뀐다(SoT 경로 변경뿐 아니라 rule 본문 편집·base 전진도 키를 바꿔 검토를 발화한다).
- **적용 rule 지문을 제안된 머지 결과 상태에서 계산**한다(그 트리에 적용될 규칙 기준). 검사 코드·정책만 신뢰 base에서 읽는다 — "머지 결과에서 계산"과 "base에서 읽음"을 혼동하지 않는다.
- **콘텐츠당 1회**: **각 키(정합성=판정 키, 완전성=완전성 스윕 키)에 대해** 이미 완료된 산출물이 있으면 그 검토를 재실행하지 않는다 — `review_clear`/`completeness_clear`든 `review_blocked`/`completeness_blocked`든 완료된 검토다. 차단 결과를 재실행하면 비결정적 검토기가 매번 다른 finding을 내어 사용자 결정이 무효가 되는 순환에 빠진다(규칙 ②의 콘텐츠당 1회 조항). 미선언 rule 본문 편집처럼 완전성 스윕 키만 바뀌면 완전성 검토만 재실행된다.
- 산출 = **두 신뢰 산출물** — 정합성(판정 키 + open blocking `[F-n+digest]` + 형식 결과; verdict `review_clear`/`review_blocked`)과 완전성(완전성 스윕 키 + open blocking `[F-n+digest]`; verdict `completeness_clear`/`completeness_blocked`).
- 산출물은 컨트롤러가 읽는다. 커밋 상태는 push 권한자가 임의 이름으로 위조할 수 있으므로 **강제의 근거로 쓰지 않는다** — 컨트롤러는 각 산출물의 키(정합성=판정 키, 완전성=완전성 스윕 키)가 착지 두 키와 일치하는지 스스로 확인하고, 불일치·부재·기형이면 fail-closed다.
- **두 키 대조만으로는 위조를 막지 못한다 — 진짜 방어선은 산출물 저장 위치의 쓰기 통제다.** 두 키는 공개 콘텐츠(제안된 머지 결과)의 결정적 함수라 비밀도 작업 증명도 아니다 — 작성자는 자기 PR의 두 키를 사양대로 계산할 수 있다. 위협은 남의 키를 도용한 재전송이 아니라, `review_blocked`/`completeness_blocked`가 뜬 작성자가 **자기 키에 대해** `review_clear`/`completeness_clear`·`format_ok`·blocking 0건짜리 (정합성·완전성) 산출물을 밀어 넣는 것이다. 이를 막는 것은 "**신뢰된 ② CI 신원만 산출물을 쓸 수 있다**"는 쓰기 통제(또는 CI 신원의 서명)이고, 두 키 대조는 **재전송(다른 콘텐츠의 산출물 재사용) 방지용**이다. 같은 저장소 브랜치 PR에는 시크릿이 전달되므로(실증), ② CI가 저장소 안에서 돌며 산출물 저장소에 쓸 수 있는 구성이면 이 쓰기 통제가 뚫린다. **산출물 저장소의 쓰기 신뢰 모델은 하중을 받는 보안 요소다**(§8).
- `②검토`는 PR 코드를 실행하지 않고 SoT 트리 **데이터만** 읽는다. SoT 문서 내용이 검토기 프롬프트에 들어가므로 **프롬프트 주입 잔여 위험**이 있다 — 문서에 심긴 지시문이 검토기를 오도할 수 있다. 검토기 출력은 구조화 산출물로만 소비하고 자유 텍스트를 신뢰하지 않는다.
- 실행은 작성 세션과 분리(자기검토 편향 방지). 실행 모델·프롬프트는 감사 로그(비신뢰 사본)에 기록.

### 4.3 3-호스트 강제 매트릭스 (미래 멀티호스트 Phase 선행 스케치 — 이 증분 범위 밖)

| 강제 요구(호스트 중립) | GitHub (실증) | GitLab (provisional) | Forgejo (provisional) |
|---|---|---|---|
| `main` 갱신을 컨트롤러로 제한 | 룰셋 `update` + bypass=컨트롤러 계정 | protected branch: "Allowed to merge = 컨트롤러" | branch protection: whitelist merge = 컨트롤러 |
| 컨트롤러가 승인을 우회하지 못함 | **룰셋 분리 필수**(bypass는 룰셋 단위) | approval rule은 별도 객체 — 분리 기본 | 승인 설정 별도 |
| 승인 + dismiss-stale | "Require approvals" + "Dismiss stale approvals" | approval rules + "Remove approvals on push" (필수 승인 강제는 **Premium**으로 보임 — provisional) | "Enable Approvals" + "Dismiss stale approvals" |
| 지정 승인자 명단 | 게이트가 검사 + CODEOWNERS 백스톱 | 게이트가 검사 + Code Owners(**Premium**) | 게이트가 검사 + 승인 화이트리스트(CODEOWNERS 강제 불가) |
| 감사 이력 보존 | 룰셋 `allowed_merge_methods: ["merge"]` + `non_fast_forward` + `deletion` | MR "Squash = Do not allow" + force-push 차단 | merge commit만 활성 + force-push·삭제 차단 |
| 머지 직렬화 | 컨트롤러(merge queue 불가) | 컨트롤러 | 컨트롤러 |
| 채널 결정 read + 권한 | PR comments + `role_name`==admin | MR notes + access level(50=Owner) | PR comments + admin(maintain 경계 흐릿) |

> 이 설계가 필수 검사에 기대지 않으므로 GitLab 티어 의존(external status checks = Ultimate)이 사라진다. 남는 티어 의존은 Code Owners(Premium)와 **GitLab의 필수 승인 강제(Premium으로 보임)**로, 필수 승인 독립 관문의 성립 여부는 호스트 티어에 따라 다르다 — 그 경우에도 게이트의 자체 명단·승인 검사는 티어 무관하게 남으므로 설계는 성립한다. Forgejo의 CODEOWNERS 강제 불가도 같은 이유로 치명적이지 않다. 티어 경계는 멀티호스트 Phase에서 확인한다(provisional).

---

## 5. 패키지 레이아웃 (D12 → `WIP/`)

```
WIP/axdt/sot_gate/
  __init__.py
  keys.py             # JudgmentKey, CompletenessSweepKey, FullBindingKey, normalize_finding_digest
  models.py           # ConsistencyArtifact, CompletenessArtifact, BlockingFinding, ChannelDecision, ApprovalEvent,
                      #   PRMetadata, GateInputs, GateOutcome, GateStatus, FindingDecision
  gate.py             # evaluate_gate(순수)
  controller.py       # MergeController(직렬화·재평가·머지·감사 기록)
  ports.py            # GateHostPorts(ABC) + FakeGatePorts(테스트)
  hosts/
    __init__.py; github.py            # GitHubGatePorts (gh api) — provisional
  ENFORCEMENT_MATRIX.md; README.md
  tests/
    __init__.py; test_keys.py; test_models.py
    test_gate.py; test_controller.py; test_ports.py
```

> `sot_gate`는 (b) `git_host`의 통제 어휘(`PullRequest`/`PullRequestState`)를 소비하되 강제 계산은 독립. 룰셋 설정은 코드가 아니라 선언적 셋업 문서 + `ENFORCEMENT_MATRIX`.

---

## 6. 테스트 (계약 고정)

- **test_keys**: `JudgmentKey`(4성분)/`CompletenessSweepKey`(3성분)/`FullBindingKey` 불변·동등성. **두 키 타입이 다르면(판정 키 vs 완전성 스윕 키) 같은 finding_id·digest여도 완전 결속 키가 동등하지 않다**(교차 무효화 없음). `normalize_finding_digest` 결정성 — 공백·항목 순서·**유니코드 NFC·개행(CRLF↔LF)** 변형이 같은 digest를 낸다. 축·참조·심각도·본문이 다르면 다른 digest. `DIGEST_VERSION` 변경 시 digest가 달라진다. **마크다운 변형 동일성은 요구하지 않는다**(§2.2).
- **test_models**: 데이터클래스 불변; `GateInputs`/`GateOutcome` 구성.
- **test_gate** (`evaluate_gate` 순수, 기본 입력은 `touches_sot=True`·head_ref=`sot/x`·head_repo==target_repo·결정자≠PR작성자·결정자/승인자 `role_name==admin`·`is_human`·`inputs.allowlist`에 등재·**두 산출물(정합성·완전성) 모두 clear**·**두 키 각각 삼자 일치**(landing = artifact = approval)):
  - (a) `review_clear` + `format_ok` + 유효 승인 → GREEN.
  - (b) open blocking 전부 accepted/rejected(유효 결정) → GREEN.
  - (c) open blocking 중 하나가 미대조 → RED.
  - (d) 결정자의 현재 `role_name != admin`(또는 `inputs.allowlist` 밖·기계 계정) → 결정권 미충족 → 폐기 → RED. 강등은 즉시 반영된다.
  - (d2) 결정자가 표시 당시엔 명단 밖이었으나 현재 `role_name==admin` ∧ `inputs.allowlist` 등재 ∧ 사람 → 유효 → GREEN. **승격은 소급한다**(§2.7) — 게이트는 표시 시점 권한이 아니라 현재 원시 사실만 입력으로 받는다.
  - (e) supersession: 같은 완전 결속 키에 rejected 후 accepted(더 큰 `comment_id`) → accepted 적용.
  - (f) `approved_judgment != landing_judgment` → RED.
  - (f2) `consistency_artifact.judgment != landing_judgment`(트리 같고 rule 지문만 다름, 또는 `review_policy_epoch`·카탈로그 manifest만 다름) → RED — **판정 키 성분 불일치**.
  - (g) `consistency_artifact=None` → RED.
  - (h) `consistency_artifact.format_ok=False` → RED.
  - (i) 완전 결속 키의 finding_id/digest가 산출물과 다른 결정 → 대조 실패 → RED.
  - (j) `head_ref`가 `sot/<slug>` 정규식에 안 맞음 → RED. `sot/A_B`·`sot/x/y`·`sot/`도 거부.
  - (k) 승인자가 `role_name != admin` / `inputs.allowlist` 밖 / 기계 계정(`approver_is_human=False`) → RED. 결정권 논리곱은 코어가 계산한다.
  - (l) 결정 author == PR author → 폐기 → RED. 승인자 == PR author → RED.
  - (m) 정합성 산출물 불변식 위반(`review_clear=True`+blocking≠∅, 또는 그 역) → RED.
  - (n) **현재 유효본으로 선택될 결정이 편집됨**(`updated_at != created_at`) → RED (변조 나, §2.7).
  - (n2) **무관한 코멘트가 편집·삭제됨**(유효본도 아니고 open blocking을 닫지도 않음) → GREEN — 서비스 거부 방지(§2.7).
  - (n3) **낡은 판정 키에 붙은 결정이 변조됨** → 현재 대조 대상이 아니므로 GREEN.
  - (n4) **유효본을 닫던 결정이 삭제됨** → 그 결정이 대조에서 빠져 open blocking이 미대조 → RED(항목 8, 별도 변조 조항 없이).
  - (o) `pr_state != OPEN` → RED('pr not open').
  - (p) 같은 완전 결속 키의 유효 후보 중 동일 `comment_id`가 둘 이상(결정값 무관) → 미해결로 RED(결정론).
  - (q) `head_repo != target_repo`(포크) → RED.
  - (r) **`touches_sot=False` ∧ `touches_enforcement_surface=False`** → 산출물이 없고 승인도 없어도 GREEN (pass-through).
  - (s) `touches_sot=False`이고 `pr_state != OPEN` → RED.
  - (t) **승인이 여러 개**: 유효 하나 + 무효 여럿 → GREEN. 전부 dismissed → RED.
  - (u) `approvals=()`(승인 없음) → RED.
  - (v) **`touches_enforcement_surface=True`·포크**(`head_repo != target_repo`) → RED — ①② 없이도 포크 거부.
  - (w) **`touches_enforcement_surface=True`·포크 아님·결정권자 승인 존재** → GREEN — 산출물·①②를 요구하지 않는다(강제-필수 경로 분기).
  - (x) **`touches_enforcement_surface=True`·결정권자 승인 없음**(또는 승인자 결정권 미충족, 또는 승인자==PR작성자) → RED.
  - (y) `touches_sot=False`·`touches_enforcement_surface=False`·OPEN → GREEN (pass-through, (r) 재확인).
  - **(2키 — 완전성 검토·교차 키)**
  - (z1) `completeness_artifact=None`(정합성 산출물은 정상) → RED (항목 4).
  - (z2) 완전성 산출물 불변식 위반(`completeness_clear=True`+blocking≠∅, 또는 그 역) → RED (항목 5).
  - (z3) `completeness_artifact.sweep_key != landing_completeness` → RED — **완전성 스윕 키 불일치**(항목 7).
  - (z4) 완전성 `open_blocking` 중 미대조(정합성은 clear) → RED (항목 8).
  - (z5) 완전성 `open_blocking` 전부 accepted/rejected(그 finding의 완전 결속 키 `review_key` = 완전성 스윕 키) → GREEN.
  - (z6) `approved_completeness != landing_completeness`(판정 키는 일치) → RED (항목 10).
  - (z7) **교차 키**: 완전성 finding을, 같은 `finding_id`·`content_digest`이나 `review_key`가 판정 키인 결정으로 닫으려 함 → 완전 결속 키 불일치로 미대조 → RED (표시는 자기 검토의 키에만 결속, §2.2·규칙 §②).
  - (z8) 정합성 `review_blocked`이나 전부 accepted ∧ 완전성 `completeness_clear` → GREEN (두 검토 독립 성립).
- **test_controller** (`FakeGatePorts` + `MergeController`):
  - `merge_if_green`이 GREEN일 때만 `merge_pull_request`를 호출한다(호출 기록으로 검증).
  - RED면 머지하지 않는다.
  - **머지 직전 재평가**: 평가와 머지 사이에 포트가 다른 값을 돌려주도록 스크립트하면(승인 철회), 머지가 일어나지 않는다.
  - **룰셋 구성 점검 실패**: `verify_ruleset_config`가 False면 GREEN 판정이어도 머지하지 않는다(fail-closed, §4.1).
  - **head 고정**: `merge_pull_request`에 그 평가의 `inputs.meta.head_sha`가 전달된다(머지 시점 재조회값이 아님을 인자로 검증). 평가 후 head가 바뀌도록 포트를 스크립트하면 전달값은 옛 SHA이고, 호스트가 거부하도록 하면 머지되지 않고 재평가로 돈다.
  - 직렬화: 동시 호출이 겹치지 않는다.
  - 감사 기록이 착지 두 키(판정 키·완전성 스윕 키)·반영된 결정·승인 이벤트·base SHA를 담는다.
- **test_ports**: `FakeGatePorts`가 7개 포트(read 5 = `compute_landing_keys`·`read_pr_metadata`·`read_ci_artifacts`·`read_channel_decisions`·`read_approvals` + `merge_pull_request` + `verify_ruleset_config`)를 모두 만족한다. `read_ci_artifacts`가 어느 산출물이든 None을 돌려주면 → RED.

---

## 7. 초기 마이그레이션 · 롤아웃

- **활성화 = 규칙의 재검토 트리거가 정한 강제 도입 시점.** 기존 완료 문서 전량에 **선언 완전성 검사(완전성 스윕 키에 결속)를 최초 1회 스윕**해 `rules` 선언 완전성을 확립한다 — 선언 완전성은 정합성 4축의 한 축이 아니라 활성 rule 카탈로그 본문 전량을 입력으로 보는 **별도 검토**다(규칙 §②). 현재 `docs/sot/{requirements,specification,test-design}`에는 `README`·`_TEMPLATE`뿐이라 **스윕 대상이 0건**이다(2026-07-09 실측).
- **마이그레이션 워크플로**: ② 선언 완전성 검사를 전량 1회 실행 → **완전성 스윕 키**·baseline finding을 **전용 마이그레이션 PR의 구조화 코멘트**(동일 호스트 채널, append-only)로 게시(완전 결속 키는 완전성 스윕 키에 결속). 기존 main 문서엔 PR이 없으므로 이 PR을 채널로 연다(파일 결정 금지). admin이 accept/reject로 닫는다(`FindingDecision`에 RESOLVED 없음 — 'resolve' 어휘 폐기).
- **마이그레이션 PR의 소비와 수명**: 이 PR은 SoT를 바꾸지 않으므로 머지하지 않는다. baseline finding이 전부 닫히면 컨트롤러가 그 스냅샷을 자기 감사 기록에 옮기고 PR을 닫는다. 닫힌 뒤에도 코멘트는 남아 감사 이력이 된다. **이 결정은 머지 게이트의 입력이 아니다** — `read_channel_decisions`는 평가 중인 PR의 코멘트만 읽는다(§3). 감사 기록으로 이관된 뒤에는 Phase 8 트리거(D6)의 입력일 뿐이며, 이후 같은 두 키의 SoT PR은 자기 채널에서 결정을 다시 받는다.
- **활성화 순서**: RS-B(승인·감사)를 먼저 켜고, 컨트롤러가 살아 있음을 확인한 뒤 RS-A(갱신 제한)를 켠다. 순서를 뒤집으면 컨트롤러가 준비되기 전에 모든 머지가 멈춘다.
- **활성화 전제조건 (변경 측 통보 규약, Phase 3 회신 §5.2·§6·후속).** Phase 6 활성화 전에 반드시: (ㄱ) 게이트·컨트롤러 코어 코드 경로가 `axdt-critical-paths` 블록에 등재돼 있어야 한다 — PR #17 블록은 현재 위치 `WIP/axdt/sot_gate/**`를 이미 잠정 등재했으므로(그 블록이 `main`에 착지하는 것은 (ㅁ) 소관), 지금 추가할 것은 없다. 남은 통보는 코드가 §8의 정식 위치(`WIP/` 밖)로 이관될 때 Phase 6가 변경 측으로서 Phase 3에 경로 갱신을 통보하는 것이다. 이 등재가 빠지면 게이트 코드 자체가 강제-필수 분기에 걸리지 않는다. (ㄴ) 결정권자 명단은 저장소 **밖**(컨트롤러 도메인)에 두기로 확정했으므로(§2.7·§10) 이 통보는 **해당 없다** — 명단을 저장소 안에 두는 구성으로 바뀌면 그때 그 경로를 블록에 추가 통보한다. (ㄷ) 코드오너 검토를 방어 축(2차 관문)으로 쓰려면 다인 구성(작성자 ≠ 코드오너) 전환이 선행돼야 한다(§4.1) — 그전까지 방어는 게이트의 결정권자 명단 승인 하나다. (ㄹ) `ADR-0009`가 `main`에 착지하면 Phase 3가 `rule-protected-paths`의 forward 표기를 확정 참조로 정리하므로 착지 시 통보한다. (ㅁ) 필요 경로가 모두 반영된 `axdt-critical-paths` 블록이 신뢰 base(`main`)에 착지해 게이트가 읽고 파싱할 수 있어야 한다 — §2.2가 정책을 신뢰 base(`main`)에서 읽도록 요구하므로, 블록이 `main`에 없거나 기형이면 강제-필수 판정의 유일 입력이 비어 fail-closed로 막는다(그 상태에서 강제-필수 분기를 켜면 해당 PR을 무관문 통과시키지 않고 RED). 이 판독·파싱은 컨트롤러가 머지 직전 잠금 안에서 `verify_ruleset_config`와 같은 **사전 관문**으로 수행하며, 실패를 `PRMetadata.touches_enforcement_surface=False`로 접지 않고 `evaluate_gate`에 앞서 직접 fail-closed RED로 처리한다(불리언은 블록이 읽힐 때만 계산되므로 "못 읽음"이 pass-through로 새지 않는다). 이 계약과 테스트는 블록 읽기·glob 매칭 포트 구현과 함께 둔다(§8 provisional).
- **test-design 공백 = 엄격 차단 + 백필**: req+spec만으로 완료됐던 문서는 test-design(`ADR-0008`)이 빠져 fail-closed로 떨어진다. 유예 없이 백필한다. 게이트가 신규 도입이라 영향분은 작다(현재 0건).
- **되돌리기**: RS-A를 지우면 즉시 사람이 머지할 수 있다. 컨트롤러 장애 시 비상 경로다(다만 그 순간 ①②③ 강제가 사라지므로 기록을 남긴다).

---

## 8. provisional (라이브 — 강제용 `ENFORCEMENT_MATRIX.md`)

실증으로 확정된 것(룰셋 분리·bypass 단위·`update` 룰의 관리자 적용·`allowed_merge_methods`·merge queue 불가·private 무료 플랜의 `403`)은 provisional에서 뺀다. 남은 것:

- ② 검토 CI 워크플로 실체(검토 실행기·두 키(판정 키·완전성 스윕 키) 계산 잡·정합성/완전성 두 검토 실행).
- ~~개인 소유 저장소의 `require_code_owner_review` 허용 여부~~ — **해소(Phase 3 회신 §5.3)**: 기능 제약 없음. 다만 1인 구성에선 셀프 승인 불가로 실효 없어 필수 전제로 두지 않고, 작성자 아닌 코드오너 1인+ 확보(다인 구성) 전환이 코드오너 검토 유효화의 활성화 전제조건이다(§4.1·§7). provisional 아님.
- `gh api` 스키마: PR 코멘트 조회, `collaborators/{login}/permission`의 `role_name`, 리뷰 스트림, 머지 API의 거부 코드.
- 코멘트 편집·삭제(변조 나) 감지 방식(타임스탬프 비교 대 이벤트).
- **승인 두 키(`approved_judgment`·`approved_completeness`) 취득**: (ㄱ) 감사 기록·`main` first-parent로 승인 시각 base 복원(한 번의 착지 계산이 두 키를 함께 낸다) / (ㄴ) 승인 본문 구조화 스탬프(두 키 모두 명시) — 둘 중 실제 채택과 구현(§2.3).
- **산출물 저장소의 쓰기 신뢰 모델**: 신뢰된 ② CI 신원만 쓰도록 하는 방식(전용 저장 위치의 쓰기 통제 또는 CI 신원 서명) 및 같은 저장소 브랜치 PR의 시크릿 전달과의 관계(§4.2).
- **`verify_ruleset_config`의 라이브 룰셋 조회 스키마**: RS-A/RS-B 분리·RS-B bypass 공백·필수 파라미터를 `gh api`로 읽어 선언 상태와 대조하는 방식(§4.1). 아울러 **외부 admin의 룰셋 변경 TOCTOU 창**(점검 통과 후 머지 착지 전 약화)을 좁히는 호스트 수준 보장 — 룰셋 변경 이벤트 감시 또는 머지 직후 재확인.
- 두 키의 정확한 계산 정의(판정 키 4성분: 트리 해시·적용 rule 지문·`review_policy_epoch`·카탈로그 manifest digest / 완전성 스윕 키 3성분: projection 트리 해시·활성 카탈로그 입력 digest·epoch — 정규화·직렬화는 규칙 §②이 정본)와, 컨트롤러가 제안된 머지 결과를 얻는 방법.
- `touches_sot`·`touches_enforcement_surface`를 머지 결과 변경분에서 얻는 방법(변경 경로 집합 취득 + glob 매칭 구현). 강제-필수 경로의 **권위 정의는 해소** — `rule-protected-paths`의 `axdt-critical-paths` 블록이며 게이트가 `critical <glob>` 줄을 유일 입력으로 읽는다(Phase 3 회신 §5.4·§2.6). 남은 provisional은 변경분 취득·glob 매칭 구현뿐이다. 정본 블록의 `main` 착지(사용자 게이트 PR) 후 확정 인용으로 정리한다.
- 각 키(판정 키·완전성 스윕 키)당 1회 재사용의 산출물 조회 방식(산출물 저장소).
- 컨트롤러 호스팅·기동·머지 토큰 발급 범위·직렬화 잠금 구현.
- 사람 계정 대 기계 계정 판별(호스트가 구분하지 않으면 명단 자체로 판별).
- GitLab/Forgejo 전부(별도 멀티호스트 Phase).

---

## 9. 다음 단계 접합

- **Phase 8(오케스트레이션)**: 게이트 green/red를 소비해 개발 시작 트리거(D6)와 일시정지·재개를 제어. blocking이 이미 착수된 작업에 미치는 효과는 트리거 상태 머신(Phase 8).
- **Phase 9(라이브 도그푸딩)**: 실제 저장소에 RS-A/RS-B 적용, 컨트롤러 배포, `gh api` 스키마 확정, `ENFORCEMENT_MATRIX` 라이브 검증.
- **미래 멀티호스트 Phase**: GitLab/Forgejo 강제 realization(§4.3 매트릭스가 선행 스케치).
- **Phase 3**: 허브 `main` ref 보호(균일 ref 규칙)는 이 호스트 강제와 별개 층(`ADR-0007`).

---

## 10. 확정된 결정

- **강제 = 머지 컨트롤러**가 `main`의 유일 갱신 권한자로서 머지 직전에 `①∧②∧③`를 계산하고 초록일 때만 머지한다. 필수 검사를 강제 수단으로 쓰지 않는다.
- **룰셋 두 벌 분리가 불변식**이다. 합치면 컨트롤러가 승인 관문을 함께 우회한다(실증).
- **두 키(판정 키·완전성 스윕 키)가 각각 세 지점(착지·검토·승인)에서 일치**해야 초록. 승인의 두 키는 승인 시점에 고정하며, 취득은 base 복원 또는 구조화 스탬프로 한다(재계산 금지, §2.3).
- **머지 전역 직렬화 + 머지 직전 재평가**로 낡은 판정을 구조적으로 배제한다. base 부동은 RS-A 배타성+직렬화가, head 이동은 평가 head SHA 고정이 막는다 — 호스트의 base 거부에 기대지 않는다.
- **룰셋 구성 점검**을 머지 직전 잠금 안에서 수행하고, RS-A/RS-B 분리·bypass 공백이 깨졌으면 fail-closed로 머지를 거부한다.
- **분기는 셋**: SoT PR은 ①②③ / **강제-필수 경로 PR은 ①② 없이 포크 거부 + 결정권자 승인**(규칙·CI·CODEOWNERS·게이트 코드 갈아치우기 차단) / 그 밖은 pass-through. 판단은 머지 결과 변경분으로 한다. 강제-필수 경로는 `rule-protected-paths`의 `axdt-critical-paths` 블록을 **유일 입력**으로 읽는다(Phase 3 소유·손사본 금지).
- **결정권 = admin ∧ 지정 명단 ∧ 사람 계정** — 논리곱은 코어가 원시 사실+주입된 명단으로 계산한다(포트가 접지 않는다). 명단은 컨트롤러 도메인 구성. 권한은 평가 시점의 현재 값(승격은 소급 유효). 코드오너 검토는 **다인 구성에서만 유효한 2차 관문**이며 필수 전제가 아니다 — 1차 방어는 결정권자 명단 검사다.
- **변조 차단은 현재 유효본 편집에만** 적용해 서비스 거부를 막는다(초기 (가) 조항은 발화 불가라 폐기). 삭제된 결정은 미대조 RED로 잡힌다.
- **② 산출물의 신뢰는 저장 위치의 쓰기 통제**다 — 두 키는 공개 함수라 위조 방지가 아니고, 대조는 재전송 방지용이다.
- **감사 이력은 호스트가 강제**(`main`의 `allowed_merge_methods`·force-push 차단), 컨트롤러의 선택은 보조. **`sot/*` 소스 브랜치도 force-push·삭제를 차단**해 단조 전진만 시킨다(RS-C, §2.8·§4.1 — 2026-07-18 `ADR-0009` 결정 8 개정: 컨트롤러 read-set의 ABA 창을 닫는다). 승인~머지 창은 merge commit 보존·dismiss-stale·head SHA 고정이 별도로 막는다(§2.5). 컨트롤러 도메인에 불변 감사 기록.
- **전제조건** = 룰셋을 걸 수 있는 저장소 구성(공개 전환으로 충족).
- **테스트 경계** = `evaluate_gate`·`normalize_finding_digest`는 순수 TDD; 포트 GitHub 구현·CI 워크플로·컨트롤러 호스팅은 provisional.
