# Scenario 4 — RSI Score Tracking

## RSI 점수 추적표

| 라운드 | 테스트 수 | 통과 | 실패 | 통과율 | 커버리지 | 변화 |
|--------|----------|------|------|--------|---------|------|
| Baseline | 37 | 37 | 0 | 100% | 77% | — |
| Round 1 (cli+config) | 57 | 57 | 0 | 100% | 88% | +11% |
| Round 2 (detector+orch) | 84 | 84 | 0 | 100% | 95% | +7% |
| Final (executor+edge) | 91 | 91 | 0 | 100% | 96% | +1% |

## 단조 증가 검증
```
77% < 88% < 95% < 96%  ✅ Monotonically increasing
```

## Phase 5 실전 검증
- Fleet 8-pane 감지: ✅ 
- DEAD pane 복구 시도: ✅ (브라우저 pane → 정상 실패)
- JSONL 이벤트 로그: ✅ (15 entries in events_phase5.jsonl)
- Worker 상태 분류 정확도:
  - LIVE: %0(Master), %2(W1), %3(W2), %9(W5)
  - IDLE: %1(CSO), %4(W3), %8(W4)
  - DEAD: %7(Dashboard — 브라우저, 정상)

## RSI 라운드별 개선 내역

### Round 1 — CLI + Config 테스트
- `test_cli.py` 신규: main() dispatch, help, start/status/stop, __main__
- `test_config.py` 신규: env var overrides, YAML loading, load_config integration
- cli.py: 0% → 95%, config.py: 24% → 95%

### Round 2 — Detector + Orchestrator 심화
- `test_detector.py` 확장: detect_one, detect_all, _update_hash, _last_active_time, _stuck_since, _list_panes, stuck 경로
- `test_orchestrator.py` 확장: _format_cycle_summary, _execute_and_log, OSError 처리, start/stop lifecycle
- detector.py: 52% → 99%, orchestrator.py: 69% → 81%

### Round 3 — Executor Edge Cases + Integration Fix
- `test_executor.py` 확장: _send_keys timeout/FileNotFoundError/nonzero RC, retry failure, restart CLI launch failure, escalate failure
- `__main__.py` 테스트 추가
- cmux-win 실전 호환성 수정: tmux shim 해결, UTF-8 인코딩, cmux-win list-panes 포맷 파싱
- executor.py: 81% → 96%, __main__.py: 0% → 100%
