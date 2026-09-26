package com.example.wooddetect.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class ReviewAnnotationDTO {
    private Long originalDetailId;

    @NotBlank
    private String className;

    @NotNull @Min(0)
    private Integer x1;
    @NotNull @Min(0)
    private Integer y1;
    @NotNull @Min(0)
    private Integer x2;
    @NotNull @Min(0)
    private Integer y2;
}
