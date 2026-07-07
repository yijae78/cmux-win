# 시나리오 1 — 코드 리뷰 종합 보고서

**대상**: EnvironmentScan-system-main-v4 (환경 스캔 시스템)
**파일**: `monitor.py` (745줄), `launch_monitor.py` (37줄)
**분석일**: 2026-06-17
**참여 워커**: Worker1(Claude), Worker2(AGY), Worker3(Codex)

---

## Executive Summary

3개 워커의 독립적 분석을 종합한 결과, EnvironmentScan 대시보드는 **프로토타입으로서 기능적으로 완성**되어 있으나, 프로덕션 수준의 **보안·성능·유지보수성**에서 개선이 필요합니다.

| 평가 항목 | 점수 | 요약 |
|-----------|------|------|
| 기능 완성도 | 7/10 | 실시간 ETA, SVG 차트, 자동 갱신 등 핵심 기능 구현 완료 |
| 코드 품질 | 6/10 | 단일 파일 모놀리스, 200줄+ 함수, 변수명 개선 필요 |
| 보안 | 5/10 | XSS 위험, 네트워크 노출, 입력값 미검증 |
| 성능 | 5.5/10 | 매 렌더링마다 파일시스템 스캔, blocking sleep |
| 에러 핸들링 | 4.5/10 | 포괄적 예외 묵살, 디버깅 불가 |
| 아키텍처 | 5.5/10 | 데이터/로직/렌더링 미분리, 테스트 불가 구조 |
| **종합** | **5.6/10** | 프로토타입 OK, 프로덕션 배포 전 리팩토링 필수 |

---

## 1. 3개 워커 공통 지적 사항 (Critical — 전원 일치)

### 1.1 XSS/HTML 인젝션 위험
- **Worker1**: CSS/HTML 문자열에 외부 데이터 직접 삽입 (`unsafe_allow_html=True`)
- **Worker2**: JSON 파일 값이 HTML에 포매팅되어 직접 렌더링 — XSS 공격 가능
- **Worker3**: `html.escape()` 없이 signal titles, category labels 등 삽입

> **권장**: 모든 데이터 파생 값에 `html.escape(str(value))` 적용

### 1.2 `time.sleep()` Blocking 문제
- **Worker1**: `time.sleep(30)` + `st.rerun()` — UI 무응답 유발
- **Worker2**: 메인 스레드 차단형 대기로 반응성 저해
- **Worker3**: 세션 워커를 5~30초 점유 → 다중 사용자 시 심각

> **권장**: `st_autorefresh` 또는 타임스탬프 기반 rerun으로 교체

### 1.3 포괄적 예외 묵살 (`except Exception: return None`)
- **Worker1**: `_j()` 함수의 모든 에러 묵살 → 디버깅 불가
- **Worker2**: `try-except-pass` 구문으로 원인 추적 불가
- **Worker3**: FileNotFoundError, JSONDecodeError 등 구분 없이 동일 처리

> **권장**: 좁은 범위 예외 캐치 + 로깅 추가

---

## 2. 2개 워커 이상 지적 사항 (High)

### 2.1 매 렌더링마다 파일시스템 전체 스캔
- **Worker2**: `st.session_state`/`st.cache_data` 미활용 → 불필요한 디스크 I/O
- **Worker3**: 파일 glob + stat 반복 → 로그 축적 시 성능 저하

> **권장**: `st.cache_data`로 `(path, mtime)` 기반 캐싱

### 2.2 단일 파일 모놀리스 구조
- **Worker1**: 데이터 로딩, 비즈니스 로직, 렌더링이 모두 한 파일에 혼재
- **Worker3**: 데이터 접근/상태 도출/렌더링 3계층 분리 권장

> **권장**: data_loader.py / view_model.py / renderer.py 분리

### 2.3 타입 안전성 부족
- **Worker1**: `_j()` → `dict | None` 반환, 내부 구조 미검증
- **Worker3**: `TypedDict` 또는 dataclass로 JSON 스키마 명시 필요

---

## 3. 개별 워커 고유 발견 사항

### Worker1(Claude) 고유
- CSS 키프레임 중복 정의 (CSS vs CSS_ANIM 상수)
- Three Horizons 데이터 로딩 시 `today` vs `data_date` 불일치
- `launch_monitor`의 stdout/stderr 소거로 디버깅 불가
- **종합 점수**: 6.0/10

### Worker2(AGY) 고유
- `window.parent.document` 접근 — iframe 샌드박스 우회 우려 (ZOOM 스크립트)
- 명시적 바인딩 주소 부재 → 네트워크 노출 위험
- Streamlit 상태 관리 아키텍처(`st.session_state`) 미준수
- 강한 파일시스템 종속성과 도메인 레이어 결합

### Worker3(Codex) 고유
- `_load()` 내부 parsed dict 직접 변이 (mutation) → 캐싱 시 사이드이펙트
- 날짜 처리 시 historical vs current-day 데이터 혼합 가능
- 런처의 고정 포트(8504) 충돌 가능성
- `KeyboardInterrupt` 시 자식 프로세스 미종료

---

## 4. 주요 버그 목록

| # | 심각도 | 파일 | 내용 |
|---|--------|------|------|
| 1 | High | monitor.py | XSS — JSON 값이 HTML에 미이스케이프 삽입 |
| 2 | High | monitor.py | `time.sleep(30)` blocking → UI 무응답 |
| 3 | High | monitor.py | `_j()` 포괄 예외 묵살 → 오류 원인 추적 불가 |
| 4 | Medium | monitor.py | Three Horizons `today` vs `data_date` 불일치 |
| 5 | Medium | monitor.py | CSS 키프레임 중복 정의 |
| 6 | Medium | monitor.py | 매 렌더링마다 파일시스템 glob+stat 반복 |
| 7 | Medium | launch_monitor.py | stdout/stderr 소거 → 실패 시 디버깅 불가 |
| 8 | Medium | launch_monitor.py | 고정 포트 충돌 + 준비 상태 미확인 |
| 9 | Low | monitor.py | `wf_validation`, `cross_wf` 로드 후 미사용 |
| 10 | Low | launch_monitor.py | 프로세스 종료 시 자식 프로세스 누수 |

---

## 5. 개선 우선순위

### Phase 1 — 즉시 (보안·안정성)
1. `html.escape()` 적용 (XSS 차단)
2. `time.sleep()` → `st_autorefresh` 교체
3. `_j()` 예외 범위 축소 + 로깅

### Phase 2 — 단기 (구조·성능)
4. `st.cache_data` 도입 (파일 I/O 감소)
5. `_load()` 함수 분할 (175줄 → 3~4개 함수)
6. Three Horizons 날짜 정합성 수정

### Phase 3 — 중기 (아키텍처)
7. 3계층 분리 (data / view_model / render)
8. TypedDict 도입으로 타입 안전성 확보
9. 런처 개선 (준비 상태 폴링, 에러 출력)

---

## 6. 워커별 원본 보고서

| 워커 | 파일 | 크기 |
|------|------|------|
| Worker1(Claude) | `worker1_code_analysis.md` | 11,807 bytes |
| Worker2(AGY) | `worker2_security_review.md` | 7,114 bytes |
| Worker3(Codex) | `worker3_tech_review.md` | 8,798 bytes |

---

*본 보고서는 Javis Fleet 시나리오 1 테스트의 일환으로 생성되었습니다.*
*마스터가 3개 워커의 독립 분석을 종합하여 작성.*
