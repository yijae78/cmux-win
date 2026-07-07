"""NLP Model Management: Singleton loading with memory tracking.

Provides centralized model lifecycle management to enforce:
    - Kiwi MUST be singleton (prevents +125 MB leak per reload)
    - SBERT shared between KeyBERT and BERTopic
    - Sequential load/unload with gc.collect() between stages
    - Memory monitoring against 20GB budget

Modules:
    model_registry  - Singleton model loader with memory tracking
    kiwi_singleton  - Kiwi singleton instance (Step 2 R2: mandatory)
"""
