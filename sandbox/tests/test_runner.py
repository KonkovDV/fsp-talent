"""Run inside the image: docker run --rm --network none fsp-sandbox python -m unittest discover -s tests"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runner import available_languages, run  # noqa: E402

PY_SUM = "def solve(xs):\n    return sum(x for x in xs if x > 0)\n"
JS_SUM = "function solve(xs) { return xs.filter(x => x > 0).reduce((a, b) => a + b, 0) }"
CASES = [[[1, -2, 3]], [[]], [[5, 5]]]


class RunnerTest(unittest.TestCase):
    def test_both_languages_answer_every_case(self):
        self.assertIn("javascript", available_languages())
        self.assertIn("sql", available_languages())
        fixture = "create table nums(n integer); insert into nums values (1), (-2), (3);"
        self.assertEqual(run("sql", "select sum(n) from nums", [[fixture]])["outputs"], [2])
        self.assertEqual(run("sql", "delete from nums", [[fixture]])["outputs"], [None])
        self.assertEqual(run("python", PY_SUM, CASES), {"outputs": [4, 0, 10], "timed_out": False})
        self.assertEqual(run("javascript", JS_SUM, CASES), {"outputs": [4, 0, 10], "timed_out": False})

    def test_no_network_from_a_solution(self):
        source = (
            "def solve(xs):\n"
            "    import socket\n"
            "    try:\n"
            "        socket.create_connection(('1.1.1.1', 80), timeout=1).close()\n"
            "        return 1\n"
            "    except OSError:\n"
            "        return 0\n"
        )
        self.assertEqual(run("python", source, [[[]]])["outputs"], [0])

    def test_an_endless_loop_is_a_limit_not_a_wrong_answer(self):
        started = time.monotonic()
        for language, source in (("python", "def solve(xs):\n    while True:\n        pass\n"),
                                 ("javascript", "function solve(xs) { for (;;) {} }")):
            out = run(language, source, [[[]]])
            self.assertTrue(out["timed_out"], language)
            self.assertEqual(out["outputs"], [None])
        self.assertLess(time.monotonic() - started, 10)

    def test_memory_and_processes_are_bounded(self):
        hog = "def solve(xs):\n    a = []\n    while True:\n        a.append(bytearray(1 << 20))\n"
        self.assertEqual(run("python", hog, [[[]]])["outputs"], [None])
        fork = ("def solve(xs):\n    import os\n    n = 0\n    while n < 500:\n"
                "        try:\n            os.fork()\n        except OSError:\n            return -1\n"
                "        n += 1\n    return n\n")
        self.assertIn(run("python", fork, [[[]]])["outputs"][0], (None, -1))

    def test_python_cannot_fork_or_start_a_thread(self):
        # Audit M-1: no child can leave the process group that killpg ends.
        escape = ("def solve(xs):\n    import os\n    try:\n        pid = os.fork()\n    except OSError:\n"
                  "        return -1\n    if pid == 0:\n        os.setsid()\n        os._exit(0)\n    return 1\n")
        self.assertEqual(run("python", escape, [[[]]])["outputs"], [-1])
        thread = ("def solve(xs):\n    import threading\n    try:\n        threading.Thread(target=int).start()\n"
                  "    except RuntimeError:\n        return -1\n    return 1\n")
        self.assertEqual(run("python", thread, [[[]]])["outputs"], [-1])
        self.assertEqual(run("python", PY_SUM, CASES)["outputs"], [4, 0, 10])

    def test_a_solution_cannot_unlink_the_control_socket(self):
        source = (
            "def solve(xs):\n"
            "    import os\n"
            "    try:\n"
            "        os.unlink('/run/sandbox/sandbox.sock')\n"
            "        return 1\n"
            "    except OSError:\n"
            "        return 0\n"
        )
        self.assertEqual(run("python", source, [[[]]])["outputs"], [0])

    def test_reloading_os_still_cannot_unlink_the_control_socket(self):
        source = (
            "def solve(xs):\n"
            "    import importlib\n"
            "    import os\n"
            "    try:\n"
            "        importlib.reload(os)\n"
            "        os.unlink('/run/sandbox/sandbox.sock')\n"
            "        return 1\n"
            "    except OSError:\n"
            "        return 0\n"
        )
        self.assertEqual(run("python", source, [[[]]])["outputs"], [0])

    def test_a_solution_cannot_import_ctypes(self):
        source = (
            "def solve(xs):\n"
            "    try:\n"
            "        import ctypes\n"
            "        return 1\n"
            "    except ModuleNotFoundError:\n"
            "        return 0\n"
        )
        self.assertEqual(run("python", source, [[[]]])["outputs"], [0])

    def test_wrong_shapes_are_nulls(self):
        self.assertEqual(run("python", "def solve(xs):\n    return 'x'\n", CASES)["outputs"], [None] * 3)
        self.assertEqual(run("javascript", "function solve(xs) { return 2 ** 80 }", [[[]]])["outputs"], [None])
        self.assertEqual(run("javascript", "const x = 1", [[[]]])["outputs"], [None])
        self.assertEqual(run("ruby", "", [])["error"], "language")


if __name__ == "__main__":
    unittest.main()
