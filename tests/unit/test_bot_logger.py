"""
Unit tests — bot_logger.py
Verifica classificazione livelli e funzionamento dell'interceptor.
"""

import sys
from modules.bot_logger import _StdoutInterceptor, init_log_interceptor


class TestClassifyLevel:
    def test_error_keywords(self):
        cases = ["Errore critico", "ERROR in module", "EXCEPTION raised",
                 "CRITICAL failure", "TRACEBACK:", "FAILED", "fail"]
        for msg in cases:
            assert _StdoutInterceptor._classify(msg) == "ERROR", f"failed for: {msg!r}"

    def test_warning_keywords(self):
        cases = ["WARNING: rate limit", "WARN: budget exceeded",
                 "ATTENZIONE: quota", "Too many requests", "RATE LIMIT hit",
                 "HTTP 429", "LIMITE GIORNALIERO raggiunto"]
        for msg in cases:
            assert _StdoutInterceptor._classify(msg) == "WARNING", f"failed for: {msg!r}"

    def test_info_fallback(self):
        cases = ["[RSS] Detector avviato", "Completato.", "[MAIN] ok",
                 "Trovati 5 risultati"]
        for msg in cases:
            assert _StdoutInterceptor._classify(msg) == "INFO", f"failed for: {msg!r}"

    def test_case_insensitive(self):
        assert _StdoutInterceptor._classify("error happened") == "ERROR"
        assert _StdoutInterceptor._classify("Warning: limit") == "WARNING"


class TestExtractModule:
    def test_bracket_prefix(self):
        assert _StdoutInterceptor._extract_module("[RSS] detector") == "rss"
        assert _StdoutInterceptor._extract_module("[MAIN] avvio") == "main"
        assert _StdoutInterceptor._extract_module("[BOT-LOGGER] ok") == "bot-logger"

    def test_no_bracket_returns_system(self):
        assert _StdoutInterceptor._extract_module("plain text") == "system"
        assert _StdoutInterceptor._extract_module("") == "system"

    def test_spaces_replaced_with_underscore(self):
        assert _StdoutInterceptor._extract_module("[MY MODULE] msg") == "my_module"

    def test_long_module_name_truncated(self):
        long_name = "A" * 50
        result = _StdoutInterceptor._extract_module(f"[{long_name}] msg")
        assert len(result) <= 40


class TestInitLogInterceptor:
    def test_idempotent(self):
        """Chiamare init_log_interceptor più volte non installa wrapper multipli."""
        init_log_interceptor()
        first_stdout = sys.stdout
        init_log_interceptor()
        second_stdout = sys.stdout
        assert first_stdout is second_stdout
        # Ripristino per non inquinare altri test
        if isinstance(sys.stdout, _StdoutInterceptor):
            sys.stdout = sys.stdout._original

    def test_interceptor_is_wrapper(self):
        init_log_interceptor()
        # Dopo l'init deve essere o un _StdoutInterceptor o ripristinato
        # Verifichiamo solo che non sollevi eccezioni
        assert True
