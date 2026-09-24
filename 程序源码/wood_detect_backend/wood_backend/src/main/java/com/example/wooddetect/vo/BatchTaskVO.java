package com.example.wooddetect.vo;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

@Data
public class BatchTaskVO {
    private String batchNo;
    private Integer totalCount;
    private Integer processedCount;
    private Integer successCount;
    private Integer failCount;
    private String status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private List<DetectResponseVO> items;
}
