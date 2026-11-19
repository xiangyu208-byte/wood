package com.example.wooddetect.vo;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class QualityDeductionVO {
    private String type;
    private String label;
    private Double points;
    private String explanation;
}
