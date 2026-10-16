"""Entry point. Native import test runs before the GUI is imported."""
import sys

def main():
    if '--self-test' in sys.argv:
        try:
            import os, tempfile
            from pathlib import Path
            Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir()), 'pt2vhf-selftest-argv.txt').write_text(repr(sys.argv), encoding='utf-8')
        except BaseException:
            pass
    if len(sys.argv) >= 3 and sys.argv[1] == '--self-test':
        from sat_tool.diagnostics import run_self_test
        return run_self_test(sys.argv[2], sys.argv[3] if len(sys.argv) >= 4 else '')
    from sat_tool.crash_diagnostics import (install_diagnostics, report_exception,
                                             clean_shutdown)
    install_diagnostics()
    try:
        from sat_tool.app import main as launch_app
        launch_app()
    except BaseException as exc:
        report_exception("Application startup/event loop failure",exc)
        raise
    clean_shutdown()
    return 0

if __name__ == '__main__':
    sys.exit(main())
