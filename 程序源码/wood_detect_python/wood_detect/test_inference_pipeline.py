import unittest

import numpy as np

from inference_pipeline import (
    Detection,
    adaptive_tiling_reason,
    class_aware_nms,
    offset_detections,
    propose_suspected_anomalies,
    run_inference,
    sliding_positions,
    touches_image_edge,
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

        contained = class_aware_nms(
            [
                Detection(4, 0.9, 0, 0, 200, 120),
                Detection(4, 0.7, 10, 10, 180, 80),
            ],
            0.5,
        )
        self.assertEqual(1, len(contained))

    def test_adaptive_mode_uses_resolution_and_first_pass(self):
        self.assertEqual("HIGH_RESOLUTION", adaptive_tiling_reason(np.zeros((2200, 2200, 3), dtype=np.uint8), []))
        self.assertEqual("NO_FIRST_PASS_DETECTION", adaptive_tiling_reason(np.zeros((600, 800, 3), dtype=np.uint8), []))
        confident = [Detection(0, 0.9, 100, 100, 500, 500)]
        self.assertIsNone(adaptive_tiling_reason(np.zeros((600, 800, 3), dtype=np.uint8), confident))
        edge_only = [Detection(4, 0.9, 0, 300, 120, 500)]
        self.assertEqual("EDGE_ONLY_FIRST_PASS", adaptive_tiling_reason(np.zeros((600, 800, 3), dtype=np.uint8), edge_only))

    def test_edge_detection_and_enclosed_wood_anomaly_proposal(self):
        self.assertTrue(touches_image_edge(Detection(4, 0.8, 0, 20, 80, 100), 800, 600))
        self.assertFalse(touches_image_edge(Detection(4, 0.8, 200, 200, 400, 400), 800, 600))

        image = np.full((600, 800, 3), (80, 140, 190), dtype=np.uint8)
        image[180:360, 260:520] = (20, 25, 30)
        proposals = propose_suspected_anomalies(image)
        self.assertGreaterEqual(len(proposals), 1)
        self.assertEqual(6, proposals[0].class_id)
        self.assertLessEqual(proposals[0].x1, 260)
        self.assertGreaterEqual(proposals[0].x2, 520)

        non_wood = np.full((600, 800, 3), (190, 80, 30), dtype=np.uint8)
        non_wood[180:360, 260:520] = (20, 25, 30)
        self.assertEqual([], propose_suspected_anomalies(non_wood))

    def test_fast_and_adaptive_outcomes_report_actual_mode(self):
        calls = []

        def predictor(image, image_size):
            calls.append(image_size)
            return [Detection(0, 0.9, 100, 100, 300, 300)], {0: "dry_knot"}

        image = np.zeros((600, 800, 3), dtype=np.uint8)
        fast = run_inference(image, "FAST", predictor, 640)
        standard = run_inference(image, "STANDARD", predictor, 640)
        self.assertEqual("FAST_WHOLE", fast.actual_mode)
        self.assertEqual("STANDARD_WHOLE", standard.actual_mode)
        self.assertEqual([512, 640], calls)


if __name__ == "__main__":
    unittest.main()
