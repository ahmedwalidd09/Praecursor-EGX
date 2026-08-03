import sys
import os

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

out_path = os.path.join(os.getcwd(), "debug_out.txt")
with open(out_path, "w", encoding="utf-8") as f:
    try:
        import traceback
        import unittest

        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        suite.addTests(loader.loadTestsFromName("tests.test_consensus"))
        suite.addTests(loader.loadTestsFromName("tests.test_scanner_workflow"))
        runner = unittest.TextTestRunner(stream=f, verbosity=2)
        res = runner.run(suite)
        f.write(f"\nResult: failures={len(res.failures)}, errors={len(res.errors)}, total={res.testsRun}\n")
        for test, err in res.failures:
            f.write(f"FAILURE in {test}:\n{err}\n")
        for test, err in res.errors:
            f.write(f"ERROR in {test}:\n{err}\n")
    except Exception as e:
        f.write(f"EXCEPTION:\n{traceback.format_exc()}\n")
