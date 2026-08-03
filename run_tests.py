import sys
import unittest

if __name__ == "__main__":
    with open("test_run.log", "w", encoding="utf-8") as f:
        loader = unittest.TestLoader()
        suite = loader.discover("tests")
        runner = unittest.TextTestRunner(verbosity=2, stream=f)
        result = runner.run(suite)
        print(f"\nSUCCESS: {result.wasSuccessful()}", file=f)
        sys.exit(0 if result.wasSuccessful() else 1)
