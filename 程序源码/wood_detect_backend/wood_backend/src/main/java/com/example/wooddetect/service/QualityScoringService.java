package com.example.wooddetect.service;

import com.example.wooddetect.config.QualityScoringProperties;
import com.example.wooddetect.vo.QualityDeductionVO;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class QualityScoringService {

    private static final Map<String, String> CLASS_LABELS = Map.of(
            "split", "裂纹",
            "dry_knot", "干节",
            "sound_knot", "健全节",
            "edge_knot", "边节",
            "small_knot", "小节",
            "wave", "波纹",
            "suspected_anomaly", "疑似异常（需复核）"
    );

    private final QualityScoringProperties properties;

    public QualityScoringService(QualityScoringProperties properties) {
        this.properties = properties;
    }

    public Assessment assess(List<QualityBox> rawBoxes, Integer imageWidth, Integer imageHeight) {
        int width = imageWidth == null ? 0 : imageWidth;
        int height = imageHeight == null ? 0 : imageHeight;
        if (width <= 0 || height <= 0) {
            throw new IllegalArgumentException("质量评分需要有效的图片宽高");
        }

        List<QualityBox> boxes = (rawBoxes == null ? List.<QualityBox>of() : rawBoxes).stream()
                .map(box -> clip(box, width, height))
                .filter(box -> box.x2() > box.x1() && box.y2() > box.y1())
                .toList();

        Map<String, Integer> counts = new LinkedHashMap<>();
        boxes.forEach(box -> counts.merge(normalizeClassName(box.className()), 1, Integer::sum));

        List<QualityDeductionVO> deductions = new ArrayList<>();
        double categoryPenalty = 0;
        for (Map.Entry<String, Integer> entry : counts.entrySet()) {
            double weight = properties.getCategoryWeights().getOrDefault(
                    entry.getKey(), properties.getUnknownCategoryWeight());
            double points = round2(weight * entry.getValue());
            categoryPenalty += points;
            deductions.add(new QualityDeductionVO(
                    "CATEGORY",
                    CLASS_LABELS.getOrDefault(entry.getKey(), entry.getKey()),
                    points,
                    String.format(Locale.ROOT, "%d 个 × %.2f 分", entry.getValue(), weight)
            ));
        }

        double imageArea = (double) width * height;
        double totalAreaRatio = calculateUnionArea(boxes) / imageArea;
        double maxAreaRatio = boxes.stream()
                .mapToDouble(box -> ((double) (box.x2() - box.x1()) * (box.y2() - box.y1())) / imageArea)
                .max().orElse(0);
        totalAreaRatio = clamp(totalAreaRatio, 0, 1);
        maxAreaRatio = clamp(maxAreaRatio, 0, 1);

        double areaPenalty = round2(Math.min(
                properties.getTotalAreaPenaltyCap(),
                totalAreaRatio * 100 * properties.getAreaPenaltyPerPercent()));
        double maxAreaPenalty = round2(Math.min(
                properties.getMaxAreaPenaltyCap(),
                maxAreaRatio * 100 * properties.getMaxAreaPenaltyPerPercent()));
        if (areaPenalty > 0) {
            deductions.add(new QualityDeductionVO(
                    "TOTAL_AREA", "缺陷覆盖面积", areaPenalty,
                    String.format(Locale.ROOT, "去重覆盖图片 %.2f%%，每 1%% 扣 %.2f 分（上限 %.2f 分）",
                            totalAreaRatio * 100, properties.getAreaPenaltyPerPercent(), properties.getTotalAreaPenaltyCap())
            ));
        }
        if (maxAreaPenalty > 0) {
            deductions.add(new QualityDeductionVO(
                    "MAX_AREA", "最大缺陷面积", maxAreaPenalty,
                    String.format(Locale.ROOT, "最大单框占图片 %.2f%%，每 1%% 扣 %.2f 分（上限 %.2f 分）",
                            maxAreaRatio * 100, properties.getMaxAreaPenaltyPerPercent(), properties.getMaxAreaPenaltyCap())
            ));
        }

        double score = round2(clamp(
                properties.getBaseScore() - categoryPenalty - areaPenalty - maxAreaPenalty, 0, 100));
        return new Assessment(
                score,
                grade(score),
                round6(totalAreaRatio),
                round6(maxAreaRatio),
                counts,
                deductions,
                properties.getRuleVersion(),
                properties.getDisclaimer()
        );
    }

    private String grade(double score) {
        if (score >= properties.getGradeAMin()) return "A";
        if (score >= properties.getGradeBMin()) return "B";
        if (score >= properties.getGradeCMin()) return "C";
        return "D";
    }

    private long calculateUnionArea(List<QualityBox> boxes) {
        if (boxes.isEmpty()) return 0;
        List<Integer> xs = boxes.stream()
                .flatMap(box -> java.util.stream.Stream.of(box.x1(), box.x2()))
                .distinct().sorted().toList();
        long area = 0;
        for (int i = 0; i < xs.size() - 1; i++) {
            int left = xs.get(i);
            int right = xs.get(i + 1);
            if (right <= left) continue;
            List<int[]> intervals = boxes.stream()
                    .filter(box -> box.x1() < right && box.x2() > left)
                    .map(box -> new int[]{box.y1(), box.y2()})
                    .sorted(Comparator.comparingInt(interval -> interval[0]))
                    .toList();
            long coveredY = 0;
            int start = -1;
            int end = -1;
            for (int[] interval : intervals) {
                if (start < 0) {
                    start = interval[0];
                    end = interval[1];
                } else if (interval[0] <= end) {
                    end = Math.max(end, interval[1]);
                } else {
                    coveredY += end - start;
                    start = interval[0];
                    end = interval[1];
                }
            }
            if (start >= 0) coveredY += end - start;
            area += (long) (right - left) * coveredY;
        }
        return area;
    }

    private QualityBox clip(QualityBox box, int width, int height) {
        if (box == null) return new QualityBox("unknown", 0, 0, 0, 0);
        return new QualityBox(
                normalizeClassName(box.className()),
                (int) clamp(box.x1(), 0, width),
                (int) clamp(box.y1(), 0, height),
                (int) clamp(box.x2(), 0, width),
                (int) clamp(box.y2(), 0, height)
        );
    }

    private String normalizeClassName(String className) {
        return className == null || className.isBlank() ? "unknown" : className.trim().toLowerCase(Locale.ROOT);
    }

    private double clamp(double value, double min, double max) {
        return Math.max(min, Math.min(max, value));
    }

    private double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private double round6(double value) {
        return Math.round(value * 1_000_000.0) / 1_000_000.0;
    }

    public record QualityBox(String className, int x1, int y1, int x2, int y2) {}

    public record Assessment(
            double score,
            String grade,
            double defectAreaRatio,
            double maxDefectAreaRatio,
            Map<String, Integer> defectCounts,
            List<QualityDeductionVO> deductions,
            String ruleVersion,
            String disclaimer
    ) {}
}
