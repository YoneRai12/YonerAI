import sys
from pathlib import Path


def test_imports():
    print("Running import validation...")
    root = Path(__file__).parent.parent
    sys.path.append(str(root / "core" / "src"))
    sys.path.append(str(root))

    modules_to_test = [
        "ora_core.main",
        "ora_core.api.routes.messages",
        "ora_core.api.schemas.messages",
        "ora_core.brain.process",
        "ora_core.brain.memory",
        "ora_core.brain.context",
        "src.utils.core_client",
    ]

    failed = False
    for mod in modules_to_test:
        try:
            __import__(mod)
            print(f"[OK] {mod}")
        except Exception as e:
            print(f"[FAIL] {mod}: {e}")
            failed = True

    if failed:
        print("\nImport validation failed. Check log for details.")
        sys.exit(1)
    else:
        print("\nAll core modules imported successfully.")

if __name__ == "__main__":
    test_imports()
