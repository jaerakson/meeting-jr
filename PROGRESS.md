## 2026-08-22 (에이전트 팀 자동 개발 완료)
- 브랜치: main (git 미사용)
- 완료: Meeting Junior 전체 앱 자동 개발 + QA 완료
- 현재 상태: 실행 준비 완료
- 다음 할 일:
  1. backend/.env 확인 (HF_TOKEN 이미 설정됨)
  2. cd frontend && npm install
  3. cd backend && pip install -r requirements.txt
  4. 터미널1: cd backend && python -m uvicorn app.main:app --reload --port 8000
  5. 터미널2: cd frontend && npm run dev
  6. 브라우저: http://localhost:3000
- 막힌 점/주의: PyAnnote 첫 실행 시 모델 다운로드 약 1GB (수 분 소요)
- 관련 파일: backend/, frontend/, QA_REPORT.md
- 푸시 여부: 미푸시
