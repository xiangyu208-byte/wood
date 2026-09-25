import unittest

import numpy as np

from inference_pipeline import (
    Detection,
    adaptive_tiling_reason,
    class_aware_nms,
    offset_detections,
    run_inference,
    sliding_positions,
)


class InferencePipelineTest(unittest.TestCase):
    def test_sliding_positions_cover_far_edge(self):
        self.assertEqual([0], sliding_positions(640, 896, 0.2))
        positions = sliding_positions(2048, 896, 0.2)
        self.assertEqual(0, positions[0])
        self.assertEqual(1152, positions[-1])

    def test_offset_restores_original_coordinates(self):
        source = [Detection(1, 0.8, 10, 20, 30, 40)]
        self.assertEqual(Detection(1, 0.8, 110, 220, 130, 240), offset_detections(source, 100, 200)[0])

    def test_nms_merges_same_class_but_keeps_other_classes(self):
        detections = [
            Detection(0, 0.9, 0, 0, 100, 100),
            Detection(0, 0.8, 5, 5, 100, 100),
            Detection(1, 0.7, 5, 5, 100, 100),
        ]
        kept = class_aware_nms(detections, 0.5)
        self.assertEqual(2, len(kept))
        self.assertEqual({0, 1}, {item.class_id for item in kept})

    def test_adaptive_mode_uses_resolution_and_first_pass(self):
        self.assertEqual("HIGH_RESOLUTION", adaptive_tiling_reason(np.zeros((2200, 2200, 3), dtype=np.uint8), []))
        self.assertEqual("NO_FIRST_PASS_DETECTION", adaptive_tiling_reason(np.zeros((600, 800, 3), dtype=np.uint8), []))
        confident = [Detection(0, 0.9, 100, 100, 500, 500)]
        self.assertIsNone(adaptive_tiling_reason(np.zeros((600, 800, 3), dtype=np.uint8), confident))

    def test_fast_and_adaptive_outcomes_report_actual_mode(self):
        calls = []

        def predictor(image, image_size):
            calls.append(image_size)
            return [Detection(0, 0.9, 10, 10, 200, 200)], {0: "dry_knot"}

        image = np.zeros((600, 800, 3), dtype=np.uint8)
        fast = run_inference(image, "FAST", predictor, 640)
        standard = run_inference(image, "STANDARD", predictor, 640)
        self.assertEqual("FAST_WHOLE", fast.actual_mode)
        self.assertEqual("STANDARD_WHOLE", standard.actual_mode)
        self.assertEqual([512, 640], calls)


if __name__ == "__main__":
    unittest.main()
