"""Cross-layer shared utilities.

Provides common infrastructure used across crawling, analysis, and storage:
    - Structured JSON logging with per-module configuration
    - YAML configuration loading and validation
    - Retry decorators with exponential backoff
    - Custom exception hierarchy
    - Circuit Breaker pattern implementation
    - Memory monitoring and gc.collect() triggers

Modules:
    logging_config  - Structured JSON logging setup
    config_loader   - YAML configuration loading + validation
    error_handler   - Retry decorators, exception hierarchy, Circuit Breaker
    memory_monitor  - RSS memory tracking + gc.collect() triggers
"""
