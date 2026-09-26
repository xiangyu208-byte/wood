package com.example.wooddetect.controller;

import com.example.wooddetect.common.Result;
import com.example.wooddetect.dto.ReviewSubmissionDTO;
import com.example.wooddetect.service.ReviewService;
import com.example.wooddetect.vo.DetectResponseVO;
import com.example.wooddetect.vo.ModelVersionStatsVO;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/review")
public class ReviewController {
    private final ReviewService reviewService;

    public ReviewController(ReviewService reviewService) {
        this.reviewService = reviewService;
    }

    @PutMapping("/{recordId}")
    public Result<DetectResponseVO> submitReview(
            @PathVariable Long recordId,
            @Valid @RequestBody ReviewSubmissionDTO submission) {
        return Result.success("人工复核已保存", reviewService.submitReview(recordId, submission));
    }

    @GetMapping("/export/yolo")
    public void exportYolo(
            @RequestParam(required = false) List<Long> recordIds,
            @RequestParam(required = false) String reviewStatus,
            @RequestParam(required = false) String modelVersion,
            HttpServletResponse response) {
        reviewService.exportYoloDataset(recordIds, reviewStatus, modelVersion, response);
    }

    @GetMapping("/model-versions")
    public Result<List<ModelVersionStatsVO>> modelVersions() {
        return Result.success(reviewService.getModelVersionStats());
    }
}
