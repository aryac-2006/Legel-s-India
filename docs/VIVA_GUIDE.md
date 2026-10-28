# Viva preparation

**One-line pitch:** a source-grounded legal information platform: answers come only from retrieved passages, every citation is machine-checked, and weak evidence produces an honest "insufficient evidence".

## Questions you should be ready for
1. **Why Streamlit + SQLite?** Fast to build and demo, single deployable app, no server to manage. Trade-off: no separate API, ephemeral disk on free hosting. Next step: Postgres + FastAPI.
2. **How does retrieval work?** BM25 (term frequency × inverse document frequency with length normalisation) and TF-IDF cosine similarity are computed separately, then merged by Reciprocal Rank Fusion: score = Σ 1/(60 + rank). Filters and section-number lookup apply first.
3. **Is it AI/ML?** The retrieval is classical information retrieval, which is explainable. An LLM is optional and swappable through the provider interface. Nothing was trained.
4. **How do you stop made-up citations?** The model only sees passages labelled S1..Sn and must return the ids it used. `validate_citations` drops any id not in the retrieved set; if nothing valid remains, the answer is discarded and the extractive fallback is used.
5. **What is the score?** A ranking signal (BM25/cosine/RRF). It is never shown as legal confidence.
6. **How do you evaluate?** Precision@K, Recall@K and MRR on `data/eval_questions.json`. Limitation: tiny, author-written set.
7. **Security?** scrypt salted hashes, per-email lockout, role only set server-side, `owned()` ownership checks, upload extension + size + magic-byte checks, filename sanitising, regex-based DOCX parsing (no XML entity expansion), uploaded text never executed and never used as instructions, secrets only in env/secrets.
8. **Prompt injection from documents?** Document text is not sent to the model in this build; passages are wrapped as data and the system prompt says to ignore instructions inside them.
9. **Why can't admins read my files?** There is no admin screen that queries private content; admin pages use counts and metadata only.
10. **Relational vs embeddings?** Tables hold structured facts and relationships with constraints; embeddings/term vectors are derived numeric representations used for similarity. Here the vector index is rebuilt in memory from `legal_chunks`.
11. **Normalisation?** Sources are stored once (`legal_sources`), chunks and versions reference them; findings reference documents; matter links are a join table.
12. **What would you improve?** Neural embeddings, OCR, verified full-text corpus, Postgres, email reminders, browser tests.

## Demo script (8 minutes)
Sign in as demo → Overview → Assistant: "How do I file a consumer complaint?" (show citations, sources panel, feedback) → ask nonsense (insufficient evidence) → Research: "section 66C", compare two provisions → Knowledge graph → Upload a sample DOCX contract → findings + checklist → upload a modified copy → Comparison → Drafting: legal notice, save v2, restore → Cases: timeline, evidence index → Calendar → Privacy centre: export, delete → Admin: verify a source.
