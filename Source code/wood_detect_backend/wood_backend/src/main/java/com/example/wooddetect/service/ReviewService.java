package com.example.wooddetect.service;

import com.example.wooddetect.dto.ReviewSubmissionDTO;
import com.example.wooddetect.vo.DetectResponseVO;
import com.example.wooddetect.vo.ModelVersionStatsVO;
import jakarta.servlet.http.HttpServletResponse;

import java.util.List;

public interface ReviewService {
    DetectResponseVO submitReview(Long recordId, ReviewSubmissionDTO submission);

    void exportYoloDataset(List<Long> recordIds, String reviewStatus, String modelVersion,
                           HttpServletResponse response);

    List<ModelVersionStatsVO> getModelVersionStats();
}
