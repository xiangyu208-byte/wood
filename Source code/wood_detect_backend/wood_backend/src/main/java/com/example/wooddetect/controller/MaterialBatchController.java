package com.example.wooddetect.controller;

import com.example.wooddetect.common.Result;
import com.example.wooddetect.service.InspectionAnalysisService;
import com.example.wooddetect.service.MaterialBatchService;
import java.util.List;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/inspection")
public class MaterialBatchController {
    private final MaterialBatchService batches;
    private final InspectionAnalysisService analysis;

    public MaterialBatchController(MaterialBatchService batches, InspectionAnalysisService analysis) {
        this.batches = batches;
        this.analysis = analysis;
    }

    public record BatchInput(String code) {}

    @GetMapping("/batches")
    public Result<List<String>> list() { return Result.success(batches.list()); }

    @PostMapping("/batches")
    public Result<String> create(@RequestBody BatchInput input) { return Result.success(batches.create(input.code())); }

    public record AssignInput(String code, boolean createNew, List<Long> recordIds) {}
    public record MergeInput(String targetCode, List<String> sourceCodes) {}

    @PostMapping("/batches/assign")
    public Result<MaterialBatchService.Change> assign(@RequestBody AssignInput input) {
        return Result.success(batches.assign(input.recordIds(), input.code(), input.createNew()));
    }

    @PostMapping("/batches/merge")
    public Result<MaterialBatchService.Change> merge(@RequestBody MergeInput input) {
        return Result.success(batches.merge(input.targetCode(), input.sourceCodes()));
    }

    @PostMapping("/statistics")
    public Result<InspectionAnalysisService.ResultView> statistics(@RequestBody InspectionAnalysisService.Scope scope) {
        return Result.success(analysis.result(analysis.facts(scope), false));
    }

    @PostMapping("/report")
    public Result<InspectionAnalysisService.ResultView> report(@RequestBody InspectionAnalysisService.Scope scope) {
        return Result.success(analysis.result(analysis.facts(scope), true));
    }
}
