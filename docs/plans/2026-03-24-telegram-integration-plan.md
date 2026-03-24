# 텔레그램 연동 구현 계획

> **작성일**: 2026-03-24
> **상태**: 구현 완료 (커밋 대기)

---

## 아키텍처

```
Electron Main Process
  ├── TelegramBotService (grammY, long polling)
  │     ├── Outbound: notification-created → sendMessage + InlineKeyboard
  │     └── Inbound: /status, /approve, /reject, /send, /agents, /help
  ├── SideEffectsMiddleware → showToast() + telegramBot.sendNotification()
  └── telegram-token-store.ts → safeStorage 암호화
```

## 성찰 반영 사항 (13건)

| # | 결함 | 심각도 | 수정 |
|---|------|--------|------|
| C1 | bot.catch() 미설정 → 앱 크래시 | CRITICAL | bot.catch()에서 모든 에러 흡수 |
| C2 | 다중 인스턴스 409 Conflict | CRITICAL | app.requestSingleInstanceLock() |
| C3 | bot.stop() 미호출 → 앱 hang | CRITICAL | before-quit에서 telegramBot.stop() |
| C4 | Bot Token 평문 저장 | CRITICAL | safeStorage 암호화, SettingsState에 미저장 |
| H1 | Side-effect 동기 → async 호출 | HIGH | .catch() fire-and-forget |
| H2 | Rate Limiting 미처리 | HIGH | @grammyjs/auto-retry + 3초 디바운스 |
| H3 | HTML 이스케이프 누락 | HIGH | escapeHtml() — &, <, > |
| H4 | 일반 텍스트 자동 전달 위험 | HIGH | 명시적 명령만, 일반 텍스트 차단 |
| H5 | electron-vite 번들링 | HIGH | grammy를 external에 추가 |
| H6 | 설정 변경 시 봇 재시작 순서 | HIGH | await stop → start 직렬화 |
| M1 | InlineKeyboard 콜백 만료 | MEDIUM | 타임스탬프 5분 체크 |
| M2 | 에이전트 상태 경쟁 조건 | MEDIUM | 버튼 클릭 시 상태 재검증 |
| M3 | 네트워크 에러 로그 폭주 | MEDIUM | 카운터 기반 로그 억제 |

## 파일 목록

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `src/main/notifications/telegram-bot.ts` | 신규 | TelegramBotService 핵심 모듈 |
| `src/main/notifications/telegram-token-store.ts` | 신규 | safeStorage 토큰 암호화 |
| `tests/unit/notifications/telegram-bot.test.ts` | 신규 | 12개 유닛 테스트 |
| `src/shared/types.ts` | 수정 | SettingsState.telegram 추가 |
| `src/shared/constants.ts` | 수정 | DEFAULT_SETTINGS.telegram 기본값 |
| `src/main/index.ts` | 수정 | 단일인스턴스, 봇 초기화/종료, side-effect 연결 |
| `src/main/socket/handlers/notification.ts` | 수정 | telegram.* RPC 4개 추가 |
| `electron-vite.config.ts` | 수정 | grammy external 추가 |
| `package.json` | 수정 | grammy, @grammyjs/auto-retry 의존성 |

## Telegram 명령어

| 명령 | 동작 |
|------|------|
| `/status` | 워크스페이스 + 에이전트 상태 |
| `/agents` | 에이전트 목록 |
| `/approve` | needs_input 에이전트에 y 전송 |
| `/reject` | needs_input 에이전트에 n 전송 |
| `/send <text>` | 확인 후 에이전트에 텍스트 전송 |
| `/help` | 도움말 |
| [인라인 버튼] | 승인/거부/상태 (5분 만료) |
| 일반 텍스트 | 차단 + 안내 메시지 |

## 설정 방법

1. @BotFather에서 봇 생성 → 토큰 획득
2. Socket API `telegram.set_token` 호출로 토큰 저장 (safeStorage 암호화)
3. `settings.update` → `{ telegram: { enabled: true, chatId: "..." } }`
4. 봇이 자동 시작, 알림 전달 시작

## 테스트 결과

- 텔레그램 테스트: 12 passed
- 전체: 407 passed, 9 failed (기존 동일: tmux-shim 3 + history-db 6)
- 회귀 없음
