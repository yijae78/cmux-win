"""Analysis Layer: 8-stage NLP pipeline implementing 56 analysis techniques.

Stages:
    Stage 1 - Preprocessing:     Kiwi (ko) + spaCy (en) tokenization
    Stage 2 - Feature Extraction: SBERT embeddings, TF-IDF, NER, KeyBERT
    Stage 3 - Article Analysis:   Sentiment, emotion, STEEPS classification
    Stage 4 - Aggregation:        BERTopic, HDBSCAN, NMF/LDA, community
    Stage 5 - Time Series:        STL, burst, changepoint, Prophet, wavelet
    Stage 6 - Cross Analysis:     Granger, PCMCI, co-occurrence, cross-lingual
    Stage 7 - Signal Classification: 5-Layer (L1-L5) + novelty detection
    Stage 8 - Data Output:        Parquet merge + SQLite FTS5/vec index

Pipeline orchestration: pipeline.py
Model management: models/ (singleton pattern, memory tracking)
"""
