package com.example.wooddetect.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class ReviewSubmissionDTO {
    @NotBlank
    private String reviewStatus;

    @Size(max = 1000)
    private String comment;

    @Valid
    private List<ReviewAnnotationDTO> annotations = new ArrayList<>();
}
