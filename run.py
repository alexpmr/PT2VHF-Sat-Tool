"""Entry point. Native import test runs before the GUI is imported."""
import sys

def main():
    if len(sys.argv) >= 3 and sys.argv[1] == '--self-test':
        from sat_tool.diagnostics import run_self_test
        return run_self_test(sys.argv[2], sys.argv[3] if len(sys.argv) >= 4 else '')
    from sat_tool.app import main as launch_app
    launch_app()
    return 0

if __name__ == '__main__':
    sys.exit(main())
