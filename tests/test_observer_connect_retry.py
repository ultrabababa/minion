import importlib.util
import unittest
from pathlib import Path


def _load_module(script_path: Path):
    spec = importlib.util.spec_from_file_location("observer", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeSocket:
    def __init__(self, created, failures_before_success):
        self._created = created
        self._failures_before_success = failures_before_success
        self.closed = False

    def connect(self, _addr):
        attempt = len(self._created)
        if attempt <= self._failures_before_success:
            raise OSError("No route to host")

    def close(self):
        self.closed = True


class ObserverRetryTests(unittest.TestCase):
    def test_connect_with_retry_retries_and_eventually_succeeds(self):
        module = _load_module(Path(__file__).resolve().parents[1] / "observer.py")

        created = []

        def socket_factory(*_args, **_kwargs):
            sock = _FakeSocket(created, failures_before_success=2)
            created.append(sock)
            return sock

        now = {"t": 0.0}

        def monotonic():
            return now["t"]

        def sleeper(seconds):
            now["t"] += seconds

        sock = module.connect_with_retry(
            ("10.30.20.1", 5002),
            socket_factory=socket_factory,
            monotonic=monotonic,
            sleeper=sleeper,
            total_timeout=10.0,
            retry_interval=1.0,
        )

        self.assertEqual(len(created), 3)
        self.assertTrue(created[0].closed)
        self.assertTrue(created[1].closed)
        self.assertFalse(created[2].closed)
        self.assertIs(sock, created[2])

    def test_connect_with_retry_raises_after_timeout(self):
        module = _load_module(Path(__file__).resolve().parents[1] / "observer.py")

        created = []

        def socket_factory(*_args, **_kwargs):
            sock = _FakeSocket(created, failures_before_success=9999)
            created.append(sock)
            return sock

        now = {"t": 0.0}

        def monotonic():
            return now["t"]

        def sleeper(seconds):
            now["t"] += seconds

        with self.assertRaises(RuntimeError):
            module.connect_with_retry(
                ("10.30.20.1", 5002),
                socket_factory=socket_factory,
                monotonic=monotonic,
                sleeper=sleeper,
                total_timeout=2.0,
                retry_interval=1.0,
            )


if __name__ == "__main__":
    unittest.main()
