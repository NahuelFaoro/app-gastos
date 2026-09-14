"""Entrada del ejecutable: arranque habitual o diagnóstico con datos temporales."""
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path


def run():
    if len(sys.argv) == 3 and sys.argv[1] in ("--self-test", "--ocr-self-test"):
        from scripts.check_app import main as check
        with Path(sys.argv[2]).open("w", encoding="utf-8") as log:
            with redirect_stdout(log), redirect_stderr(log):
                if sys.argv[1] == "--ocr-self-test":
                    from scripts.check_packaged_ocr import main as check_ocr
                    return check_ocr()
                return check()
    from main import main
    main()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
