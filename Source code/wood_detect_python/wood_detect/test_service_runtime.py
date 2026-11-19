import tempfile
import threading
import unittest
from pathlib import Path

from service_runtime import InferenceBusyError, InferenceGate, InputImageError, resolve_input_image


class InputImageResolutionTest(unittest.TestCase):
    def test_accepts_file_inside_upload_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "original" / "sample.jpg"
            image.parent.mkdir()
            image.write_bytes(b"image")

            self.assertEqual(image.resolve(), resolve_input_image(str(image), root))

    def test_rejects_file_outside_upload_root(self):
        with tempfile.TemporaryDirectory() as upload_directory, tempfile.TemporaryDirectory() as other_directory:
            outside = Path(other_directory) / "outside.jpg"
            outside.write_bytes(b"image")

            with self.assertRaisesRegex(InputImageError, "上传目录"):
                resolve_input_image(str(outside), Path(upload_directory))

    def test_rejects_missing_and_blank_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(InputImageError, "不能为空"):
                resolve_input_image("  ", root)
            with self.assertRaisesRegex(InputImageError, "不存在"):
                resolve_input_image(str(root / "missing.jpg"), root)


class InferenceGateTest(unittest.TestCase):
    def test_rejects_when_all_slots_are_busy(self):
        gate = InferenceGate(max_concurrency=1, acquire_timeout_seconds=0.01)
        entered = threading.Event()
        release = threading.Event()

        def hold_slot():
            with gate.slot():
                entered.set()
                release.wait(timeout=1)

        worker = threading.Thread(target=hold_slot)
        worker.start()
        self.assertTrue(entered.wait(timeout=1))
        try:
            with self.assertRaisesRegex(InferenceBusyError, "繁忙"):
                with gate.slot():
                    self.fail("繁忙时不应获得推理槽")
        finally:
            release.set()
            worker.join(timeout=1)

    def test_releases_slot_after_exception(self):
        gate = InferenceGate(max_concurrency=1, acquire_timeout_seconds=0.01)
        with self.assertRaisesRegex(RuntimeError, "boom"):
            with gate.slot():
                raise RuntimeError("boom")

        with gate.slot():
            pass

    def test_rejects_invalid_configuration(self):
        with self.assertRaises(ValueError):
            InferenceGate(max_concurrency=0, acquire_timeout_seconds=1)
        with self.assertRaises(ValueError):
            InferenceGate(max_concurrency=1, acquire_timeout_seconds=-1)


if __name__ == "__main__":
    unittest.main()
