# 카카오톡 알림 연동 설계

> 씨윈의 모든 알림을 카카오톡 "나에게 보내기"로 핸드폰에 전달한다.
> 텔레그램 제거 후 대체 수단. 무료, 사업자 등록 불필요.

## 배경

- 텔레그램 코드 전체 삭제 완료 (2026-06-17)
- 씨윈에서 핸드폰으로 알림을 보낼 수단이 없음
- 카카오톡 "나에게 보내기" API로 대체

## 구조

```
[씨윈 알림 이벤트]
  notification-created (side-effect)
       |
       v
[kakao-talk.ts] ---fetch()--> https://kapi.kakao.com/v2/api/talk/memo/send
       |                              |
       v                              v
[kakao-token-store.ts]          [카카오 서버]
  (safeStorage 암호화)                |
                                     v
                              [핸드폰 카톡 푸시]
```

## 파일 구조

```
src/main/notifications/
  windows-toast.ts       (기존 - 로컬 알림)
  kakao-talk.ts          (신규 - 카톡 나에게 보내기)
  kakao-token-store.ts   (신규 - 토큰 암호화 저장/자동 갱신)
```

## 상세 설계

### 1. kakao-token-store.ts

Electron safeStorage로 암호화 저장 (기존 텔레그램 토큰과 동일 패턴).

**저장 항목:**
- `access_token` — API 호출용 (만료: 6시간)
- `refresh_token` — access_token 갱신용 (만료: 2개월)
- `rest_api_key` — 카카오 앱 REST API 키
- `token_expires_at` — access_token 만료 시각 (ISO string)

**저장 위치:** `%APPDATA%/cmux-win/kakao-tokens.enc`

**함수:**
```typescript
saveTokens(appDataDir: string, tokens: KakaoTokens): boolean
loadTokens(appDataDir: string): KakaoTokens | null
deleteTokens(appDataDir: string): void
```

### 2. kakao-talk.ts

**KakaoTalkService 클래스:**

```typescript
class KakaoTalkService {
  constructor(store: AppStateStore)

  // 토큰 설정 (초기화 시 + 설정 변경 시)
  configure(tokens: KakaoTokens): void

  // 알림 전송 (notification-created 이벤트에서 호출)
  sendNotification(title: string, body: string, meta?: {
    workspaceId?: string
    surfaceId?: string
  }): Promise<void>

  // 토큰 자동 갱신 (access_token 만료 시)
  private refreshAccessToken(): Promise<void>
}
```

**API 호출:**
```
POST https://kapi.kakao.com/v2/api/talk/memo/send
Authorization: Bearer {ACCESS_TOKEN}
Content-Type: application/x-www-form-urlencoded

template_object={
  "object_type": "text",
  "text": "메시지 내용",
  "link": { "web_url": "https://github.com/manaflow-ai/cmux-win" }
}
```

**토큰 자동 갱신:**
```
POST https://kauth.kakao.com/oauth/token
grant_type=refresh_token
client_id={REST_API_KEY}
refresh_token={REFRESH_TOKEN}
```
- access_token 만료 시 자동 호출
- refresh_token 만료 1개월 전이면 새 refresh_token도 발급됨
- 갱신된 토큰은 즉시 kakao-token-store에 저장

**디바운스:**
- 동일 워크스페이스에서 3초 이내 중복 알림 무시 (기존 텔레그램과 동일)

**에러 처리:**
- 401 Unauthorized → 토큰 갱신 시도 → 재실패 시 로그 경고
- 네트워크 에러 → 3회 재시도 (1초, 2초, 4초 간격)
- 토큰 없음 → 무시 (설정 전에는 알림 안 감)

### 3. index.ts 연동

기존 `notification-created` 이벤트 핸들러에 카카오톡 호출 추가:

```typescript
// 기존
showToast(title, body);

// 추가
kakaoTalk
  .sendNotification(title, body, { workspaceId, surfaceId })
  .catch((err) => console.warn('[kakao] send failed:', err.message));
```

**초기화 (app.whenReady):**
```typescript
const kakaoTokens = loadTokens(app.getPath('userData'));
if (kakaoTokens) {
  kakaoTalk.configure(kakaoTokens);
}
```

### 4. 소켓 API (notification.ts 핸들러)

토큰 설정/관리용 소켓 메서드:

```
kakao.set_tokens    — access_token + refresh_token + rest_api_key 저장
kakao.get_status    — 토큰 존재 여부 + 만료 시각
kakao.delete_tokens — 토큰 삭제
kakao.test          — 테스트 메시지 발송
```

### 5. 메시지 형식

```
[cmux-win] {title}

{body}

{워크스페이스명} | {timestamp}
```

예시:
```
[cmux-win] Claude needs input

What should I do next?

My-Sermon-Editor | 16:30
```

### 6. Context Watchdog 연동 (후속 작업)

컨텍스트 리밋 감지 시 카카오톡으로 알림:
- 컴팩션 감지 → "[cmux-win] 마스터 컨텍스트 임계 도달"
- /clear 완료 → "[cmux-win] 마스터 컨텍스트 초기화 완료"

## 초기 설정 절차 (1회)

1. developers.kakao.com 접속 → 앱 등록 → REST API 키 발급
2. 카카오 로그인 활성화 + 동의항목에서 "카카오톡 메시지 전송" 활성화
3. Redirect URI 등록: `http://localhost:3000/callback`
4. 브라우저에서 인가코드 발급 URL 접속 → 카카오 로그인 → 인가코드 획득
5. 인가코드로 토큰 교환 (access_token + refresh_token)
6. 씨윈 소켓 API `kakao.set_tokens`로 토큰 저장
7. `kakao.test`로 테스트 메시지 발송 확인

## 의존성

- 외부 라이브러리 없음 (Node.js 내장 fetch 사용)
- Electron safeStorage (기존)

## 비용

- 무료 (카카오톡 나에게 보내기 API)
- 앱 검수 불필요 (개인 사용)
