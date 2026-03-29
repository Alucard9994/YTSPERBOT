"""
YTSPERBOT - Bot Logger
Intercetta sys.stdout per catturare tutti i print() del bot e salvarli
nel DB (tabella bot_logs) con classificazione automatica del livello.
"""

import sys
import re


class _StdoutInterceptor:
    """Wrapper di sys.stdout che duplica l'output sul DB."""

    def __init__(self, original):
        self._original = original
        self._buf = ""

    def write(self, text: str):
        self._original.write(text)
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.rstrip()
            if len(line) > 3:
                self._save(line)

    def flush(self):
        self._original.flush()

    def fileno(self):
        return self._original.fileno()

    # Forward every other attribute access to the original stream
    def __getattr__(self, name):
        return getattr(self._original, name)

    # ── classificazione livello ───────────────────────────────────────
    @staticmethod
    def _classify(line: str) -> str:
        upper = line.upper()
        if any(x in upper for x in (
            "ERRORE", "ERROR", "EXCEPTION", "CRITICAL", "CRITICO",
            "TRACEBACK", "FAILED", "FAIL",
        )):
            return "ERROR"
        if any(x in upper for x in (
            "WARNING", "WARN", "ATTENZIONE", "LIMITE GIORNALIERO",
            "BUDGET", "QUOTA", "TOO MANY", "RATE LIMIT", "429",
        )):
            return "WARNING"
        return "INFO"

    @staticmethod
    def _extract_module(line: str) -> str:
        m = re.match(r"\[([^\]]{1,40})\]", line)
        if m:
            return m.group(1).lower().replace(" ", "_")
        return "system"

    def _save(self, line: str):
        try:
            from modules.database import save_bot_log
            level = self._classify(line)
            module = self._extract_module(line)
            save_bot_log(level, line, module)
        except Exception:
            pass  # non propagare mai errori dal logger


_interceptor_installed = False


def init_log_interceptor():
    """
    Installa l'interceptor su sys.stdout.
    Idempotente: chiamare più volte non crea wrapper multipli.
    """
    global _interceptor_installed
    if _interceptor_installed:
        return
    if isinstance(sys.stdout, _StdoutInterceptor):
        return
    sys.stdout = _StdoutInterceptor(sys.stdout)
    _interceptor_installed = True
    print("[BOT-LOGGER] Log interceptor attivato.")
