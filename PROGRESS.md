## 2026-09-01 13:22 (작업 PC: 로컬) — 세션 61 (**PR #82 머지 완료** — 화자 매핑 리팩터링 PR C 종료)

- 브랜치: **`main`** (머지 커밋 `9ceec34`). `refactor/speaker-label-mapping-c`는 squash 머지 후
  원격·로컬 모두 삭제. 로컬에 남은 브랜치는 `main` 하나뿐(`git branch -a`로 확인).
- **PR #82 MERGED** (2026-09-01T04:19:36Z). 36파일 +5454/−379.
  이로써 **화자 매핑 리팩터링 3부작(PR A/B/C) 종료** — CLAUDE.md가 "다음 작업 1순위"로 지정했던
  "화자 이름을 문자열 토큰이 아니라 라벨 기준으로 다룬다"가 완료됐다.
- 이번 세션에 한 일 (세션 60에서 이어짐):
  1. 코드리뷰 잔여 지적 2건 수정 — director(dir-c5)+front-c5+back-c5 팀 구성해 처리
     - `ff61e47` (front-c5) — `DEVGUIDE.md` §10의 `[후속 과제]` 항목이 **이미 고친 결함을
       미해결로 기술**하던 것을 `[확정]`으로 정정. 커밋 순서 실측: 문서 `8e16cb0`(00:20)이
       "미해결"로 적힌 **뒤** 코드 `8c47a56`(07:15)이 근본 원인을 고쳤는데 문서를 안 고친 것이었다.
       정정문에 해소 커밋·현재 계약(3곳 전부 `render(seg, {})`)·**재유입 경고**를 넣고, 기존 사실
       2건(서버 `restore_segment_labels` 방어는 계속 필요 / `TranscriptEditor`는 애초에 무관)은 보존.
     - `b11c74e` (back-c5) — `scripts/migrate_legacy_speaker_map.py`의 tie-break 사본 제거.
       죽은 코드였던 `_representative`를 **삭제가 아니라 소생**시켜 단일 출처로 삼고,
       `_merge_duplicate_names` L203의 인라인 재구현을 그 호출로 교체(정확히 1줄).
       삭제 대신 소생을 택한 이유: 그 docstring이 "이건 PR B에서 지운 overlap 휴리스틱이 아니다"라는
       **재유입 방지 논증**을 담고 있어, 지우면 규칙이 50줄 함수 한가운데 인라인으로만 남는다.
  2. 팀리드 직접 검증(팀원 보고를 그대로 믿지 않는 규칙) — `c2deb03..b11c74e` 전체 diff가
     **2파일 2+/2−**임을 눈으로 확인, 문서가 인용한 행 번호(`Transcript.tsx` L186·196·208)가
     실제 코드와 일치하는지 `grep`으로 대조, `_representative` 정의 1 + 호출 1 확인.
  3. 푸시 → squash 머지 → 브랜치 정리 → **main에서 테스트 재실행**
     (백엔드 359 passed / 프론트 48 passed / `tsc --noEmit` 0).
- **머지하며 남긴 것 (다음 사람이 알아야 할 것)**:
  - `_merge_duplicate_names` docstring(L169-170)에 tie-break 규칙이 **산문으로** 한 번 더 있다.
    실행되지 않으므로 "조용히 다른 결과를 내는" 위험은 아니라고 판단해 이번엔 손대지 않았다
    (코드 프리즈를 2건 한정 해제한 상태였다). 나중에 규칙을 바꾸면 이 문장도 같이 고칠 것.
  - **공개 저장소에 실명(`아빠`·`손주환`·`손재락`)과 실제 job ID가 들어가 있다.**
    `gh repo view` 실측 `isPrivate: false`. main에도 이미 있던 것이나 PR C가 신규 테스트 파일과
    §10에서 범위를 넓혔다(신규 83행). 전역 보안 규칙("개인정보도 동일하게 마스킹")에 걸린다.
    리뷰 채점 50점이라 머지를 막지는 않았으나 **후속 과제로 남긴다** — 픽스처를 `김팀장`류
    placeholder로 교체할 것.
- **다음 할 일 (1순위)**: **회의 전환 시 이전 회의 상태 잔존 (전 5건, rematch가 최악 —
  화자 이름이 DB에 잘못 기록됨)**. 상세는 `docs/ai_analysis/20260828_잔여_기획_후보.md`의
  "★ 다음 PR 확정 안건". 여기에 `showResummarizeModal`이 job 전환 시 안 닫히는 결함
  (PR C에서 증상만 차단하고 원인은 미수정)도 함께 들어간다.
- **2순위**: `backend/tests/conftest.py` 신설 + `DB_PATH` tmp 격리.
  **`pytest tests/`가 여전히 운영 DB를 오염시킨다**(1회 실행당 `recording_notes` +2행).
  이번 세션에도 백업→실행→복원으로만 넘겼다. 최종 md5 `837db16f24128f8893409744429b37dd`
  (510행)로 원복 확인. **다음 사람도 pytest 전에 반드시 백업할 것.** 제품 결함이 아니라
  개발 인프라 결함이며, 지금 `meetings` 테이블이 무사한 건 운이 좋았을 뿐이다.
- 막힌 점: 없음. 팀원(dir-c5/front-c5/back-c5) 전원 종료 완료.
- 관련 파일/커밋: `9ceec34`(main 머지 커밋), `ff61e47`, `b11c74e`
- 푸시 여부: **origin/main 반영 완료 (PR #82 squash 머지). 원격 브랜치 삭제됨.**

### 내일 이어서 시작할 것 (2026-09-01 13:3x 추가)
- **인수인계 문서: `docs/ai_analysis/20260901_다음_작업_인수인계.md`** — 현재 사용 가능 상태,
  남은 작업 4건, 내일 시작 순서가 전부 여기 있다. **이 파일 하나만 읽으면 이어갈 수 있다.**
- **앱은 정상 사용 가능하다.** 실측: 백엔드 8000 / 프론트 3000 재기동 후 `/api/jobs` 회의 10건
  정상 반환, 프론트 HTTP 200.
- **"기존 데이터가 안 보인다" 증상의 원인은 DB가 아니라 백엔드 미기동이었다.** 프론트(3000)만
  떠 있고 백엔드(8000)가 죽어 있었다(당시 돌던 uvicorn은 다른 프로젝트 `mflex-demo` 8010이었다 —
  포트만 보고 오판하기 쉽다). 재시작으로 해결. DB는 무손상(`meetings` 10행, `-wal`/`-shm` 없음).
  **같은 증상 재발 시 `lsof -iTCP:8000 -sTCP:LISTEN -n -P` 부터 확인할 것.**
- 착수 지점: `git checkout -b fix/job-switch-state-leak` →
  `docs/ai_analysis/20260828_잔여_기획_후보.md` 160행~ 정독 → `meeting-jr-dev` 스킬(프로세스 B).
- 1순위 견적(코드 실측 기반 추정): **작업 세션 1회(집중 3~5시간)**, 회귀 시 최대 2세션.
  구현은 작다(`<MainArea key={job.id}>`는 사용처 2곳뿐이라 실질 2줄) — 시간은 검증이 먹는다.
  rematch(1번)에 서버측 방어까지 넣기로 결정하면 +1세션.

---

## 2026-09-01 13:20 (작업 PC: 로컬) — 세션 60 (PR C 검증·푸시·코드리뷰 완료, 머지 대기)

- 브랜치: `refactor/speaker-label-mapping-c` — **PR #82 OPEN, MERGEABLE, 아직 미머지**
  (https://github.com/jaerakson/meeting-jr/pull/82). 최신 커밋 `e16158e`, **origin 푸시 완료**
  (세션 59에서 밀려 있던 로컬 27커밋을 이번에 푸시 — `2f09afc..e16158e`).
- 팀원 4명(dir-c4 / front-c4 / back-c4 / qa-c4)은 이번 세션 시작 시 **전원 종료**했다.
  세션 59에서 "진행 중"으로 남아 있던 B2~B7 / T10 / F3 / 중복 표시이름 픽스처는
  종료 전에 모두 커밋 완료된 상태였다(아래 검증으로 확인).
- 완료:
  - **검증 전량 재확인(세션 59가 "다음 사람이 반드시 재확인할 것"으로 남긴 항목)**
    - 백엔드: `pytest tests/ -q` → **359 passed** (경고 2건은 asyncio subprocess 소멸자 관련, 무해)
    - 프론트: `npx vitest run` → **7 files / 48 tests passed**, `npx tsc --noEmit` → 0,
      `npm run build` → 성공(8 라우트)
  - **푸시**: `git push origin refactor/speaker-label-mapping-c` 완료. PR #82가 이제 최신 코드 반영.
  - **코드 리뷰 실행**(`/code-review:code-review 82`, CLAUDE.md 필수 절차):
    적격성·CLAUDE.md 수집·PR 요약 3개 + 리뷰 5개(CLAUDE.md 준수 / 얕은 버그 스캔 /
    git 이력 대조 / 이전 PR 코멘트 대조 / 코드 주석 대조) + 신뢰도 채점 4개 = 12 에이전트.
    - **이전 PR #82 리뷰 지적 8건(2026-08-31 15:14Z 6건 + 22:04Z 2건) 전부 해소 확인.**
    - **과거 3대 재발 결함 모두 재발 없음 확인**: ① `finalize_job` identity 재키잉 제거,
      ② transcript 컬럼 실명 굽기 제거(모든 소비 지점이 `display_transcript`/`render` 경유),
      ③ `localSpeakerMap` 초기값 `null` 센티널 + 모든 리셋 지점 `null` 일관.
    - 채점 결과 4건 전부 임계값 80 미만 → **PR 코멘트 미게시**(리뷰 스킬 규칙).
      다만 아래 "남은 지적"에 기록한다.
- **남은 지적 (임계값 미달이나 실재 확인됨 — 머지 전/후 판단 필요)**:
  1. (75) `DEVGUIDE.md:475` §10 항목이 **이미 고친 결함을 미해결 "후속 과제"로 기술**한다.
     `Transcript.tsx`의 `saveEdit`/`saveSpeakerAll`/`reassignLine`(L186·196·208)은 이미
     `render(..., {})`로 라벨만 내보낸다. 커밋 순서상 `8c47a56`(수정)이 `8e16cb0`(문서 기록)보다
     **먼저**였는데 문서를 갱신하지 않았다. 이 프로젝트는 §10 정확성에 의존해 재발을 막으므로
     그대로 두면 "이미 고친 것을 또 고치는" 위험이 있다.
  2. (75) `scripts/migrate_legacy_speaker_map.py:151-156`의 `_representative()`가
     **어디서도 호출되지 않는 죽은 코드**이고, `_merge_duplicate_names`(L202-203)가 동일한
     tie-break를 인라인으로 재구현했다. 지금은 결과가 같아 버그는 없으나, 이 저장소가
     "매칭 규칙 사본이 갈라져 5라운드 연속 같은 버그"를 겪은 바로 그 패턴이다.
     둘 중 하나로 통일(호출하거나 삭제)할 것.
  3. (50) 실명(`아빠`·`손주환`·`손재락`)과 실제 job ID가 **공개 저장소**에 들어간다
     (`gh repo view` 실측 `isPrivate: false`). main에도 이미 존재하던 것이나 이번 PR이
     신규 테스트 파일 전체·DEVGUIDE §10에서 범위를 크게 넓혔다(신규 추가 83행). 전역 보안 규칙
     "개인정보도 동일하게 마스킹"에 걸린다. 픽스처를 `김팀장`류 placeholder로 교체 권고.
  4. (50) 커밋 `cbe8447`이 `wip:` 접두어 사용. squash 머지 예정이라 main 이력엔 안 남는다.
- **다음 할 일**: 위 1·2(각 75점) 반영 여부 결정 → 머지(`gh pr merge --squash --delete-branch`,
  사용자 확인 필요) → 로컬 브랜치 정리 → **다음 PR 1순위: 회의 전환 시 이전 회의 상태 잔존(전 5건,
  rematch가 최악)**. 상세는 `docs/ai_analysis/20260828_잔여_기획_후보.md`의 "★ 다음 PR 확정 안건".
- 막힌 점/주의:
  - **`pytest tests/`는 여전히 운영 DB `backend/meetings.db`를 오염시킨다**(conftest 부재).
    이번 세션 실측: `recording_notes` 510행 → 512행(1회 실행당 +2행 누적). 세션 58 기록의 406행에서
    이미 510행까지 늘어난 상태였다. 이번엔 **실행 전 백업 → 실행 → 백업 복원**으로 처리했고
    최종 md5 `837db16f...`(510행)로 원복 확인. **다음 사람도 pytest 전에 반드시 백업할 것.**
    근본 수정(`conftest.py` 신설 + `DB_PATH` tmp 격리)은 여전히 미착수, PR C 범위 밖.
  - `showResummarizeModal`이 job 전환 시 안 닫히는 결함은 이번에도 미수정(증상만 차단된 상태).
- 관련 파일/커밋: `e16158e`(HEAD), 리뷰 대상 36파일 +5454/−379.
  `DEVGUIDE.md:475`, `scripts/migrate_legacy_speaker_map.py:151-156,202-203`
- 푸시 여부: **origin/refactor/speaker-label-mapping-c 푸시 완료. PR #82 미머지.**

---

## 2026-09-01 07:29 (작업 PC: 로컬) — 세션 59 (PR C 2라운드 진행 중: 프론트 계약 분리 + 화자 이름 소실 회귀 수정)

- 브랜치: `refactor/speaker-label-mapping-c` — **PR #82 OPEN, 아직 미머지**
  (https://github.com/jaerakson/meeting-jr/pull/82). 이번 라운드 커밋은 **origin에 아직 미푸시**
  (로컬이 `origin/refactor/speaker-label-mapping-c` 대비 8커밋 앞섬 — 아래 "완료" 목록).
- **확정 계약(정본)**: `job.transcript` 컬럼은 항상 화자 라벨 그대로(`SPEAKER_00` 등) 저장한다.
  화자 이름은 `job.speakers`(label→name)가 별도로 나른다. 표시(화면·다운로드·복사·공유)는
  **소비 시점**에 `displayName(label, speakers)`(프론트) / 동일 규칙(백엔드)로 렌더한다.
  이름을 본문에 구워 저장하지 않는다.
- 완료 (세션 58의 PR #82 코드리뷰 지적 6건 수정 이후, 2라운드 근원 수정):
  - 프론트: `8c47a56`(`Transcript.tsx` — `onTranscriptChange`를 `{transcript, speakerMap}`로
    분리, 저장용 페이로드는 항상 라벨 그대로 + 비편집 모드도 `speakers` prop으로 이름 렌더 — **근원**),
    `6a4b84d`(`MainArea.tsx`가 새 계약에 맞춰 편집·다운로드 소비하도록 갱신),
    `a4c97fb`(**차단급 회귀 수정** — 아래 "핵심 사고 이력" ②),
    `07bacf4`(시드 `useEffect`의 `eslint-disable` 사유 주석 + 비편집 모드 실명 렌더 회귀 테스트,
    팀 내부 호칭 F2)
  - 백엔드: `124fa94`(B1 — `PATCH /api/jobs/{id}/transcript`가 `speaker_map`을 body로 수용)
  - 테스트: `d56aa95`(T1~T4, `PATCH /transcript` speaker_map 수용 관련),
    `1b43abe`(T5 — `apply-match`/`rename-speakers`가 transcript 컬럼에 실명을 굽던 결함의
    **4번째 재발**을 고정하는 회귀 테스트, qa-c4)
  - 문서: `b4afe09`(프론트 `fetch` 65곳 중 `res.ok` 미검사 36곳을 두 부류로 구분해
    `docs/ai_analysis/20260828_잔여_기획_후보.md`에 후속 과제로 기록 — 이번 PR 범위 밖으로 확정,
    코드 수정 없음)
- 진행 중 (다음 사람이 이어받을 것):
  - qa-c4: 백엔드 T5(완료, `1b43abe`)에 이어 T10(서버측 빈 `speaker_map` 방어 테스트) 작성 중.
    프론트 쪽은 **F3**(`res.ok` 422 응답 시 편집 모드 유지·로컬 상태 미소거 검증, 저장·재요약 양쪽)와
    **중복 표시이름(`대표님`×3) 픽스처로 `reassignLine` payload의 `transcript`가 라벨 그대로인지
    검증**(차단 3의 실제 안전망) — 둘 다 **미작성**, qa-c4 전담으로 확정.
  - back-c4: B2~B7 대기. **B7 = 서버측 빈 `speaker_map` 방어**(아래 ② 회귀의 서버측 쌍둥이 결함에
    대한 방어 — 프론트 수정이 정본, 서버는 방어. 구버전 번들·직접 API 호출 대응상 **둘 다 필요**).
- **다음 PR 1순위(이 PR 머지 직후 착수, 팀리드·director 확정)**: 회의 전환 시 이전 회의 상태
  잔존(전 5건, rematch가 최악 — 화자 이름이 DB에 잘못 기록됨). 상세는
  `docs/ai_analysis/20260828_잔여_기획_후보.md`의 "★ 다음 PR 확정 안건" 항목.
- **핵심 사고 이력 (다음 사람이 반드시 알아야 할 것)**:
  1. `apply-match`·`rename-speakers`가 transcript 컬럼에 이름을 **직접 구웠던 것**이 레거시 행
     생성 결함의 **4번째 재발** 원인이었다. T5(`1b43abe`)로 회귀를 고정했다.
  2. **[차단급, 수정 완료]** `MainArea.tsx`의 `localSpeakerMap` 초기값이 `{}`(비-null)였던 탓에
     `localSpeakerMap ?? job.speakers ?? {}`의 `??`가 **죽은 코드**였다. 재요약 모달은
     `[job?.id]` 이펙트로 닫히지 않는데(별도 결함, 미수정) 그 이펙트가 `localSpeakerMap`은
     리셋한다 — 모달을 연 채 다른 회의로 전환하면 편집 진입(시드)을 거친 적 없는 새 회의의
     `speaker_map: {}`가 그대로 `POST /finalize`로 나가 **회의의 모든 화자 이름이 영구 소실**된다.
     `a4c97fb`에서 `null` 센티널로 수정(null="편집 미진입", `{}`="편집에서 실제로 빈 맵 확정"을
     구분). **`showResummarizeModal`이 job 전환 시 안 닫히는 것 자체는 아직 안 고쳤다** — 이번엔
     증상(speaker_map 소실)만 막았다.
  3. `backend/meetings.db`는 `.gitignore` 대상이라 **`git status`로 오염 여부를 판단할 수 없다**
     (실측: `.gitignore:25`). 테스트가 운영 DB를 건드렸는지 의심되면 행 수를 직접 세야 한다
     (세션 58 참조 — `recording_notes` 404→406행 오염 사례, PR C 범위 밖 후속 과제로 남아있음).
  4. **팀 프로세스 변경**: 구현자가 자기 구현에 맞춰 테스트를 갱신하면 "의도대로 동작하는가"는
     검증돼도 "의도 자체가 틀렸는가"는 못 잡는다 — 위 ②를 팀리드/구현자 모두 처음엔 놓쳤고
     director가 리뷰에서 잡았다. 이후 **프론트 신규 테스트는 qa-c4 전담**으로 역할을
     재분리했다(이미 나온 산출물은 유지, 신규만 분리 — revert 안 함).
- 막힌 점/주의: 현재 없음. 각자(front-c4 구현 대기, qa-c4 T10+F3+픽스처, back-c4 B2~B7) 진행 중.
- 관련 파일: `frontend/components/{Transcript,MainArea}.tsx`,
  `frontend/__tests__/{Transcript.labelModel,MainArea.resummarize}.test.tsx`,
  `backend/app/main.py`, `docs/ai_analysis/20260828_잔여_기획_후보.md`
- 검증: 프론트 `npx vitest run`(6 files, 40 tests) / `npx tsc --noEmit` / `npm run build` 전부
  통과(front-c4 확인, 세션 59 시점). 백엔드 테스트 결과는 qa-c4가 진행 중이라 이 항목에서
  확정치로 적지 않는다 — **다음 사람은 이어받을 때 반드시 재확인할 것.**
- 푸시 여부: **미푸시.** 로컬 8커밋(`8c47a56`~`1b43abe`)이 origin에 안 올라가 있다. PR #82는
  이전 라운드(세션 58) 기준으로 이미 OPEN 상태이며, 이번 라운드 커밋은 아직 반영 안 됨 —
  director가 PR 프리즈 직전에 최종 상태로 갱신 후 푸시할 예정.

---

## 2026-08-31 (작업 PC: 로컬) — 세션 58 (PR C 진행 중: 마이그레이션 + 확정 결함 2건)

> ### ★ 다음 작업 최우선 — **테스트가 운영 DB 를 오염시킨다 (개발 인프라 결함)**
> 제품 한계가 아니라 **개발 인프라 결함**이다. PR C 범위 밖이라 이번에 고치지 않았다.
> - **증상**: `cd backend && pytest tests/` 실행 후 `backend/meetings.db` 의 md5 가 바뀐다.
>   실측: `recording_notes` 404행 → **406행** (테스트가 운영 DB 에 실제로 INSERT).
>   삽입 예: `{'content': '중요 포인트', 'timestamp': 10.5}`. **실행할 때마다 누적된다.**
> - **원인 (확정)**: `backend/app/database.py:13` `DB_PATH` 가 **고정 경로**이고,
>   `backend/tests/conftest.py` 가 **아예 없다** — DB 를 격리하는 픽스처가 없다.
>   `test_recording_notes.py` 가 그대로 운영 DB 에 쓴다.
> - **현재 피해 범위**: `recording_notes` 만 오염(실제 화면에 나오는 데이터).
>   `meetings` 테이블(회의 데이터)은 **무사**하다.
> - **위험**: `meetings` 를 쓰는 테스트가 하나라도 추가되는 순간 **사용자 회의 데이터가 오염된다.**
>   지금 무사한 건 운이 좋았을 뿐이다. 이번 세션에만 pytest 를 수십 번 돌렸다.
> - **조치 방향**: `conftest.py` 신설 + `DB_PATH` 를 테스트에서 tmp 로 격리
>   (일부 테스트는 이미 `monkeypatch.setattr(db_module, "DB_PATH", ...)` 로 개별 격리하고 있다 —
>   이 패턴을 autouse 픽스처로 올리면 된다).
> - **마이그레이션 `--write` 실행 시 주의**: pytest 를 돌린 직후의 DB 상태와 사용자가 보는
>   DB 상태가 다를 수 있다. **`--write` 전에 반드시 `backend/meetings.db` 백업.**

- 브랜치: `refactor/speaker-label-mapping-c` (PR C, 진행 중)
- 완료: `scripts/migrate_legacy_speaker_map.py` (기본 dry-run, `--write` 로만 기록, 자동 실행 없음,
  커넥션을 `mode=ro` 로 열어 읽기 전용을 코드로 강제). 실 DB dry-run 실측:
  **자동복구 3 / 병합복구 2 / 건너뜀 1(`60b7b738`, 사전조건③) / 조치불필요 4.**
  director 독립 계산과 행 구성까지 일치. 실행 전후 md5 동일 확인.
- **[확정 결함 — PR C 에서 수정 중] `patch_transcript` 가 새 레거시 행을 만든다**
  `app/main.py:656` 이 `parse_transcript()` 로 **이미 이름이 렌더된 본문**을 다시 파싱해
  실명을 라벨로 삼는다. MainArea 의 "회의록 수정" 경로. `TranscriptEditor` 는 PR C 가 막았지만
  **이 경로는 감사에서 빠졌다.** §10 의 "생성자를 막았으므로 모집단이 고정된다"는 **거짓이었다.**
  깨진 행에 apply-match 를 걸면 422 가 아니라 **200 으로 조용히 성공**하며 고아 키를 남긴다.
  마이그레이션으로 복구해도 이 경로로 다시 깨지므로(밑 빠진 독) 문서 정정이 아니라 수정을 택했다.
  수정 계약: (a)이미 키/diar 라벨 → 그대로 / (b)`start` 가 같은 **편집 이전** 세그먼트의 표시 이름과
  일치 → **그 old label** / (c)값이 유일한 역맵 / (d)미해소 시 **422·부분 저장 금지**.
  **(b)가 핵심** — 표시 이름 중복 회의(`5938f69c` 의 `대표님` 3벌)도 편집이 막히지 않는다.
  (b)는 *누가 말했는지* 추론이 아니라 **이미 그 줄에 붙어 있던 라벨을 되찾는 것**이다.
- **[교훈] 건수 대조만으로는 못 잡는다**: backend-c3 의 첫 판정 기준("모든 라벨이 speaker_map 키에
  있으면 정상")은 `60b7b738` 을 **정상으로 위장**시켰는데 **건수는 3/2/1/4 로 정확히 맞았다.**
  숫자만 대조했으면 깨진 행을 정상으로 보고하고 통과했을 것이다. **행 구성까지 대조할 것.**
  → 팀원에게 예상 숫자를 **목표가 아니라 반증 대상**으로 주는 방식이 유효했다.
- **[교훈] 폐기 방식 재유입 압력은 실재한다**: qa 가 착수 질문에서 "삭제된 overlap 휴리스틱을
  마이그레이션 1회성으로 재사용하는 것인지" 를 물었다. 아니라고 못박고, **역맵으로 해소 안 되는
  라벨이 있으면 diar 가 아무리 풍부해도 복구하지 않고 건너뛴다**는 단언을 테스트에 넣게 했다.
- 관련 파일: `scripts/migrate_legacy_speaker_map.py`, `backend/app/main.py`(patch_transcript),
  `backend/tests/test_patch_after_rename_legacy_row.py`, `DEVGUIDE.md` §10(1행 정정 + 4행 추가)
- 푸시 여부: **PR #82 생성 완료**(https://github.com/jaerakson/meeting-jr/pull/82). 코드리뷰 완료 → **지적 6건 수정 중**(머지 전)
- **[코드리뷰 지적, 수정 중]** ①**[머지 차단]** `handleResummarize`→`finalize_job` 이 레거시 행을 계속 생성 (`patch_transcript` 와 **같은 결함의 다른 호출부**. summarizer 사본 → patch_transcript → 이번 건으로 **세 번째 반복**) ②(b)의 같은 `start` 충돌 시 first-wins = 추측 ③(b)가 `old_label` 을 라벨 공간에 재검증 안 함 ④공유 페이지가 raw 라벨 표시 ⑤마이그레이션 stale-read ⑥문서 4곳
- **[후속 과제, 프론트]** `Transcript.tsx` 의 `onTranscriptChange` 가 **전송용 페이로드와 화면용 렌더를 분리하지 않는다**
  (항상 `render(segments, speakerMap)` = 이름 적용판을 내보냄). 편집 중 이름을 한 번이라도 바꾸면
  이후 텍스트만 고쳐도 이름이 구워진다. `handleSaveTranscript`·`handleResummarize` **두 결함의 공통 근원**.
  현재는 서버가 `restore_segment_labels` 로 사후 방어. **서버 방어는 프론트를 고쳐도 계속 필요**하다
  (구버전 번들·직접 API 호출 무방비). 프론트 수정은 대체가 아니라 **추가 방어**다.
  PR #82 범위에서 제외한 이유: 재리뷰 단계 + qa 가 서버측 계약으로 테스트 작성 중이라 지금 바꾸면 무효화된다
- **[교훈] 지목된 한 곳만 고치지 말 것.** `patch_transcript` 를 닫을 때 *"이름이 렌더된 transcript 를 서버로 보내는 호출부"* 를 **전수로 세지 않아** 머지 차단 결함이 남았다. grep 은 증상이 아니라 **패턴**으로 걸어야 한다

---

## 2026-08-31 (작업 PC: 로컬) — 세션 57 (PR #81: 화자 매핑 리팩터링 PR B — 라벨 기반 전환)
- 브랜치: main (PR #81 squash 머지, `b1a1ee6`)
- 완료 (PR B = 3단계 중 2단계, **삭제가 본체**):
  - apply_match = **라벨 검증 → speaker_map 갱신 → `render()` 재렌더**. participation = `speaker_map.get(label, label)`.
    rename-speakers 에 재렌더 추가(speakers 만 갱신하던 구조적 desync 해소)
  - 삭제: apply_match 3a~3e, `replace_map`, `collision_groups`, `applied_labels`,
    `_resolve_speaker_display`, `seen_display_names`, overlap 휴리스틱 → **`backend/app` 전수 0건**
  - `_is_identity_mapped` 는 **경로 선택용으로 존치**(삭제하면 레거시 행에서 이름이 사라진다 — 아래 참조)
  - 기존 회귀 테스트 1,094줄 → 라벨 모델로 재작성. **시나리오 26개 전수 보존**(대응표: `docs/ai_analysis/20260831_PR_B_시나리오_대응표.md`)
- 테스트: **297 passed** (착수 시 19 failed → 0). `main.py` 약 316줄 축소
- 코드리뷰: 전체 프로토콜(리뷰어 5 + 채점 4). **지적 4건 확정 + 리뷰가 놓친 결함 1건 추가 발견**
  1. [재현] `rename-speakers` 부분 map → 본문에서 화자 이름 소실. `apply_match` 와 같은 merge-safe 패턴으로 통일
  2. [재현] 이름 맞바꾸기 후 요약 재생성 시 **두 화자가 한 명으로 붕괴**(순차 `.replace()`)
  3. `save_speaker_profile` 이 폐기 휴리스틱의 마지막 사본인데 **어느 PR 범위에도 없었음** → PR C 배정
  4. 문서-구현 모순 3곳(DEVGUIDE `raw` 공식, `rename_speakers` docstring, 테스트 module docstring)
  5. **[qa 발견] `summarizer._replace_speakers`** — main.py 수정을 그대로 상쇄하던 중복 치환.
     `render()` 로 올바르게 만든 스크립트 위에 한 번 더 순차 치환이 걸렸다. **줄 앵커조차 없어 본문까지 오염**
- **폐기 방식 사본 회계 (기준을 혼동하지 말 것)**
  - 순차 `.replace()` 알고리즘: `finalize_job` / `regenerate_summary` / `summarizer._replace_speakers` = **3벌, 전부 제거**
  - overlap 휴리스틱(설계문서가 근본 원인으로 지목): 4벌 중 3벌 제거, **`save_speaker_profile` 1벌이 PR C 배정**
- **확정된 판단 기준**: **PR B 가 도달성을 만든 경로면 PR B 범위, 아니면 후속 배정.**
  (summarizer 는 이 PR 이 이름 맞바꾸기를 정식 지원하며 도달 가능하게 만들었으므로 이번에 처리)
- 막힌 점/주의:
  - **[머지 후 남은 불일치, 사용자 승인함]** 같은 레거시 행(speaker_map 키가 실명)에 대해
    `apply_match` 는 `422 + skipped` 로 거부하는데 `save_speaker_profile` 은 조용히 옛 휴리스틱을 돌려 **성공한다.**
    사용자 눈에는 한 화면에서 거부된 데이터가 다른 화면에서 처리되는 것처럼 보인다. **PR C 에서 닫는다.**
  - **[승인된 기능 손실]** 레거시 회의(10건 중 1건)에서 음성프로필 재매칭 무동작 → 명시적 422.
    PR C 가 근본 원인(finalize identity 재키잉)을 제거하므로 **모집단이 고정된다**
  - **[의도된 부작용]** 레거시 행 participation 이 transcript 경로를 타 `total_seconds`·`percentage` 변경.
    전/후 실측값은 대응표에 표로 고정(구현 후엔 측정 불가라 워크트리로 미리 쟀다)
  - **검증 기법 — PR C 에 반드시 적용**: qa 가 **Claude CLI 만 mock 으로 막고 최종 prompt 를 캡처**해
    summarizer 결함을 잡았다. **중간 산출물(스크립트 파일)은 올바른데 최종 입력이 깨지는 형태**라
    중간만 검증했으면 그대로 머지됐다. 요약·프론트로 나가는 **최종 산출물**을 캡처해 검증할 것
  - **grep 은 `backend/app` 전수로 걸 것.** 팀리드가 `main.py` 만 보고 "코드베이스 0건"이라 보고했고
    director 가 그걸 PR body 에 옮겨 적었다. 이 오류 때문에 다섯 번째 사본을 놓칠 뻔했다(§10 에 기록됨)
  - **역할 분리가 작동했다**: 구현자(backend)가 테스트 단언을 한 줄도 고치지 않았고,
    "미결"로 올린 건(빈 `new_name`)이 실제로는 이름 삭제 결함이었다
- 다음 할 일 — **PR C (마지막 단계)**
  - `finalize_job` 의 **identity 재키잉 삭제** — 라벨 정체성을 파괴하는 근본 원인. 이걸 제거해야 레거시 행이 더 생기지 않는다
  - 프론트 파서 4개 + 시리얼라이저 2개를 **공유 모듈 1개로 통합** → `TranscriptEditor.tsx:25` 의 `\S+` 공백 이름 버그 동시 해소
  - `save_speaker_profile` 을 라벨 모델로 전환(위 불일치 해소)
  - TranscriptEditor 가 segments 로 왕복. body 에 segments 없으면 문자열 경로 폴백(구버전 번들 방어)
  - **frontend-dev 소환 필요** (PR A·B 는 백엔드만이라 부르지 않았다)
- 관련 파일: backend/app/{main,transcript,database,summarizer}.py,
  backend/tests/test_{apply_match,participation}_label_model.py, test_rename_speakers_api.py,
  test_regenerate_speaker_swap.py, DEVGUIDE.md §10,
  docs/ai_analysis/20260831_PR_B_시나리오_대응표.md, 20260831_화자매핑_라벨_리팩터링_설계.md
- 푸시 여부: origin/main 푸시 완료 (PR #81 squash 머지 + 브랜치 삭제)

---

## 2026-08-31 (작업 PC: 로컬) — 세션 56 (PR #80: 화자 매핑 리팩터링 PR A — transcript_segments 도입)
- 브랜치: main (PR #80 squash 머지, `8745cad`)
- 배경: CLAUDE.md 1순위 과제. 이 영역에서 **5라운드 연속 같은 부류 버그**가 나와 패치를 멈추고 설계 안건으로 전환했다.
  설계 전문: `docs/ai_analysis/20260831_화자매핑_라벨_리팩터링_설계.md` (근본 원인·PR 3분할·회귀 위험)
- 완료 (PR A = 3단계 중 1단계, **순수 additive·동작 변화 0**):
  - `transcript_segments TEXT`(JSON `[{start,end,label,text,raw?}]`) 컬럼 + 신규 `backend/app/transcript.py`
    (`parse` / `render` / `get_segments` — lazy 파싱 + 조회 시 백필)
  - 생산자 2곳이 segments 기록: `merge_and_save`(3-tuple 확장) / `_parse_txt_transcript`(시그니처 고정, 호출부 parse)
  - **강제 불변식**: transcript 문자열은 in-place 변경 금지, `render(segments, speaker_map)` 출력으로만 쓴다
  - `_row_to_dict` 에 역직렬화 추가 → `get_job()["transcript_segments"]` 가 다른 JSON 컬럼과 같은 타입 관행을 따른다
  - **결함 3건이 이 파서에서 닫혔다**: 100분 초과 회의(`\d{2}`→`\d+`) / 공백 포함 실명("김 팀장", `\S+` 금지) /
    라벨 앞뒤 공백 오염(왕복은 성립하는데 치환만 조용히 실패)
- 테스트: **282 passed**. 신규 3파일 제외 시 **기존 215 무수정 통과**(베이스라인 일치).
  팀리드 독립 검증 — 실제 DB 회의 10건/1,307줄 왕복 불일치 0건, 백필 후 바이트 동일
- 코드리뷰: 전체 프로토콜(리뷰어 5 + 채점 6) 실행. 지적 6건 중 80점 통과 1건 + 사실 확정 1건 수정
  - [80점] `_row_to_dict` 미역직렬화 — PR B/C 에서 터질 타입 불일치 (PR #53 과 같은 부류)
  - [75점] DEVGUIDE §10 한계 기록이 같은 PR 의 테스트와 모순 → 아직 사실인 것만 남김
  - 제외 4건(브랜치·커밋 접두어, `prev_end` falsy, payload)은 기존 패턴이거나 실질 도달 불가
- 막힌 점/주의:
  - **테스트가 초록인 상태에서 결함 4건이 나왔다.** 왕복 단언만으로는 구조적으로 안 잡히는 부류가 있다
    (라벨 공백 결함: 왕복 성립 + 치환 실패 → 258개 전부 통과). → **PR B 부터 왕복과 치환을 항상 짝으로 단언한다.**
  - 신규 필드에는 "동작 변화 0"이 아니라 **"기존 관행과의 일관성"이 기준**이다(`_row_to_dict` 반려가 이 혼동에서 나왔다)
  - `job_queue.job_queue` 가 프로세스 전역 싱글턴이라 테스트가 서로 오염됐다(단독 통과·전체 간헐 실패).
    테스트 안에서만 격리 큐로 해결. 프로덕션 코드 미변경
- 다음 할 일 — **PR B (apply_match·participation 라벨 전환, 삭제가 본체)**
  - 삭제: apply_match 3a~3e(main.py 약 130줄), `replace_map`, `collision_groups`, `applied_labels`,
    overlap 매칭, `_resolve_speaker_display`, `_is_identity_mapped`, `seen_display_names`,
    `save_speaker_profile` 폴백. participation 은 `speaker_map.get(label, label)` 로 축소
  - **합격 기준 4가지**: ① 기존 1,094줄의 시나리오 개수 보존(대응표 제출) ② 삭제 대상 함수 0회 참조(grep 증명)
    ③ 왕복과 치환을 짝으로 단언 ④ **PR A 의 282개 무수정 통과**
    (PR A 와 달리 "기존 테스트 무수정"이 합격 기준이 될 수 없다 — 삭제가 본체라 옛 동작 단언은 실패해야 정상)
  - **역할 분리**: 1,094줄 단언 재작성은 qa 담당. backend 는 읽기만 하고 "단언이 틀렸다"고 보면 director 에게 보고.
    구현자가 자기 테스트를 고치는 형태를 금지한다(5라운드 반복 영역이라 이 안전망이 핵심)
  - **착수 전 확인된 함정 2건**:
    ① `SpeakerMapper.tsx:42` 초기값이 `''` 라 빈 이름이 그대로 전송된다. 지금은 `rename_speakers` 가 transcript 를
       안 건드려 무해하지만, PR B 가 재렌더를 붙이면 **화자 이름을 지운다.**
       → 렌더 측 `(speaker_map.get(label) or "").strip() or label` 로 기존 `display == label` 규칙에 흡수(별도 분기 금지)
    ② `rename-speakers` 는 `_save_speakers` 에서만 빈 값을 거르고 `update_job_result(speakers=...)` 에는 body 를
       그대로 저장한다(비대칭). 쓰기 정규화만으로는 이미 저장된 행을 못 막아 **2겹 방어**가 필요하다.
       현 DB 10건에 빈 값 보유 행은 0건이지만 쓰기 경로가 허용하므로 언제든 생길 수 있다
  - `rename-speakers`(main.py:2084)는 **백엔드 테스트 0건**이다. PR B 가 재렌더를 붙이므로 신규 테스트가 필요하다
    (`SpeakerMapper.tsx:50` 이 실제 호출 — 프론트가 보내는 payload 형태로)
- 관련 파일: backend/app/transcript.py, backend/app/{database,job_queue,main,audio_processor}.py,
  backend/tests/test_transcript_{module,backfill,producers}.py, DEVGUIDE.md §10,
  docs/ai_analysis/20260831_화자매핑_라벨_리팩터링_설계.md, 20260831_PR_A_생산자_정찰.md
- 푸시 여부: origin/main 푸시 완료 (PR #80 squash 머지 + 브랜치 삭제)

---

## 2026-08-29 (작업 PC: 로컬) — 세션 55 (PR #79: apply-match 이름 충돌 외 4건)
- 브랜치: main (PR #79 b132d14)
- 배경: PR #78 머지 후 정식 코드리뷰를 한 번 더 돌려 새 버그 4건 발견 → 이번 PR로 수정
- 완료:
  - **버그 1 [HIGH] replace_map 키 충돌** — `replace_map[current_name]` 이 현재 transcript 토큰으로 키를 잡아,
    서로 다른 라벨이 같은 이름으로 해석되면 뒤엣것이 앞엣것을 덮어씀. speakers 에는 두 이름이 남는데
    transcript 에는 하나만 남아 PR #78 이 고치려던 불일치가 재발.
    → **충돌 시 라인 단위 치환**으로 격상. 각 라인의 `[MM:SS]` 를 diar 세그먼트와 overlap 면적으로 대조해 배정.
      충돌 없는 경우는 기존 원자적 정규식 경로 유지(외과적 범위 축소)
  - **버그 2 [MED] participation 중복 display_name** — 매핑 안 된 모든 라벨을 해석해 과분할 시 같은 이름 중복.
    → `seen_display_names` 로 이미 차지한 이름이면 raw 라벨 폴백
  - **버그 3 [MED] 해석 실패를 삼키고 200 반환** — diarization 없는 txt 업로드 회의에서 아무것도 안 바뀌는데
    프론트는 성공으로 알고 모달을 닫음. → 응답 스펙 도입(200 / 200+skipped+warning / 422) + 프론트 안내
  - **버그 4 [LOW] 공백 불일치** — 프론트가 transcript 엔 trim 한 이름을, speaker_map 엔 trim 안 한 값을 저장
    → 백엔드 `.strip()` + 프론트 `.trim()` 이중 방어
  - **코드리뷰 확정 4건 추가 수정** (리뷰 5개 중 4개가 각각 발견, 전부 재현 확인):
    1) [HIGH] `diar_data` 를 identity 라벨이 있을 때만 조회 → 이미 매핑된 라벨끼리 충돌 시 diarization 이
       DB 에 있어도 "없음" 경로로 퇴화. rematch 재호출이라는 정상 시나리오에서 발생. → 게이팅 분리
    2) [MED] 라인별 치환이 포인트 매칭(`seg_s <= ts < seg_e`) → **PR #78 리뷰에서 지적된 회귀의 재발**.
       서브초 드리프트에서 오배정. → `min(seg_e, line_end) - max(seg_s, line_start)` overlap 면적으로 통일
    3) [HIGH] 세그먼트 커버리지 없는 라벨도 speakers 에 성공으로 확정 → 이 PR 자신의 테스트 불변식을 깨는 경로.
       → `applied_labels` 로 실제 치환된 라벨만 확정, 나머지는 skipped
    4) [MED] **버그 4 수정이 만든 새 변종** — `(names[s] || s).trim()` 이 serialize 의 `names[..]?.trim() || ..` 과
       순서가 달라, 공백만 입력 시 transcript 는 raw 라벨인데 speaker_map 은 빈 문자열. → 순서 일치
  - 신규 테스트: `test_apply_match_collision.py`(16), `test_participation_collision.py`(3),
    `TranscriptEditorTrim.test.tsx`(2). 전체 백엔드 215 / 프론트 13 통과
  - DEVGUIDE 섹션 10: 충돌 정의·overlap 공식·speakers 확정 규칙·diar 한계·trim 이중 방어·participation 중복 방지 기록
- 현재 상태: 안정 — 백엔드 215, 프론트 13, tsc 통과 (팀리드 직접 실행 검증)
- 막힌 점/주의:
  - **이 영역에서 다섯 라운드 연속 같은 부류 버그가 나왔다.** PR #78(3건) → PR #78 재리뷰(4건) → PR #79(4건).
    근본 원인은 화자 이름을 **문자열 토큰**으로 다루는 구조다. 같은 토큰을 쓰는 서로 다른 라벨을 구분할 수 없고,
    타임스탬프 판별 로직을 매번 새로 짜다 보니 PR #66 이 폐기한 포인트 매칭이 두 번 재도입됐다.
    → **후속 과제로 기록: 화자 매핑을 라벨 기준으로 다루는 리팩터링.** 패치 반복으로는 안 끝난다.
  - 코드리뷰 비용이 과다했다(라운드당 에이전트 13개). 사용자가 지적했고 타당하다.
    → **앞으로 작은 수정·재리뷰는 팀리드가 직접 diff·테스트로 검증하고, 전체 프로토콜은 큰 기능 PR 에만 적용한다.**
  - 리뷰 중 커밋이 움직여 리뷰를 다시 돌린 사고가 있었다(PR #78). → "PR 생성 보고 = 코드 프리즈" 규칙 정착.
- 다음 할 일:
  - 후속 과제 3건은 `docs/ai_analysis/20260828_잔여_기획_후보.md` 참조
    (화자 매핑 리팩터링 / `_resolve_speaker_display` 정규식 오탐 / `new_name` 미trim·3c-3d 오염 가능성)
  - 잔여 기획 후보 5건도 같은 문서 참조 (용어집 STT 후보정 → 액션아이템 마감일 순 권장)
- 관련 파일: backend/app/main.py(apply_match 3a~3d, get_participation),
  backend/tests/test_apply_match_collision.py, test_participation_collision.py,
  frontend/components/{MainArea,TranscriptEditor}.tsx, frontend/__tests__/TranscriptEditorTrim.test.tsx, DEVGUIDE.md
- 푸시 여부: origin/main 푸시 완료 (PR #79 b132d14, squash 머지 + 브랜치 삭제)

---

## 2026-08-28 (작업 PC: 로컬) — 세션 54 (PR #78: 버그 2건 수정 — apply-match 정합성 + 테스트 stale)
- 브랜치: main (PR #78 7267aae)
- 완료:
  - **버그 1 - apply-match 화자 매핑 정합성:**
    - 원인: apply_match가 `transcript.replace(f"{old_name}:", ...)` 에서 old_name을 항상 raw SPEAKER_XX로 사용.
      finalize 이후 transcript에는 이미 실명이 적용돼 있어 replace가 no-op → speakers만 갱신되어 불일치
    - 수정: `label_to_current` 로 현재 display name 조회 후 치환. identity-mapped는 diarization 역매핑으로 해석
    - participation 폴백: identity-mapped 회의로 판별될 때만 역매핑 시도 (미매핑 화자가 엉뚱한 이름 가져오던 문제)
  - **버그 2 - TranscriptEditor 테스트 stale:**
    - PR #67(8b62f3c)이 "suggestedSpeakers 자동 채우기 제거, 적용/되돌리기 버튼 추가"로 UX를 의도적으로 변경했는데
      테스트(최종 수정 PR #62 d065e3e)가 따라오지 않아 main에서도 실패하던 사전 결함
    - **구현은 그대로 두고 테스트만 현재 동작에 맞게 갱신** (제안 칩 + 수동 적용/되돌리기 검증)
  - 코드리뷰 확정 3건 + 권고 2건 수정:
    1) [100] **이름 맞바꾸기 시 transcript 붕괴** — 순차 `replace()` 가 문자열을 누적 오염.
       두 화자 이름 교환 시 1회차 치환 결과가 2회차에 재차 걸려 모든 발언이 한 이름으로 합쳐짐.
       → 단일 정규식 콜백으로 **원자적 치환** 전환
    2) [100] **부분 매칭 후 미매칭 화자가 원시 라벨로 퇴행** — apply_match가 매칭된 화자만 SPEAKER_XX로 정규화해
       speakers가 혼합 상태가 되는데, `_is_identity_mapped` 가 `not any(k.startswith("SPEAKER_"))` 라 이를 오판.
       → `any(not re.match(r'^SPEAKER_\d+$', k))` 로 되돌려 혼합 상태도 identity-mapped로 처리.
       **이 브랜치 내부 회귀였음**: 933efe8은 정상 → 446d5ae가 논리 반전 → 리뷰에서 발견
    3) [85] **PR #66이 폐기한 알고리즘 재도입** — `_resolve_speaker_display` 가 가장 이른 세그먼트 하나만 anchor로
       삼는 point-matching. PR #66(bd33196)은 "±2초 포인트 매칭은 발화 1건이거나 diarization 시작이 3초 이상 뒤면
       실패"를 이유로 구간 overlap 면적 방식으로 옮겼던 이력. → overlap 면적 방식으로 재작성
    권고: 역매핑 실패 시 해당 라벨 건너뛰기(원래 버그 재발+고아 키 방지), DEVGUIDE 문구를 코드와 일치하도록 정정
  - 재현 케이스 3건을 테스트로 고정 (test_rematch_name_swap_atomic, test_partial_match_unmapped_speaker_keeps_display_name,
    test_early_short_segment_does_not_mislead)
- 현재 상태: 안정 — 백엔드 198개, 프론트 11개, tsc --noEmit 전부 통과 (팀리드 직접 실행 검증)
- 막힌 점/주의:
  - **코드리뷰가 잡은 3건 모두 신규 테스트 6개가 통과한 상태에서 남아 있었다.** 테스트를 늘리는 것만으로는
    부족하고, 리뷰에서 나온 재현 시나리오를 테스트로 고정하는 절차가 실제로 효과가 있었다.
  - **문서-구현 불일치가 PR #75·#76·#77·#78 네 번 연속 지적됐다.** DEVGUIDE 기록 시 코드와 대조 필수.
  - 진행 중 사용자가 창을 닫아 팀 6개가 동작 불능이 된 사고가 있었다. 작업물이 미커밋 상태였고 팀리드가
    WIP 커밋(e32979b)으로 보호 후 새 팀(director-4, backend-dev-2)을 구성해 재개했다.
    → **작업 단위마다 즉시 커밋**, **PR 보고 시점 = 코드 프리즈** 규칙을 팀 운영에 추가
- 다음 할 일:
  - 잔여 기획 후보 5건은 `docs/ai_analysis/20260828_잔여_기획_후보.md` 참조
    (용어집 STT 후보정 → 액션아이템 마감일 순 권장)
- 관련 파일: backend/app/main.py(apply_match, _resolve_speaker_display, get_participation),
  backend/tests/test_apply_match_consistency.py(신규 9개), frontend/__tests__/TranscriptEditor.test.tsx, DEVGUIDE.md 섹션 10
- 푸시 여부: origin/main 푸시 완료 (PR #78 7267aae, squash 머지 + 브랜치 삭제)

---

## 2026-08-28 (작업 PC: 로컬) — 세션 53 (PR #77: 화자 이름 클릭 점프)
- 브랜치: main (PR #77 82716ae)
- 완료:
  - **PR #77 - 화자 이름 클릭 → 해당 화자 발언으로 이동:**
    - 사용자 요청: "이름부분을 클릭하면 해당 부분의 처음으로 가는 기능"
    - 백엔드 변경 없음 — 순수 프론트 UX. 기존 handleTimeClick → audioPlayerRef.seekTo 경로 재사용
    - Transcript.tsx: 비편집 모드 화자명 클릭 → 첫 발언 시킹+스크롤. 같은 화자 반복 클릭 시
      currentTime 이후 다음 발언으로 순환(마지막 이후 → 첫 발언). 편집 모드는 기존 이름변경 UI 유지
    - ParticipationChart.tsx: `onSpeakerClick?` optional prop, 범례 클릭 가능
    - MainArea.tsx: handleSpeakerClick 2-pass 매칭 — (1) transcript 직접 일치 (2) speakers 역방향 조회(displayName→label)
    - 테스트 9개 (SpeakerNameJump.test.tsx): SPEAKER_XX/실명/txt업로드/identity mapping/편집모드/순환/회의전환
    - 코드리뷰 이슈 2건(확정) + 1건(권고) 수정:
      1) [100] 두 진입점 동작 불일치 — Transcript는 순환하는데 ParticipationChart 범례는 항상 첫 발언.
         그런데 DEVGUIDE에 두 컴포넌트 공통으로 "순환"이라 기재. 리뷰 에이전트 4명 전원 독립 확인.
         → 차트 범례는 "첫 발언 고정"으로 확정하고 DEVGUIDE 문구를 경로별로 구분해 정정 + 반복클릭 테스트 추가
      2) [100] lastClickedSpeaker가 회의 전환 시 미리셋 — 기존 리셋 useEffect는 `if (editable)` 가드가 있어
         비편집 모드에서 미실행, <Transcript>에 key도 없어 재마운트 안 됨. 같은 라벨 가진 다른 회의로 전환 후
         첫 클릭이 "반복 클릭"으로 오인되어 두 번째 발언으로 이동. → transcript 변경 시 리셋 useEffect 추가
      3) [75, 권고] apply-match(PR #67) 이후 identity-mapped 회의에서 speakers/transcript 불일치로 매칭 실패
         → 이번엔 console.warn 폴백만. **근본 원인은 미해결 — 아래 참고**
- 현재 상태: 안정 — 프론트 SpeakerNameJump 9/9, tsc --noEmit, 백엔드 189/189 통과 (팀리드 직접 실행 검증)
- 막힌 점/주의:
  - **[미해결] apply-match 데이터 불일치**: PR #67의 apply-match(backend/app/main.py:1796-1801)는
    `transcript.replace(f"{old_name}:", f"{new_name}:")` 후 `speakers.update(matches)` 를 하는데
    matches는 항상 raw SPEAKER_XX 키다. identity-mapped 회의(transcript가 이미 `아빠:`)에서는 replace가
    no-op인데 speakers에는 `SPEAKER_00 → 새이름`이 새로 들어가 job.speakers와 job.transcript가 어긋난다.
    → participation API의 display_name(새이름)과 transcript의 화자 토큰(아빠)이 불일치 → 화자 클릭 무반응.
    별도 이슈로 수정 필요.
  - **[미해결] 기존 프론트 테스트 실패 1건**: `__tests__/TranscriptEditor.test.tsx` 의 suggestedSpeakers
    fallback 테스트가 main에서도 실패한다(팀리드가 main 체크아웃 후 재현 확인). PR #77과 무관한 사전 결함.
- 다음 할 일:
  - 위 미해결 2건 (apply-match 데이터 불일치 / TranscriptEditor 테스트 실패)
  - 잔여 기획 후보 5건은 `docs/ai_analysis/20260828_잔여_기획_후보.md` 참조 (용어집 STT 후보정 → 액션아이템 마감일 순 권장)
- 관련 파일: frontend/components/{Transcript,ParticipationChart,MainArea}.tsx,
  frontend/__tests__/SpeakerNameJump.test.tsx, DEVGUIDE.md 섹션 10
- 푸시 여부: origin/main 푸시 완료 (PR #77 82716ae, squash 머지 + 브랜치 삭제)

---

## 2026-08-28 (작업 PC: 로컬) — 세션 52 (PR #75~#76: 발언 참여도 + 회의 시리즈)
- 브랜치: main (PR #75 3774226, PR #76 3a7a178)
- 완료:
  - **PR #75 - 발언 참여도 분석:**
    - GET /api/jobs/{id}/participation — 화자별 발언시간·비중·턴수·평균 발언길이
    - 데이터 소스 우선순위: diarization DB → 파일 폴백(+lazy migration) → transcript 타임스탬프 근사
    - ParticipationChart.tsx (recharts 수평 BarChart, 다크모드), MainArea 우측 패널 max-h-[35%] 가드 안에 배치
    - 코드리뷰 이슈 4건 수정:
      1) transcript 폴백 정규식이 SPEAKER_XX만 인식 → 이름 라벨 txt 업로드에서 빈 결과 (신뢰도 100)
      2) diarization 파일 폴백(lazy migration) 누락 → PR #63 이전 회의가 부정확한 근사치 사용 (80)
      3) 차트가 PR #64 높이 가드 밖에 삽입 → 높이 붕괴 재발 경로 (75, 권고로 수정)
      4) 재리뷰에서 발견: 정규식이 콜론 뒤 공백 미요구 → `[00:12] 다음 회의는 15:00입니다`를 화자로 오인 → `(.+?):\s` 로 수정
    - 테스트 18개 추가 (총 166개)
  - **PR #76 - 회의 시리즈 & 후속조치 자동 대조:**
    - meeting_series 테이블 + meetings.series_id/followup_items 컬럼 (PR #63의 _migrate idempotent 패턴)
    - 시리즈 API 6개 + 후속조치 API 3개
    - 후속조치: 같은 시리즈 직전 회의의 미완료 액션아이템을 claude -p로 현재 회의와 대조
      → ai_status(AI 추정) / user_status·confirmed(사용자 확정) 이원화. AI 추정만으로 완료 처리하지 않음
    - SeriesSelect.tsx, FollowupPanel.tsx 신규 (다크모드, PR #64 높이 가드 준수)
    - DEVGUIDE.md 섹션 6(API)·섹션 10(확정 결정사항) 갱신 — PR #71~#75 누락분 일괄 반영
    - 코드리뷰 이슈 4건(확정) + 3건(권고) 수정:
      1) [100] 후속조치에 사용자 진입점 없음 — 자동 대조는 run_summary에서 series_id를 보는데
         SeriesSelect는 status==='done' 이후에만 렌더링 → 그 시점 series_id는 항상 NULL.
         수동 "재분석" 버튼도 items 비면 패널째 숨겨져 최초 생성 불가.
         → run_summary 자동 대조 제거, assign_series에서 트리거, items 빈 경우 "후속조치 분석" CTA 노출
      2) [100] PATCH /followup 계약 불일치 — 백엔드는 {index,...} 델타 기대, 프론트는 index 없는 전체 배열 전송
         → 사용자 확정이 화면에만 반영되고 저장 안 됨. 프론트를 델타 전송으로 수정
      3) [95] 재생성 실패 시 result=[] 저장 → 확정해둔 user_status/confirmed 영구 소실. 실패 시 500 반환으로 수정
      4) [100] generate_followup_comparison 모델 하드코딩 → model 파라미터 + get_setting("CLAUDE_MODEL") 주입
      권고: ai_status 폴백 배지(LLM 스키마 밖 값 크래시 방지), SSE done 지연 해소, 미사용 get_job_followup 삭제
    - 테스트 23개 추가 (총 189개)
- 현재 상태: 안정 — 전체 189개 테스트 통과, tsc --noEmit 통과 (팀리드 직접 검증)
- 막힌 점/주의:
  - 2026-08-27 18:09 계정 세션 한도로 팀 전체 중단 → 22:45 재개. 중단 시점에 미커밋 변경이 깨진 상태로 남아 있었음
    (summarizer 시그니처에 model 없는데 main.py가 model= 전달 → TypeError). 재개 후 정리 완료.
  - PR #76 최초 제출 시 테스트 185개가 통과했음에도 위 이슈 1·2가 남아 있었다. 원인: 테스트가 전부 DB 직접 조작 또는
    엔드포인트 직접 호출이라 **실제 사용자 경로**(시리즈 할당 → 대조 생성, 프론트가 보내는 payload 형태)를 지나지 않았음.
    앞으로 UI가 개입하는 기능은 사용자 경로 자체를 검증하는 테스트를 반드시 포함할 것.
- 다음 할 일 (기획 후보, 사용자 미승인) — **상세: `docs/ai_analysis/20260828_잔여_기획_후보.md` 를 먼저 읽을 것**
  1. 용어집(고유명사 사전) 기반 STT 후보정 — 난이도 중, 파급 효과 최대 (전사 품질이 모든 하위 기능을 좌우)
  2. 액션아이템 마감일 + 지연 표시 — 난이도 중, PR #71·#76에 빠진 마지막 조각인 기한 개념
  3. 하이라이트 클립 추출·공유 — 난이도 중, Range 요청(PR #70)·공유 토큰(PR #72) 기반 있음
  4. 이메일/Slack 발송 — 난이도 하~중, 외부 발송이라 사용자 확인 단계 필수
  5. C-1 실시간 전사 — 난이도 상, MLX-Whisper 스트리밍 리서치 선행 필요. 리서치만 별도 작업 단위로 끊을 것
  - 착수 방법: `meeting-jr-dev` 스킬 호출 → director 분석 → 팀원 소환 → TDD → 코드리뷰 → 머지
  - **TDD 조건 필수**: 프론트가 실제 보내는 payload 형태 + 사용자 경로 전체 + 기존 NULL 데이터 호환을 검증할 것
    (PR #76이 테스트 185개를 통과하고도 기능이 동작하지 않았던 원인)
- 관련 파일: backend/app/{main,database,summarizer}.py, backend/tests/test_{participation,series,followup}_api.py,
  frontend/components/{ParticipationChart,SeriesSelect,FollowupPanel,MainArea}.tsx, frontend/types/index.ts, DEVGUIDE.md
- 푸시 여부: origin/main 푸시 완료 (PR #75 3774226, PR #76 3a7a178 — 둘 다 squash 머지 + 브랜치 삭제)

---

## 2026-08-28 (작업 PC: 로컬) — 세션 51 (PR #71~#74: 4대 신규 기능 추가)
- 브랜치: main (PR #71 417ed8e, #72 a6a044f, #73 55d6614, #74 afe0574)
- 완료:
  - **PR #71 - 액션 아이템 통합 대시보드:**
    - GET /api/action-items — assignee/done 필터, 페이지네이션, pending_count, assignees 목록
    - /action-items 전용 페이지 — 필터 바, 완료 토글(optimistic), 원본 회의 링크
    - 사이드바 미완료 건수 배지
    - 코드리뷰 이슈: assignee 드롭다운 현재 페이지만 표시 → API에 assignees 필드 추가로 수정
  - **PR #72 - 회의록 공유 링크:**
    - POST /api/jobs/{id}/share, GET /api/shared/{token}, DELETE /api/jobs/{id}/share
    - /shared/[token] 읽기 전용 공유 페이지 (요약+트랜스크립트, 화자 컬러, 워터마크)
    - SummaryPanel에 공유/링크복사/공유중지 버튼
    - 코드리뷰 이슈: 에러 피드백 녹색 표시 → 에러는 빨간색으로 수정
  - **PR #73 - AI 추가 질의:**
    - POST /api/jobs/{id}/ask — transcript+summary context로 claude -p 질의
    - SummaryPanel 'AI 질의' 탭 — 채팅 버블 UI, 세션 내 히스토리
    - 코드리뷰: 이슈 없음 통과
  - **PR #74 - 크로스 회의 인사이트:**
    - POST /api/insights — keyword/날짜 필터 → 복수 회의 summary 기반 claude -p 질의
    - /insights 페이지 — 키워드, 날짜 범위, 질문 UI + 분석 결과 + 참조 회의 링크
    - 사이드바 "인사이트" 링크
    - 코드리뷰 이슈: keyword 경로 50개 vs no-keyword 10개 비대칭 → 양쪽 [:10] 통일
  - 전체 148개 테스트 통과, 4건 코드리뷰 모두 통과
- 현재 상태: 안정 — 로드맵 A-1~B-2 전부 완료
- 다음 할 일: C-1 실시간 전사 (MLX-Whisper 스트리밍 리서치 선행 필요)
- 관련 파일: backend/app/main.py, database.py, frontend/app/action-items/, shared/, insights/, components/SummaryPanel.tsx, Sidebar.tsx
- 푸시 여부: origin/main 푸시 완료 (afe0574)

---

## 2026-08-27 (작업 PC: 로컬) — 세션 50 (PR #68~#70: 녹음 파형 + 오디오 시킹 수정)
- 브랜치: main (PR #68 9533352, #69 2a2b183, #70 3dfcbfa)
- 완료:
  - **PR #68 - 녹음 시 음성 파형 미표시 수정:**
    - 원인: drawWave()를 setIsRecording(true) 직후 동기 호출 → canvas 미마운트 상태에서 canvasRef=null
    - 수정: useEffect로 isRecording/isPaused 상태 변화 후 canvas 확인 뒤 drawWave() 호출
  - **PR #69 - WebM remux (duration/Cues 추가):**
    - MediaRecorder WebM 파일에 duration=N/A → ffmpeg -c copy remux로 메타데이터 추가
    - _remux_webm_if_needed() 유틸: ffprobe 확인 → 필요 시 remux → 원본 교체
    - POST /api/record 저장 후 + GET /api/jobs/{id}/audio 서빙 시 적용
  - **PR #70 - HTTP Range 요청 지원:**
    - Starlette FileResponse가 Range 미지원 → seekable={0,0} → 시킹 불가
    - StreamingResponse로 206 Partial Content + Content-Range 구현
    - Accept-Ranges: bytes 헤더 추가
  - Playwright 검증: 전체 5개 녹음 파일 시킹 정상 동작 확인
    - 데이터 거버넌스(2053초), 마이크 테스트(37초), 주일 예배(2067초), 회의(49초), 가족 일상 대화(49초) — 모두 seekOK
    - 기존 webm 파일은 GET /audio 최초 요청 시 자동 remux
  - 3건 코드리뷰 모두 통과
- 현재 상태: 안정 — 녹음 파형 + 오디오 시킹 완전 해결
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: frontend/components/RecordingZone.tsx, backend/app/main.py
- 푸시 여부: origin/main 푸시 완료 (3dfcbfa)

---

## 2026-08-27 (작업 PC: 로컬) — 세션 49 (PR #63~#67: diarization DB + SummaryPanel + 프로필 추출 + 음성 매칭 UX)
- 브랜치: main (PR #63 0daed85, #64 937b501, #65 2d88f25, #66 bd33196, #67 8b62f3c, hotfix fb5ef77)
- 완료:
  - **PR #63 - Diarization DB 통합:**
    - meetings.diarization TEXT 컬럼 추가, DB 우선 조회 + lazy migration
  - **PR #64 - SummaryPanel 높이 붕괴 수정:**
    - md:h-auto → md:h-full, SummaryPanel flex-1 min-h-0, 하단 섹션 max-h-[35%] 래퍼
  - **PR #65 - Identity-mapped speakers 프로필 추출 수정:**
    - speakers {아빠: 아빠} 형태에서 SPEAKER_XX 매핑 소실 → transcript 타임스탬프 교차 비교 폴백
  - **PR #66 - 타임스탬프 매칭 개선:**
    - ±2초 포인트 매칭 → 구간 overlap 면적 매칭 (실제 데이터로 아빠 프로필 추출 성공 확인)
  - **PR #67 - 음성 매칭 UX 개선 + 기존 녹음 재매칭:**
    - TranscriptEditor: 자동 채우기 제거 → 제안 칩 `👤 이름 85% [적용]` + 되돌리기
    - POST /api/jobs/{id}/rematch: done 상태 회의에서 voice profile 재매칭
    - POST /api/jobs/{id}/apply-match: 매칭 결과를 transcript/speakers에 반영
    - MainArea: "🎤 음성 매칭" 버튼 + 결과 모달 + 전체 적용
    - _extract_and_match_speakers() 공통 함수 추출 (job_queue 인라인 → 재사용)
    - 코드리뷰 수정: handleApplyMatch null 필터링 + res.ok 검증
  - **Hotfix fb5ef77 - rematch 모달 키 불일치 수정:**
    - 모달이 speakers 키(아빠) 대신 rematchResult 키(SPEAKER_XX)로 순회하도록 수정
    - Playwright 검증: SPEAKER_00 → 아빠 (100%) 매칭 + 전체 적용 성공 확인
  - 전체 105개 테스트 통과, 5건 코드리뷰 통과
- 현재 상태: 안정
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: backend/app/database.py, job_queue.py, main.py, tests/test_speaker_profile.py, test_rematch_api.py, frontend/components/MainArea.tsx, SummaryPanel.tsx, TranscriptEditor.tsx
- 푸시 여부: origin/main 푸시 완료 (fb5ef77)

---

## 2026-08-27 (작업 PC: 로컬) — 세션 49 이전 기록 (diarization DB 통합 PR #63 + SummaryPanel 수정 PR #64)
- 브랜치: main (PR #63 squash 머지 0daed85, PR #64 squash 머지 937b501)
- 완료:
  - **PR #63 - Diarization DB 통합:**
    - meetings.diarization TEXT 컬럼 추가 (마이그레이션)
    - get_job_diarization() 경량 조회 헬퍼
    - job_queue: process_audio 결과의 diarization을 DB에 저장
    - save_speaker_profile: DB 우선 → 파일 폴백(lazy migration) → WAV 재실행 3단계 로직
    - 테스트 2개 추가 (DB-only, lazy migration), 전체 95개 통과
  - **PR #64 - SummaryPanel 높이 붕괴 버그 수정:**
    - 원인: md:h-auto가 flex stretch 무효화 → SummaryPanel 2px 붕괴 → overflow-hidden 클리핑
    - 수정: md:h-full + SummaryPanel flex-1 min-h-0 + 하단 섹션 max-h-[35%] 래퍼
    - Playwright 검증: 385px 높이 + 탭/편집 버튼 동작 확인
  - 두 PR 모두 코드리뷰 통과 (80점 이상 이슈 없음)
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: backend/app/database.py, backend/app/job_queue.py, backend/app/main.py, backend/tests/test_speaker_profile.py, frontend/components/MainArea.tsx, frontend/components/SummaryPanel.tsx
- 푸시 여부: origin/main 푸시 완료 (0daed85)

## 2026-08-27 (작업 PC: 로컬) — 세션 48 (프로필 추출 버그 수정 PR #62)
- 브랜치: main (PR #62 squash 머지, d065e3e)
- 완료:
  - Backend: save_speaker_profile에서 매핑된 화자 이름(김팀장 등)으로 diarization 역조회 로직 추가
  - Frontend: TranscriptEditor에서 suggestedNames를 names 초기값으로 사전 입력 (빈 문자열 대신)
  - TDD: qa-engineer 테스트 먼저 작성 → backend-dev/frontend-dev 구현 → qa 재검증 (93/93 통과)
  - 코드리뷰: /code-review 스킬 실행, 80점 이상 이슈 없음 → 통과
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: backend/app/main.py, backend/tests/test_speaker_profile.py, frontend/components/TranscriptEditor.tsx, frontend/__tests__/TranscriptEditor.test.tsx
- 푸시 여부: origin/main 푸시 완료 (d065e3e)

## 2026-08-27 (작업 PC: 로컬) — 세션 47 (하네스 최종 프로세스 정립)
- 브랜치: main (1c97a50)
- 완료:
  - 하네스 팀 구조·프로세스 최종 정립 (8개 파일 수정)
  - 프로세스 A(새 기능): PM brainstorming → 사용자 승인 → director → TDD → 개발 → QA → 코드리뷰 → 머지
  - 프로세스 B(버그): director 분석 → TDD → 개발 → QA → 코드리뷰 → 머지
  - TDD 도입: qa-engineer가 구현 전 테스트 먼저 작성
  - 팀리드 상황 판단: 기획→PM, 버그→director, 기능→director
  - 시스템 제약 반영: teammate 소환 불가 → 팀리드만 소환, director는 SendMessage 코디네이션
  - 보고 체계: 팀원→director→팀리드→사용자 (기획안만 사용자 승인)
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: .claude/skills/meeting-jr-dev/SKILL.md, .claude/agents/*.md, CLAUDE.md
- 푸시 여부: origin/main 푸시 완료 (1c97a50)

## 2026-08-27 (작업 PC: 로컬) — 세션 46 (speaker_map 이름 파싱 + 하네스 재정비 PR #61)
- 브랜치: main (PR #61 squash 머지, 10279a0)
- 완료:
  - Backend: finalize 시 identity-mapped speaker_map 감지 → transcript에서 실제 이름 파싱 (이름 자체를 키로 사용)
  - Frontend: 드롭다운에서 key===value일 때 중복 표시 방지
  - 코드리뷰: sorted keys vs appearance order 매핑 버그 발견 → 수정 후 재리뷰 통과
  - 하네스 전면 재정비: 팀 구조(director 최상위), Phase 0~5 재구성, brainstorming/worktree 추가
  - teammate 소환 제약 발견: flat 구조 → 팀리드만 소환 가능, 스킬/에이전트 문서 반영
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: backend/app/main.py, frontend/components/SettingsModal.tsx, .claude/skills, .claude/agents
- 푸시 여부: origin/main 푸시 완료 (72f0220)

## 2026-08-27 (작업 PC: 로컬) — 세션 45 (오디오 시크바 + duration 수정 PR #60)
- 브랜치: main (PR #60 squash 머지, 7d5c365)
- 완료:
  - AudioPlayer: webm duration Infinity 문제 해결 (durationchange + seek-to-end 워크어라운드 + fallbackDuration 3단계 폴백)
  - 시크바 클릭/드래그 탐색 활성화 (duration 정상화로 disabled 해제)
  - MainArea: job.duration_sec를 fallbackDuration prop으로 전달
  - TranscriptEditor: onDurationChange 핸들러 추가
  - preload="metadata" → "auto" 변경
  - 하네스 스킬 호출 시 무조건 TeamCreate 규칙 추가 (별도 창 표시)
  - 절차: frontend-dev → qa-engineer (전항목 PASS) → 코드 리뷰 (이슈 0건) → 머지
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: frontend/components/AudioPlayer.tsx, MainArea.tsx, TranscriptEditor.tsx
- 푸시 여부: origin/main 푸시 완료 (dc53501)

## 2026-08-26 (작업 PC: 로컬) — 세션 44 (diarization 재실행 프로필 추출 PR #59)
- 브랜치: main (PR #59 squash 머지, bfab3b6)
- 완료:
  - _diarization.json 없지만 _16k.wav 있는 기존 회의에서 프로필 추출 시 diarization 자동 재실행
  - audio_processor.py: run_diarization_and_save() 함수 추가 (pyannote 독립 실행 + JSON 저장)
  - main.py: save-speaker-profile 엔드포인트에서 wav 있으면 재실행 분기 추가
  - 절차: ai-engineer → qa-engineer (전항목 PASS) → 코드 리뷰 (이슈 0건) → 머지
- E2E 테스트 완료: 주일 예배 → 목사님(SPEAKER_00) 프로필 추출 성공 (pyannote/embedding 모델 수락 필요 — gated repo)
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: backend/app/audio_processor.py, backend/app/main.py
- 푸시 여부: origin/main 푸시 완료 (bfab3b6)

## 2026-08-26 (작업 PC: 로컬) — 세션 43 (프로필 추출 화자 이름 매칭 PR #58)
- 브랜치: main (PR #58 squash 머지, 396e471)
- 완료:
  - 설정 > 목소리 프로필 > 기존 회의에서 추출 화자 드롭다운에 실제 이름 표시
  - 이름 있으면 "목사님 (SPEAKER_00)" 형식, 없으면 기존대로 SPEAKER_XX
  - 화자 선택 시 프로필 이름 자동 입력 (extractSpeakerMap 상태 추가)
  - 절차: frontend-dev → qa-engineer (전항목 PASS) → 코드 리뷰 (이슈 0건) → 머지
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: frontend/components/SettingsModal.tsx
- 푸시 여부: origin/main 푸시 완료 (396e471)

## 2026-08-26 (작업 PC: 로컬) — 세션 42 (설정 모달 사이드바 이동 버그 수정 PR #57)
- 브랜치: main (PR #57 squash 머지, d0cfc34)
- 완료:
  - 설정 화면이 열려있을 때 사이드바에서 회의록 클릭 시 설정을 닫고 해당 회의록으로 이동하도록 수정
  - SettingsModal에 isDirtyRef prop 추가 (API 키 입력 중, 카테고리 편집 중일 때 dirty 판단)
  - dirty 상태에서 이동 시 "변경사항을 저장하지 않고 이동하시겠습니까?" confirm 대화상자 표시
  - 새 녹음 버튼에도 동일한 dirty check 적용
  - TypeScript 타입 체크 통과, 백엔드 테스트 90건 전체 pass
  - 코드리뷰: 이슈 없음 (통과)
- 다음 할 일: 다음 기능/버그 수정
- 관련 파일: frontend/app/page.tsx, frontend/components/SettingsModal.tsx
- 푸시 여부: origin/main 푸시 완료 (d0cfc34)

## 2026-08-26 (작업 PC: 로컬) — 세션 41 (목소리 프로필 추출 버그 수정 PR #56)
- 브랜치: main (PR #56 squash 머지, adde99f)
- 완료:
  - 설정 > 목소리 프로필 > "기존 회의에서 추출" 버튼 무반응 버그 수정
  - 프론트엔드: fetch 응답 상태(res.ok) 체크 추가, 에러 시 alert 표시, extracting 로딩 상태 추가
  - 백엔드: txt 업로드 회의에서 프로필 추출 시도 시 사용자 친화적 에러 메시지 반환
  - QA 검증 15/15 PASS, 백엔드 테스트 90건 전체 pass
- 다음 할 일: 다음 기능 기획
- 관련 파일: frontend/components/SettingsModal.tsx, backend/app/main.py
- 푸시 여부: origin/main 푸시 완료 (adde99f)

## 2026-08-26 (작업 PC: 로컬) — 세션 40 (PDF 다크모드 + 트랜스크립트 제거 PR #55)
- 브랜치: main (PR #55 squash 머지, 3260bdd)
- 완료:
  - 다크모드에서 PDF 저장 시 흰 배경에 흰 글자 출력 문제 수정
    - html/body에 color-scheme: light 강제, .dark 클래스 무력화
    - 모든 텍스트 요소에 !important로 명시적 라이트 색상 지정
    - Tailwind className → inline style로 컨테이너 색상 고정
  - PDF에서 대화 스크립트(트랜스크립트) 섹션 완전 제거, 요약만 포함
  - 미사용 parseTranscript 함수 제거
  - 코드리뷰: 이슈 없음 (통과)
  - 백엔드 테스트 90건 전체 pass
- 다음 할 일: 다음 기능 기획
- 관련 파일: frontend/app/print/[id]/page.tsx
- 푸시 여부: origin/main 푸시 완료 (3260bdd)

## 2026-08-26 (작업 PC: 로컬) — 세션 39 (ClovaNote txt 형식 파싱 수정 PR #54)
- 브랜치: main (PR #54 squash 머지, e1a8393)
- 완료:
  - 백엔드: `_parse_txt_transcript()` 함수 추가 — ClovaNote 내보내기 형식 자동 감지 및 표준 형식 변환
  - ClovaNote 형식: `참석자 N MM:SS\n텍스트` → `[MM:SS] SPEAKER_XX: 텍스트` 변환
  - 멀티라인 발화 텍스트를 단일 줄로 병합
  - 헤더 영역(제목/날짜/이름) 자동 건너뛰기 (false positive 방지: `\d{2}:\d{2}` 엄격 매칭)
  - suggested_names에 원본 화자 이름 매핑 (TranscriptEditor에서 자동 표시)
  - 테스트 4건 추가 (ClovaNote 업로드 통합, 표준/ClovaNote/미인식 형식 단위 테스트, 전체 90 pass)
- E2E 테스트 완료: 실제 ClovaNote 파일(회의록.txt, 참석자 5명/91발화) 브라우저 업로드 → 화자 자동 파싱 → TranscriptEditor 렌더링 → 문서 생성(Claude 요약) → done 전환 모두 정상
- 다음 할 일: 다음 기능 기획
- 관련 파일: backend/app/main.py, backend/tests/test_upload.py
- 푸시 여부: origin/main 푸시 완료 (e1a8393)

## 2026-08-26 (작업 PC: 로컬) — 세션 38 (txt 업로드 speakers 타입 불일치 수정 PR #53)
- 브랜치: main (PR #53 squash 머지, f33d5cc)
- 완료:
  - 백엔드: txt 업로드 시 speakers를 빈 딕셔너리({}) → 화자 파싱 배열([])로 변경
  - 백엔드: `\w+` regex로 `[MM:SS] SPEAKER_XX:` 패턴 자동 파싱, suggested_names/suggested_speakers 필드 추가
  - 프론트: ProgressCard.tsx에 Array.isArray 방어 코드 추가 (딕셔너리→배열 변환)
  - 중복 import re 제거 (모듈 최상단에 이미 존재)
  - 코드리뷰: regex `[^:]+` 과도한 패턴 → `\w+`로 제한 (비화자 텍스트 캡처 방지)
- 다음 할 일: 다음 기능 기획
- 관련 파일: backend/app/main.py, frontend/components/ProgressCard.tsx
- 푸시 여부: origin/main 푸시 완료 (f33d5cc)

## 2026-08-26 (작업 PC: 로컬) — 세션 37 (녹음 중 메모 + 북마크 PR #52)
- 브랜치: main (PR #52 squash 머지, 6a12472)
- 완료:
  - 기능 B (트랜스크립트 전문 검색): PR #51로 이미 머지됨 확인, 스킵
  - 기능 A (녹음 중 메모 + 북마크):
    - recording_notes 테이블 신규 (database.py)
    - POST/GET/DELETE /api/jobs/{job_id}/notes API 3개
    - RecordingZone: 녹음 중 메모 입력 + 북마크(깃발) 버튼, notesRef로 stale closure 방지
    - MainArea: done 상태에서 녹음 중 메모 표시 + 타임스탬프 클릭 시 오디오 이동
    - RecordingNote 인터페이스 (types/index.ts)
    - test_recording_notes.py 5건 추가 (전체 86 pass)
  - 코드리뷰: stale closure bug 발견 → notesRef 사용으로 수정 후 머지
- 다음 할 일: 다음 기능 기획
- 관련 파일: backend/app/{database,main}.py, frontend/components/{RecordingZone,MainArea}.tsx, frontend/types/index.ts, backend/tests/test_recording_notes.py
- 푸시 여부: origin/main 푸시 완료 (6a12472)

## 2026-08-26 (작업 PC: 로컬) — 세션 35 (타임스탬프→오디오 이동 + 카테고리 프롬프트 템플릿 PR #50)
- 브랜치: main (PR #50 squash 머지, 2f1980a)
- 완료:
  - 타임스탬프 클릭→오디오 이동: AudioPlayer forwardRef+useImperativeHandle seekTo, MainArea audioPlayerRef, SummaryPanel parseInlineTimestamps
  - 카테고리별 요약 프롬프트 템플릿: DB prompt_template 컬럼, CRUD API, SettingsModal textarea UI
  - 코드리뷰 2건 수정: create_category prompt_template 누락 + 액션 아이템 타임스탬프 파싱
- 다음 할 일: 3번(트랜스크립트 전문 검색) 또는 4번(녹음 중 북마크) 기획
- 관련 파일: backend/app/{database,main,summarizer}.py, frontend/components/{AudioPlayer,MainArea,SummaryPanel,SettingsModal}.tsx, frontend/types/index.ts
- 푸시 여부: origin/main 푸시 완료 (2f1980a)

## 2026-08-26 (작업 PC: 로컬) — 세션 34 (노이즈 제거 + 요약 별점 PR #49)
- 브랜치: main (PR #49 squash 머지, 36bc929)
- 완료:
  - 오디오 노이즈 제거: FFmpeg afftdn/highpass/lowpass 필터 조건부 적용 (설정 ON/OFF)
  - GET/PUT /api/settings/denoise 엔드포인트
  - SettingsModal 일반 탭 노이즈 제거 토글 스위치
  - 요약 품질 별점: jobs 테이블 rating 컬럼 추가
  - PATCH /api/jobs/{id}/rating, GET /api/stats/ratings API
  - SummaryPanel ★★★★★ 별점 UI + 저장 확인 메시지
  - MeetingCard 카드 하단 별점 표시
  - 코드리뷰: 80점 이상 이슈 없음 → 통과
- 테스트 완료:
  - 별점 클릭 → PATCH 저장 → "피드백 감사합니다" 표시 → /meetings 카드 별 표시 ✓
  - 노이즈 제거 토글 ON → API {"enabled": true} 저장 확인 ✓
- 다음 할 일: 다음 기능 기획 (product-manager에게 요청)
- 관련 파일: backend/app/{audio_processor,database,main}.py, frontend/components/{SettingsModal,SummaryPanel,MeetingCard,MainArea}.tsx, frontend/types/index.ts
- 푸시 여부: origin/main 푸시 완료 (36bc929)

## 2026-08-26 (작업 PC: 로컬) — 세션 33 (목소리 프로필 자동 매칭 PR #48)
- 브랜치: main (PR #48 squash 머지, 632daa3)
- 완료:
  - 백엔드: voice_profiles 테이블, embedding CRUD, Voice Profile API 7개
  - 백엔드: PyAnnote embedding 추출 함수 (extract_speaker_embedding, extract_embeddings_from_diarization)
  - 백엔드: match_speaker_to_profiles() 코사인 유사도 매칭 (임계값 0.75)
  - 백엔드: job_queue.py awaiting_edit 전 자동 매칭 + suggested_speakers SSE 전달
  - 백엔드: GET/PUT /api/voice-profiles/threshold 엔드포인트
  - 프론트: SettingsModal 화자 탭 → 목소리 프로필 관리 (목록, 직접 녹음, 기존 회의 추출, 임계값 슬라이더)
  - 프론트: TranscriptEditor 자동 매칭 결과 표시 (이름 + 신뢰도 배지)
  - 프론트: SpeakerMapper "이 목소리를 프로필로 저장" 체크박스 추가
  - 코드리뷰 3건 발견 → 수정 완료:
    1. confidence * 100 이중변환 제거 (TranscriptEditor.tsx)
    2. suggested_speakers SSE → DB 저장 + ProgressCard/MainArea 전달 연결
    3. rename-speakers 엔드포인트 추가 (main.py)
- 다음 할 일: 실제 서버 실행 후 end-to-end 테스트 (목소리 프로필 등록 → 녹음 → 자동매칭 확인)
- 관련 파일: backend/app/{database,audio_processor,job_queue,main}.py, frontend/components/{SettingsModal,TranscriptEditor,SpeakerMapper,ProgressCard,MainArea}.tsx, frontend/types/index.ts
- 푸시 여부: origin/main 푸시 완료 (632daa3)

## 2026-08-26 (작업 PC: 로컬) — 세션 31 (설정 UX 개선 PR #47)
- 브랜치: main (PR #47 squash 머지, 458f214)
- 완료:
  - 설정 패널: 모달 → 메인 영역 페이지 방식으로 변환 (← 돌아가기)
  - Claude 탭 제거, 카테고리별 모델 선택 드롭다운 추가 (Opus/Sonnet/Haiku)
  - categories 테이블 model 컬럼 추가, CRUD/backup/restore 반영
  - 기본 회의 제목 설정 항목 제거
  - "새 회의 녹음" → "새 녹음" 용어 수정
  - 다크모드 텍스트 색상 버그 수정
  - 코드리뷰: backup/restore model 누락 + 저장버튼 비활성화 2건 발견→수정
- QA: 8/8 통과 (블로커 없음). 경미한 이슈: 복원 배너 다크모드 미적용 (후속 처리)
- 현재 상태: main 최신 (458f214)
- 다음 할 일: 없음
- 관련 PR: #47
- 푸시 여부: origin/main 푸시 완료

## 2026-08-26 (작업 PC: 로컬) — 세션 30 (기능 2개 완료)
- 브랜치: main (PR #43, #45 squash 머지)
- 완료:
  - 선택 모드 일괄 북마크: ★ 버튼, Promise.all 병렬 API 호출, QA 통과 (PR #43)
  - 회의 제목 인라인 편집: Sidebar 더블클릭→input, ref guard로 이중호출 방지, MainArea 편집, Esc 취소 시 PATCH 방지 (PR #45)
  - 날짜 범위 필터: 이미 구현 완료 확인 (추가 작업 불필요)
- 코드리뷰: PR #45에서 버그 3개 발견 → 수정 후 재푸시 → 재리뷰 통과
- QA: PR #43 QA 통과 (북마크 토글, 선택모드 해제 확인)
- 현재 상태: main 최신 (9d37a0b)
- 다음 할 일: 없음
- 관련 PR: #43 (머지), #44 (close, #45로 대체), #45 (머지)
- 푸시 여부: origin/main 푸시 완료
- 추가: QA가 발견한 Sidebar 더블클릭 2회차 버그 (span 단일클릭 버블링) → PR #46 코드리뷰 통과 → 머지 (c2fb016)

## 2026-08-26 (작업 PC: 로컬) — 세션 29 (기능 2개 + 기존 확인)
- 브랜치: main (PR #41 squash 머지, PR #42 close)
- 완료:
  - 월별 통계 차트: recharts BarChart, GET /api/stats/monthly, MonthlyChart 컴포넌트 (PR #41)
  - 다중 선택 삭제: 체크박스, 선택 모드, 일괄 삭제 (PR #41에 포함)
  - 인쇄/PDF: 이미 /print/[id] 페이지로 구현 완료 확인 (추가 작업 불필요)
- QA: PR #41에 bulk-select 중복 포함 발견 → PR #42 close 처리
- 현재 상태: main 최신 (8029a61)
- 다음 할 일: 없음
- 관련 PR: #41 (머지), #42 (close)
- 푸시 여부: origin/main 푸시 완료

## 2026-08-26 (작업 PC: 로컬) — 세션 28 (기능 4개 완료)
- 브랜치: main (PR #37~#40 squash 머지)
- 완료: backend-dev + frontend-dev × 2 + qa-engineer 병렬 구현
  - 전체 텍스트 검색 개선: summary/transcript LIKE 검색 + snippet 추출 (PR #37)
  - 녹음 일시정지/재개: MediaRecorder pause/resume, ⏸/▶ 버튼, QA 통과 (PR #38)
  - 카테고리 뱃지: MeetingCard에 카테고리 색상 뱃지 5종 (PR #39)
  - 검색 결과 snippet 표시: 검색어 주변 텍스트 MeetingCard에 표시 (PR #40)
- 현재 상태: main 최신 (1e23a43)
- 다음 할 일: 없음
- 관련 PR: #37, #38, #39, #40
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 27 (사이드바 + 카드 기능)
- 브랜치: main (직접 커밋 + PR #36)
- 완료:
  - /meetings 카드 북마크 토글 버튼 추가 (313bec6)
  - /meetings 카드 삭제 버튼 추가 + confirm 다이얼로그 (6a969ee)
  - 사이드바 접기/펼치기: w-0↔w-60 transition, «/» 버튼, [ 단축키, localStorage (PR #36)
- 현재 상태: main 최신 (75960af)
- 다음 할 일: 없음
- 관련 PR: #36
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 26 (다크모드 버그 수정)
- 브랜치: main (PR #34 squash 머지)
- 완료: 다크모드 전체 영역 적용 버그 수정
  - 기존: 상단 바만 다크모드 적용됨
  - 수정: Sidebar, MainArea, SummaryPanel 등 12개 컴포넌트 dark: 클래스 일괄 보완 (PR #34)
  - 잔여 이슈 추가 수정: MeetingCard 상태 뱃지, SummaryPanel 리스트, SettingsModal 버튼, TranscriptEditor 화자 색상 (PR #35)
  - 확인: 코드 리뷰 이슈 0건 (클린 패스)
- 현재 상태: main 최신 (add523f)
- 다음 할 일: 사이드바 접기/펼치기 기능 (product-manager 기획 대기 중)
- 관련 PR: #34, #35
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 25 (신규 기능 3개 완료)
- 브랜치: main (PR #31~#33 squash 머지)
- 완료: director 직접 구현 (3가지 기능)
  - 설정 백업/복원: GET /api/settings/backup, POST /api/settings/restore, SettingsModal 내보내기/가져오기 UI (PR #31)
  - Claude 프롬프트 미리보기: 카테고리 편집/생성 시 미리보기 버튼, 샘플 대화 삽입 프롬프트 모달 (PR #32)
  - Notion 연동 상태 표시: MeetingCard Notion 배지, MainArea 상태 배지 (등록됨/미등록) (PR #33)
- 코드 리뷰: PR #31에서 민감 키 평문 노출 이슈 발견 → 수정 후 머지, PR #32/#33 클린 패스
- 현재 상태: main 최신
- 다음 할 일: 없음
- 관련 PR: #31, #32, #33
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 24 (신규 기능 3개 완료)
- 브랜치: main (PR #27~#29 squash 머지)
- 완료: director + frontend-dev 팀 구현 (3가지 기능)
  - 검색 결과 하이라이트: /meetings 검색어 일치 텍스트 노란색 형광 강조, XSS 안전 (PR #27)
  - 공유 링크 URL 라우팅: /meetings/[id] 직접 접근, 링크 복사 버튼 (PR #28)
  - Sidebar URL 동기화: 클릭 시 history.pushState, popstate 뒤로 가기 지원 (PR #30)
  - 키보드 단축키 도움말: ? 키로 단축키 목록 모달, useKeyboardShortcuts 훅 확장 (PR #29)
- 현재 상태: main 최신 (21c6603)
- 다음 할 일: 없음
- 관련 PR: #27, #28, #29, #30
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 23 (신규 기능 3개 완료)
- 브랜치: main (PR #24~#26 squash 머지)
- 완료: product-manager 기획 → director 팀 구현 (3가지 기능)
  - 타임스탬프 클릭 → 오디오 점프: [MM:SS] 버튼 파란색 링크 스타일, CustomEvent audio-seek (PR #24)
  - 요약 재생성: POST /api/jobs/{id}/regenerate, SummaryPanel 재생성 버튼+카테고리 선택 모달 (PR #25)
  - 회의 태그: DB tags 컬럼, PATCH /api/jobs/{id}/tags, GET /api/tags, 태그 입력 UI, /meetings 필터, Sidebar 뱃지 (PR #26)
- 현재 상태: main 최신 (7a28dbb)
- 다음 할 일: 없음
- 관련 PR: #24, #25, #26
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 22 (신규 기능 4개 완료)
- 브랜치: main (PR #18~#23 squash 머지)
- 완료: product-manager + director 협의 후 4개 기능 개발
  - 북마크/즐겨찾기: DB bookmarked 컬럼, PATCH API, Sidebar 별표 토글, /meetings 필터 (PR #18, #22)
  - 회의 메모 필드: DB memo 컬럼, PATCH API, done 화면 textarea+저장 (PR #19, #22)
  - 다크모드 파형+Notification: AnalyserNode 캔버스 다크/라이트, done/error 브라우저 알림 (PR #20)
  - ZIP 전체 내보내기: GET /api/export StreamingResponse, /meetings 버튼 (PR #21, #23)
- 현재 상태: main 최신 (3651b4f), 서버 실행 중
- 다음 할 일: 없음
- 관련 PR: #18, #19, #20, #21, #22, #23
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 21 (서버 검증 + 버그 수정)
- 브랜치: main (직접 커밋 8c6f1be)
- 완료: 신규 기능 3개 서버 검증 + 버그 수정
  - fix: PR #16(연관 회의 API) 코드 누락 확인 → main.py에 직접 구현
    - _extract_keywords() 헬퍼: 불용어 제거, 빈도 기반 상위 N개
    - GET /api/jobs/{id}/related: 키워드 매칭 상위 5개 반환
  - 검증: 키보드 단축키 힌트 표시, 연관 회의 섹션 정상 렌더링 확인 (Playwright 스크린샷)
- 현재 상태: main 최신 (8c6f1be), 서버 실행 중 (백엔드 8000, 프론트 3000)
- 다음 할 일: 없음
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 20 (신규 기능 3개 완료)
- 브랜치: main (PR #13~#17 squash 머지)
- 완료: product-manager + director 협의 후 3개 기능 개발
  - 액션 아이템 체크리스트: DB action_items 컬럼, Claude 요약 파싱, PATCH API, 인터랙티브 UI (PR #13, #15)
  - 키보드 단축키: useKeyboardShortcuts 훅, Space/←→/Esc, input 포커스 시 비활성화 (PR #14)
  - 연관 회의 검색: 키워드 추출 API, done 화면 하단 관련 회의 섹션 UI (PR #16, #17)
- 현재 상태: main 최신 (a468deb), 서버 실행 중
- 다음 할 일: 없음 (신규 기획 기능 모두 완료)
- 관련 PR: #13, #14, #15, #16, #17
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 19 (A, C, G 완료)
- 브랜치: main (feature/multilang-stt → PR #12 → squash 머지)
- 완료: A, C, G 전체 완료
  - A. 자동 회의 제목 생성: run_summary 후 # 첫 줄 파싱 → update_job_title (PR #10)
  - C. 마크다운 내보내기: ↓ MD 버튼, Blob 방식, 제목+날짜+요약+스크립트 (PR #11)
  - G. 다국어 STT: DB language 컬럼, 드롭다운 UI (🇰🇷/🇺🇸/🇯🇵/🌐), Whisper 전달 (PR #12)
- 현재 상태: main 최신 (7774763), 서버 실행 중 (백엔드 8000, 프론트 3000)
- 다음 할 일: 없음 (모든 계획 기능 완료)
- 관련 PR: #10, #11, #12
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 18
- 브랜치: main (feature/markdown-export → PR #11 → squash 머지)
- 완료: C. 마크다운 내보내기 (↓ MD 버튼, Blob 방식)
- 현재 상태: main 최신 (ceaba1f)
- 관련 PR: #11
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 17
- 브랜치: main (feature/auto-title → PR #10 → squash 머지)
- 완료: A. 자동 회의 제목 생성 (run_summary 요약 첫 # 줄 파싱)
- 현재 상태: main 최신 (4c4425e)
- 관련 PR: #10
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 16 (서버 검증 + 버그 수정)
- 브랜치: main (직접 커밋)
- 완료: 브라우저 실제 동작 검증 + 버그 수정
  - fix: 화자 탭 SPEAKER_00 등 내부 ID 표시 버그 → 실제 이름(값)으로 수정
    - 프론트: Object.keys() → Object.values() (중복 제거 포함)
    - 백엔드: DELETE /api/speakers/{name} — 값 기준 삭제로 변경
  - 검증: 메인/다크모드/통계카드/화자탭 모두 정상 확인 (Playwright 스크린샷)
- 현재 상태: main 최신 (05efd13), 서버 실행 중 (백엔드 8000, 프론트 3000)
- 다음 할 일: 없음 (모든 계획 기능 완료 + 검증)
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 15 (기능 b~f 완료)
- 브랜치: main (feature/mobile-responsive → PR #9 → squash 머지)
- 완료: 기능 b~f 전체 완료
  - b. 화자 프로필 관리: POST/DELETE /api/speakers + 설정 모달 '화자' 탭 (PR #7)
  - c. 통계 대시보드: GET /api/stats + /meetings 페이지 통계 카드 4개 (PR #8)
  - d. 실패 재시도: 이미 구현 확인 (추가 PR 불필요)
  - e. 다크 모드: useTheme 훅 + Tailwind class 전체 적용 (PR #6, 세션 12)
  - f. 모바일 최적화: Sidebar 삭제 버튼 모바일 상시표시, ProgressCard 패딩 (PR #9)
- 현재 상태: main 최신 (9b6dbbb), 브랜치 origin/main 만 남음
- 다음 할 일: 없음 (모든 계획 기능 완료)
- 관련 PR: #6, #7, #8, #9
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 14
- 브랜치: main (feature/stats-dashboard → PR #8 → squash 머지)
- 완료:
  - c. 통계 대시보드: GET /api/stats + /meetings 페이지 통계 카드 4개 (PR #8)
  - d. 실패 재시도: 이미 구현됨 확인 (backend POST /api/jobs/{id}/retry + MainArea 버튼, 별도 PR 불필요)
- 현재 상태: main 최신 (4d84a7c)
- 관련 커밋: PR #7, PR #8
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 13
- 브랜치: main (feature/speaker-profile → PR #7 → squash 머지)
- 완료: 화자 프로필 관리
  - 백엔드: POST /api/speakers, DELETE /api/speakers/{name}
  - 프론트: 설정 모달 '화자' 탭 (이름 추가/삭제, Enter 지원)
- 현재 상태: main 최신 (04bdded)
- 관련 커밋: PR #7
- 푸시 여부: origin/main 푸시 완료

## 2026-08-25 (작업 PC: 로컬) — 세션 12
- 브랜치: main (feature/dark-mode → PR #6 → squash 머지)
- 완료: 다크 모드 지원 + git 브랜치 정리
  - `tailwind.config.ts`: `darkMode: 'class'` 추가
  - `frontend/hooks/useTheme.ts`: localStorage + 시스템 preference 감지, FOUC 방지, hydration 안전 (null 초기값)
  - `layout.tsx`: 인라인 스크립트 FOUC 방지, `suppressHydrationWarning`
  - `Sidebar.tsx`: 다크/라이트 토글 버튼 추가
  - `MainArea.tsx`, `AudioPlayer.tsx`: dark: Tailwind 클래스 전체 적용
- 브랜치 정리: stale 원격 브랜치 6개 pruned (clipboard-copy, pdf-export, playback-speed, sidebar-delete-button, summary-patch-test, dark-mode)
- 현재 상태: main 최신 (6fee23a), 브랜치 origin/main 만 남음
- 다음 할 일: 나머지 기능 (b. 화자 프로필 관리, c. 통계 대시보드, d. 실패 재시도, f. 모바일 최적화) 순차 개발
- 관련 커밋: PR #6
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 11
- 브랜치: main (feature/sidebar-delete-button → PR #3, feature/summary-patch-test → PR #4)
- 완료: 기능 a~f 검증 및 보강
  - a. Browser Notification: 이미 구현됨 (ProgressCard.tsx + MainArea.tsx)
  - b. 음파 시각화: 이미 구현됨 (RecordingZone.tsx AnalyserNode + canvas)
  - c. 음성 다운로드: 이미 구현됨 (MainArea.tsx `<a download>`)
  - d. 회의 삭제: 사이드바 hover 시 휴지통 삭제 버튼 추가 (PR #3)
  - e. 요약 편집+저장: 이미 구현됨 + 백엔드 테스트 3개 추가 (PR #4)
  - f. 재요약: 이미 구현됨 (카테고리 변경 모달 포함)
- 현재 상태: main 최신 (11c2f58)
- 다음 할 일: 새 기능 논의
- 관련 커밋: 80f5eed (PR #3), 11c2f58 (PR #4)
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 10
- 브랜치: main (feature/playback-speed → PR #2 → squash 머지)
- 완료: 오디오 재생 속도 조절 버튼 (0.75x/1x/1.25x/1.5x/2x 순환)
- 현재 상태: main 최신 (83b711a), 서버 실행 중 (백엔드 8000, 프론트 3000)
- 다음 할 일: 새 기능 논의
- 구현 내용:
  - frontend/components/AudioPlayer.tsx: SPEEDS 배열, speed state, handleSpeedChange(), 속도 버튼 UI
- 관련 커밋: 83b711a (main, squash 머지), PR #2
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 9
- 브랜치: main (feature/pdf-export → PR #1 → squash 머지)
- 완료: PDF 내보내기 기능 + 브랜치 개발 워크플로우 확립
- 현재 상태: main 최신, 서버 실행 중
- 다음 할 일: 새 기능 논의
- 구현 내용:
  - frontend/app/print/[id]/page.tsx: 인쇄 최적화 전용 페이지 (A4, 요약+스크립트)
  - frontend/components/MainArea.tsx: done 상태에 PDF 버튼 추가
- 코드 리뷰 이슈 수정:
  - 테이블 구분자 행(| --- |) 필터링 추가
  - window.print() 트리거에 job.status === 'done' 조건 추가
- 브랜치 전략 확립: feature/* → PR → /code-review → 머지
- 관련 커밋: a22ba66 (main, squash 머지), PR #1
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 8
- 브랜치: main
- 완료: 회의 목록 카테고리/날짜 필터 기능
- 현재 상태: 서버 실행 중, 테스트 59/59 PASS
- 다음 할 일: 새 기능 논의
- 구현 내용:
  - backend/app/database.py: search_jobs()에 category_id, date_from, date_to 필터 추가 (SQLite DATE() 함수 사용)
  - backend/app/main.py: /api/meetings에 필터 쿼리 파라미터 추가
  - backend/tests/test_search_jobs.py: 카테고리 필터, 날짜 필터, 복합 필터 테스트 3개 추가
  - frontend/app/meetings/page.tsx: 카테고리 드롭다운 + 날짜 범위(from/to) 필터 UI, URL 쿼리 동기화, 필터 초기화 버튼
- 관련 커밋: 7cdd585
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 7
- 브랜치: main
- 완료: 파일 업로드 기능 E2E 테스트 완료
- 현재 상태: 전체 기능 정상, 서버 실행 중 (백엔드 8000, 프론트 3000)
- 다음 할 일: 새 기능 논의 or 배포
- E2E 테스트 결과:
  - txt 파일 업로드 → awaiting_edit 직진입 → TranscriptEditor 정상 렌더링 ✅
  - 화자 분리 (SPEAKER_00/01) + 타임스탬프 파싱 정상 ✅
  - 사이드바 "편집 대기 중" 뱃지 표시 ✅
  - 백엔드 테스트 56/56 PASS ✅
- 관련 커밋: 6e231ee (파일 업로드), ede4423 (PROGRESS 세션 6)
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 6
- 브랜치: main
- 완료: 파일 업로드 기능 (오디오/txt) + 코드 리뷰 버그 3개 수정
- 현재 상태: 서버 미실행 (코드만 수정), 모든 테스트 통과 (56/56)
- 구현 내용:
  - backend/app/main.py: POST /api/upload 엔드포인트 (오디오→STT파이프라인, txt→awaiting_edit 직진입), limit 상한 100, SSE 연결 해제 감지
  - backend/app/summarizer.py: self-referential 화자 매핑 필터링 버그 수정
  - backend/tests/test_upload.py: 업로드 테스트 4개 (56개 전체 통과)
  - frontend/components/RecordingZone.tsx: 녹음/파일업로드 탭 UI, 드래그앤드롭 + 클릭 업로드
- 관련 커밋: 6e231ee, e699d80
- 푸시 여부: origin/main 푸시 완료

## 2026-08-24 (작업 PC: 로컬) — 세션 5
- 브랜치: main
- 완료: 카테고리 시스템 E2E 테스트 + 버그 2개 수정
- 현재 상태: 서버 실행 중 (백엔드 8000, 프론트 3000), 모든 기능 정상
- 다음 할 일: 추가 테스트 또는 새 기능 논의
- 구현 내용:
  - Playwright로 UI E2E 검증 (RecordingZone 카테고리 드롭다운 5개, 설정 모달 3탭, 카테고리 인라인 편집)
  - `frontend/components/TranscriptEditor.tsx`: suggestedNames 버그 수정
    - 기존: speakers.json 이전 매핑이 이름 입력란에 자동 채워져 의도치 않게 적용됨
    - 수정: names 초기값 빈 문자열, suggestedNames는 placeholder 힌트로만 표시
  - `backend/app/notion_sync.py`: Notion 테이블 블록 구조 버그 수정
    - 기존: table_row children을 블록 최상위 children에 넣어 Notion API 422 오류
    - 수정: children을 table 오브젝트 내부로 이동 (`table.children`)
    - 영향: 설교요약 등 표가 포함된 카테고리 Notion 업데이트 정상 동작
  - `backend/tests/test_notion_sync.py`: 테이블 구조 변경에 맞게 테스트 수정
- 관련 커밋: be79908..2ff5450 (gitignore 포함)
- 푸시 여부: origin/main 푸시 완료 (https://github.com/jaerakson/meeting-jr)

## 2026-08-23 (작업 PC: 로컬) — 세션 4
- 브랜치: main
- 완료: 카테고리 시스템 전체 구현 (8개 Task, SDD 방식)
- 현재 상태: 서버 미실행 (코드만 수정), 모든 테스트 통과
- 다음 할 일: 서버 재시작 후 E2E 테스트
- 구현 내용:
  - `backend/app/categories.py`: 5개 기본 카테고리 (meeting/lecture/sermon/interview/brainstorm) + DEFAULT_PROMPTS
  - `backend/app/database.py`: categories 테이블 + seed, Job에 category_id 필드
  - `backend/app/main.py`: Category CRUD API (GET/POST/PATCH/DELETE/reset), record/finalize에 category_id 통합, run_summary 카테고리별 프롬프트 적용
  - `backend/app/notion_sync.py`: table/quote/numbered/bold 블록 지원, 카테고리 헤더 자동 삽입
  - `frontend/types/index.ts`: Category 인터페이스, Job에 category 필드 추가
  - `frontend/components/CategorySelect.tsx`: 카테고리 드롭다운 컴포넌트
  - `frontend/components/RecordingZone.tsx`: 카테고리 선택 + localStorage 저장
  - `frontend/components/TranscriptEditor.tsx`: 카테고리 선택 + finalize에 전달
  - `frontend/components/MainArea.tsx`: 카테고리 뱃지 + 재요약 카테고리 모달
  - `frontend/components/SettingsModal.tsx`: 일반/Claude/카테고리 3탭, 카테고리 CRUD UI
  - `backend/tests/`: 52개 전체 통과 (0.45s)
- QA 검증 결과:
  - 백엔드 테스트: 52/52 PASS
  - 프론트엔드 빌드: PASS (Next.js 15, static 5페이지)
  - 카테고리 API: 5개 카테고리, 전체 {script} 플레이스홀더 포함 확인
- 관련 커밋: 91c84ed..98e416c (Task 1~7)
- 푸시 여부: 미푸시 (git remote 미설정)

## 2026-08-23 (작업 PC: 로컬) — 세션 3
- 브랜치: main
- 완료: Claude 모델/프롬프트 설정 기능 구현 + 화자 매핑 버그 2개 수정
- 현재 상태: 서버 미실행 (코드만 수정), 기능 정상
- 다음 할 일: 서버 재시작 후 테스트
- 구현 내용:
  - `backend/app/settings_manager.py`: `CLAUDE_MODEL`, `CLAUDE_PROMPT` 키 추가
  - `backend/app/summarizer.py`: `DEFAULT_PROMPT` 상수 추가, `generate_summary(model, prompt_template)` 파라미터 추가
  - `backend/app/main.py`: `GET /api/settings/claude-model`, `GET /api/settings/claude-prompt` 엔드포인트 추가, `run_summary`에서 설정값 읽어 모델/프롬프트 전달
  - `backend/app/main.py`: `_save_speakers()` 수정 — key==value 무의미한 매핑(UNKNOWN→UNKNOWN 등) 저장 안 함
  - `frontend/components/SettingsModal.tsx`: Claude 모델 선택 드롭다운 + 프롬프트 textarea (10행, 초기화 버튼) 추가
  - `frontend/components/MainArea.tsx`: `handleAwaitingEdit` 수정 — transcript 없는 SSE fallback 시 editData 설정 안 함 (페이지 새로고침 시 빈 TranscriptEditor 방지)
  - `backend/speakers.json`: "UNKNOWN": "UNKNOWN" 오염 항목 제거
  - `backend/tests/test_model_prompt_setting.py`: 4개 테스트 추가
- 버그 수정 내역:
  1. 페이지 새로고침 시 awaiting_edit 상태에서 빈 TranscriptEditor 표시 → transcript 빈 경우 editData 미설정으로 수정
  2. speakers.json에 "UNKNOWN": "UNKNOWN" 같은 self-referential 항목 축적 → 필터링 추가
- 관련 커밋: 4118915.. (미커밋)
- 푸시 여부: 미푸시 (git remote 미설정)

## 2026-08-23 (작업 PC: 로컬) — 세션 2
- 브랜치: main
- 완료: Notion UX 개선 + 기본 회의 제목 설정 + 문서 전체 업데이트
- 현재 상태: 서버 실행 중 (백엔드 8000, 프론트 3000), 모든 기능 정상
- 다음 할 일: 테스트 후 추가 기능 논의
- 구현 내용:
  - `backend/app/main.py`: Notion 내보내기 제목에 `[회의날짜 HH:MM]` 접두 (created_at KST 변환)
  - `backend/app/main.py`: Notion 페이지 상단에 `📤 업로드 일시: YYYY-MM-DD HH:MM` 자동 삽입
  - `backend/app/main.py`: 녹음 시작 시 기본 제목 설정값 사용 (미설정 시 '회의록')
  - `backend/app/main.py`: `GET /api/settings/default-title` 엔드포인트 추가
  - `backend/app/settings_manager.py`: `DEFAULT_MEETING_TITLE` 키 추가
  - `frontend/components/MainArea.tsx`: Notion 버튼 로딩 피드백 (스피너 + 텍스트 변경 + disabled)
  - `frontend/components/SettingsModal.tsx`: 기본 회의 제목 입력 필드 추가 (하단 공통 저장 통합)
  - 문서: SKILL.md TeamCreate에 product-manager 추가, DEVGUIDE.md/README.md 전체 업데이트
- 관련 커밋: 980c6fb..4118915 (5개)
- 푸시 여부: 미푸시 (git remote 미설정)

## 2026-08-23 (작업 PC: 로컬)
- 브랜치: main
- 완료: 회의 목록 페이지 (/meetings) 전체 구현 + QA 완료
- 현재 상태: 실행 준비 완료 (6개 커밋, 모든 테스트 통과)
- 다음 할 일:
  1. 터미널1: cd backend && /opt/homebrew/bin/python3.11 -m uvicorn app.main:app --reload --port 8000
  2. 터미널2: cd frontend && npm run dev
  3. 브라우저: http://localhost:3000 → 사이드바 "전체 목록 보기" 클릭 → /meetings
- 구현 내용:
  - backend/app/database.py: search_jobs() 함수 추가
  - backend/app/main.py: GET /api/meetings?q=&page=&limit=12 엔드포인트
  - backend/tests/: pytest 8개 테스트 (search_jobs 5개 + endpoint 3개)
  - frontend/components/Pagination.tsx: 페이지 번호 + ellipsis 컴포넌트
  - frontend/components/MeetingCard.tsx: 카드 (제목/날짜/참석자/요약/액션수/뱃지)
  - frontend/app/meetings/page.tsx: 검색+그리드+페이지네이션 페이지
  - frontend/components/Sidebar.tsx: "전체 목록 보기" 링크 추가
  - frontend/app/page.tsx: ?job= 파라미터 자동 선택 처리
- 머지 후 개선 사항 (Minor, 기능 영향 없음):
  - test_search_jobs.py: 미사용 import tempfile 제거
  - /meetings 마운트 시 이중 fetch 최적화
  - Pagination aria-label 추가 (접근성)
  - limit 파라미터 상한 검증 추가
- 관련 커밋: c857701..5ffbf02 (6개)
- 푸시 여부: 미푸시 (git remote 미설정)


