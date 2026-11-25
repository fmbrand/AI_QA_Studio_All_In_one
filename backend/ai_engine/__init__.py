"""AI engine: document parsing, chunking, embeddings, LLM providers, prompts and output grounding.

This package has no database or web dependencies. The app's services call it and persist the results,
so prompt logic never lives in route handlers and every piece here is unit-testable on its own.
"""
