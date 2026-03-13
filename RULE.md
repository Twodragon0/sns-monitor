# Cursor Rules

AI가 이 저장소에서 작업할 때 참고하는 규칙입니다.

- **전체 맥락:** [CLAUDE.md](./CLAUDE.md) — 프로젝트 개요, 아키텍처, API, 보안 요구사항
- **Cursor 규칙:** [.cursor/rules/](./.cursor/rules/) — 파일별/전역 규칙
  - `project-context.mdc` — 항상 적용 (프로젝트 개요, 보안)
  - `backend-python.mdc` — `backend/**/*.py`, `crawlers/**/*.py`
  - `frontend-react.mdc` — `frontend/**/*.jsx`, `frontend/**/*.tsx`, `frontend/**/*.js`, `frontend/**/*.ts`

수정 시 규칙은 짧게(50줄 이내), 한 규칙당 한 관심사, 구체적 예시를 포함하세요.
