import unittest

import numpy as np

from inference_pipeline import (
    Detection,
    MODEL_CLASS_NAMES,
    adaptive_tiling_reason,
    classify_defect_regions,
    class_aware_nms,
    offset_detections,
    propose_defect_regions,
    run_inference,
    run_tiled_prediction,
    sanitize_detections,
    trace_confirmed_cracks,
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
        proposals = propose_defect_regions(image)
        self.assertGreaterEqual(len(proposals), 1)
        self.assertEqual(-1, proposals[0].class_id)
        self.assertLessEqual(proposals[0].x1, 260)
        self.assertGreaterEqual(proposals[0].x2, 520)

        non_wood = np.full((600, 800, 3), (190, 80, 30), dtype=np.uint8)
        non_wood[180:360, 260:520] = (20, 25, 30)
        self.assertEqual([], propose_defect_regions(non_wood))

    def test_local_review_keeps_threshold_and_actual_model_coordinates(self):
        image = np.full((600, 800, 3), (80, 140, 190), dtype=np.uint8)
        image[180:360, 260:520] = (20, 25, 30)
        names = dict(enumerate(MODEL_CLASS_NAMES))
        calls = []

        def classifier(region, size):
            calls.append((region.shape, size))
            return [Detection(6, 0.12, 0, 0, 20, 20), Detection(7, 0.61, 100, 80, 220, 200)], names

        outcome = run_inference(image, "STANDARD", lambda *_: ([], names), 640, classifier)
        self.assertEqual(1, len(outcome.detections))
        result = outcome.detections[0]
        self.assertEqual(7, result.class_id)
        self.assertAlmostEqual(0.61, result.confidence)
        self.assertAlmostEqual(269, result.x1, delta=3)
        self.assertEqual(120, result.x2 - result.x1)
        self.assertGreater(outcome.tile_count, 3)
        self.assertEqual(1, len(calls))
        self.assertEqual(896, calls[0][1])
        self.assertLess(calls[0][0][0], image.shape[0])

        self.assertEqual([], classify_defect_regions(
            image, propose_defect_regions(image),
            lambda *_: ([Detection(7, 0.21, 100, 80, 220, 200)], names),
        ))
        self.assertEqual([], classify_defect_regions(
            image, propose_defect_regions(image),
            lambda *_: ([Detection(7, 0.9, 0, 0, 20, 20)], names),
        ))

        fast = run_inference(image, "FAST", lambda *_: ([], names), 640, classifier)
        self.assertEqual((), fast.detections)
        self.assertEqual(1, len(calls))

    def test_fallback_never_invents_class_or_geometric_confidence(self):
        image = np.full((600, 800, 3), (80, 140, 190), dtype=np.uint8)
        image[180:360, 260:520] = (20, 25, 30)
        names = dict(enumerate(MODEL_CLASS_NAMES))
        self.assertEqual((), run_inference(image, "STANDARD", lambda *_: ([], names), 640).detections)
        candidates = propose_defect_regions(image)
        for predictions in ([], [Detection(99, 0.9, 0, 0, 20, 20)],
                            [Detection(6, float('nan'), 0, 0, 20, 20)],
                            [Detection(6, 0.0, 0, 0, 20, 20)]):
            with self.subTest(predictions=predictions):
                self.assertEqual([], classify_defect_regions(image, candidates, lambda *_: (predictions, names)))
        self.assertEqual([], classify_defect_regions(
            image, candidates, lambda *_: ([Detection(6, 0.8, 0, 0, 20, 20)], {6: "insect_damage"}),
        ))

    def test_normal_confident_predictions_are_unchanged(self):
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        detection = Detection(9, 0.85, 100, 100, 500, 500)
        def unexpected_classifier(*_):
            self.fail("Confident model detections must not trigger fallback")
        outcome = run_inference(image, "STANDARD", lambda *_: ([detection], {9: "stain"}), 640,
                                unexpected_classifier)
        self.assertEqual((detection,), outcome.detections)

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
        self.assertEqual([512, 640, 896], calls)

    def test_small_photo_is_really_sliced_and_bounded(self):
        image = np.zeros((573, 860, 3), dtype=np.uint8)
        shapes = []
        def predictor(crop, size):
            shapes.append(crop.shape)
            self.assertEqual(896, size)
            return [], {}
        _, _, count = run_tiled_prediction(image, predictor)
        self.assertEqual(6, count)
        self.assertTrue(all(shape[0] < 573 and shape[1] < 860 for shape in shapes))
        _, _, count = run_tiled_prediction(np.zeros((2100, 4200, 3), dtype=np.uint8), predictor)
        self.assertLessEqual(count, 24)

    def test_gray_views_keep_cracks_and_reject_crop_filling_artifacts(self):
        def predictor(crop, size):
            h, w = crop.shape[:2]
            return [Detection(4, 0.7, 50, 60, 70, 140),
                    Detection(7, 0.95, 0, 0, w, h)], dict(enumerate(MODEL_CLASS_NAMES))
        detections, _, _ = run_tiled_prediction(np.zeros((573, 860, 3), dtype=np.uint8), predictor,
                                                grayscale=True)
        self.assertTrue(detections)
        self.assertEqual({4}, {d.class_id for d in detections})

    def test_filters_invalid_boxes_and_never_leaks_internal_classes(self):
        valid = Detection(4, 0.4, -2, 5, 900, 80)
        items = [valid, Detection(-1, 0.9, 1, 1, 20, 20), Detection(4, 0.1, 1, 1, 20, 20),
                 Detection(4, 0.9, 50, 50, 20, 20), Detection(4, 0.9, float('nan'), 1, 20, 20)]
        self.assertEqual([Detection(4, 0.4, 0, 5, 860, 80)], sanitize_detections(items, 860, 573, 0.25))

    def test_crack_trace_requires_a_model_seed_and_retains_confidence(self):
        image = np.full((600, 800, 3), (80, 140, 190), dtype=np.uint8)
        image[100:450, 300:304] = (20, 20, 20)
        self.assertEqual([], trace_confirmed_cracks(image, []))
        seed = Detection(4, 0.61, 294, 200, 310, 260)
        result = trace_confirmed_cracks(image, [seed])[0]
        self.assertEqual(0.61, result.confidence)
        self.assertEqual(4, result.class_id)
        self.assertLessEqual(result.y1, 100)
        self.assertGreaterEqual(result.y2, 450)

    def test_accurate_keeps_whole_image_objects(self):
        image = np.zeros((573, 860, 3), dtype=np.uint8)
        whole = Detection(6, 0.9, 50, 30, 800, 500)
        def predictor(crop, _):
            return ([whole] if crop.shape == image.shape else []), {6: 'decay'}
        self.assertEqual((whole,), run_inference(image, 'ACCURATE', predictor, 640).detections)

    def test_fine_crack_scale_is_accurate_only_and_requires_stronger_response(self):
        image = np.zeros((573, 860, 3), dtype=np.uint8)
        names = dict(enumerate(MODEL_CLASS_NAMES))
        def predictor(crop, _):
            if crop.shape[:2] == (384, 384):
                return [Detection(4, 0.6, 40, 50, 120, 65),
                        Detection(4, 0.4, 150, 90, 210, 105)], names
            return [], names
        standard = run_inference(image, 'STANDARD', predictor, 640)
        accurate = run_inference(image, 'ACCURATE', predictor, 640)
        self.assertEqual((), standard.detections)
        self.assertTrue(accurate.detections)
        self.assertTrue(all(item.confidence == 0.6 for item in accurate.detections))
        self.assertGreater(accurate.tile_count, standard.tile_count)


if __name__ == "__main__":
    unittest.main()
