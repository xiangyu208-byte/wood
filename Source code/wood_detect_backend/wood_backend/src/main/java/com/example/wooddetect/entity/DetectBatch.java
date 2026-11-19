package com.example.wooddetect.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("detect_batch")
public class DetectBatch {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String batchNo;
    private Integer totalCount;
    private Integer processedCount;
    private Integer successCount;
    private Integer failCount;
    private Integer cancelledCount;
    private String status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
