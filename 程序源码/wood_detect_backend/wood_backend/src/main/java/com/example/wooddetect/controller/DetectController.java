package com.example.wooddetect.controller;

import com.example.wooddetect.common.Result;
import com.example.wooddetect.dto.DetectionOptionsDTO;
import com.example.wooddetect.service.DetectService;
import com.example.wooddetect.vo.BatchTaskVO;
import com.example.wooddetect.vo.DetectHistoryVO;
import com.example.wooddetect.vo.DetectResponseVO;
import com.example.wooddetect.vo.PageResultVO;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController //作用：把这个类变成 SpringBoot 的接口控制器，负责接收前端请求并返回 JSON 格式数据
@RequestMapping("/api/detect")//用于设置控制器的统一请求路径前缀，使接口路径更规范、更易于维护
@CrossOrigin//用于解决前后端分离项目中的跨域问题，允许前端 Vue 访问后端接口。
public class DetectController {

    @Autowired//Spring 的依赖注入注解，自动注入依赖的对象，简化对象创建与管理，实现模块间解耦
    private DetectService detectService;

    /**
     * 单张图片上传并识别
     */
    @PostMapping("/upload")
    public Result<DetectResponseVO> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(defaultValue = "STANDARD") String modelMode,
            @RequestParam(defaultValue = "0.25") Double confidenceThreshold,
            @RequestParam(defaultValue = "AUTO") String precision) {
        DetectResponseVO vo = detectService.uploadAndDetect(
                file, new DetectionOptionsDTO(modelMode, confidenceThreshold, precision));
        return Result.success("图片上传并识别成功", vo);
    }

    /**
     * 批量图片上传并识别
     */
    @PostMapping("/batch-upload")
    public Result<List<DetectResponseVO>> batchUpload(
            @RequestParam("files") MultipartFile[] files,
            @RequestParam(defaultValue = "STANDARD") String modelMode,
            @RequestParam(defaultValue = "0.25") Double confidenceThreshold,
            @RequestParam(defaultValue = "AUTO") String precision) {
        List<DetectResponseVO> result = detectService.batchUploadAndDetect(
                files, new DetectionOptionsDTO(modelMode, confidenceThreshold, precision));
        return Result.success("批量图片上传并识别成功", result);
    }

    /**
     * 创建可轮询进度的异步批量识别任务
     */
    @PostMapping("/batch-upload-async")
    public ResponseEntity<Result<BatchTaskVO>> batchUploadAsync(
            @RequestParam("files") MultipartFile[] files,
            @RequestParam(defaultValue = "STANDARD") String modelMode,
            @RequestParam(defaultValue = "0.25") Double confidenceThreshold,
            @RequestParam(defaultValue = "AUTO") String precision) {
        BatchTaskVO task = detectService.createAsyncBatch(
                files, new DetectionOptionsDTO(modelMode, confidenceThreshold, precision));
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(Result.success("批量任务已创建", task));
    }

    /**
     * 查询批量任务总进度和逐项状态
     */
    @GetMapping("/batch-status/{batchNo}")
    public Result<BatchTaskVO> batchStatus(@PathVariable String batchNo) {
        return Result.success(detectService.getBatchStatus(batchNo));
    }

    @PostMapping("/batch-cancel/{batchNo}")
    public Result<BatchTaskVO> cancelBatch(@PathVariable String batchNo) {
        return Result.success("批量任务已取消", detectService.cancelBatch(batchNo));
    }

    @PostMapping("/batch-retry/{batchNo}")
    public ResponseEntity<Result<BatchTaskVO>> retryBatch(@PathVariable String batchNo) {
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(Result.success("失败项目已重新进入队列", detectService.retryBatch(batchNo)));
    }

    /**
     * 分页查询历史记录
     */
    @GetMapping("/history")
    public Result<PageResultVO<DetectHistoryVO>> history(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "10") Integer size,
            @RequestParam(required = false) String imageName,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String batchNo,
            @RequestParam(required = false) String sourceType,
            @RequestParam(required = false) String hasDefect,
            @RequestParam(required = false) String qualityGrade,
            @RequestParam(required = false) Double minQualityScore,
            @RequestParam(required = false) Double maxQualityScore,
            @RequestParam(required = false) String modelVersion,
            @RequestParam(required = false) String reviewStatus,
            @RequestParam(required = false) String reviewQueue,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime
    ) {
        return Result.success(
                detectService.getHistory(page, size, imageName, status, batchNo, sourceType, hasDefect,
                        qualityGrade, minQualityScore, maxQualityScore,
                        modelVersion, reviewStatus, reviewQueue, startTime, endTime)
        );
    }

    /**
     * 查询单条记录详情
     */
    @GetMapping("/{id}")
    public Result<DetectResponseVO> detail(@PathVariable Long id) {
        return Result.success(detectService.getDetail(id));
    }

    /**
     * 删除单条历史记录
     */
    @DeleteMapping("/{id}")
    public Result<String> delete(@PathVariable Long id) {
        detectService.deleteRecord(id);
        return Result.success("删除成功");
    }

    /**
     * 按勾选ID批量删除
     */
    @PostMapping("/batch-delete")
    public Result<String> batchDelete(@RequestBody List<Long> ids) {
        detectService.batchDeleteRecords(ids);
        return Result.success("批量删除成功");
    }

    /**
     * 按筛选条件一键删除全部记录
     */
    @PostMapping("/delete-by-condition")
    public Result<String> deleteByCondition(
            @RequestParam(required = false) String imageName,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String batchNo,
            @RequestParam(required = false) String sourceType,
            @RequestParam(required = false) String hasDefect,
            @RequestParam(required = false) String qualityGrade,
            @RequestParam(required = false) Double minQualityScore,
            @RequestParam(required = false) Double maxQualityScore,
            @RequestParam(required = false) String modelVersion,
            @RequestParam(required = false) String reviewStatus,
            @RequestParam(required = false) String reviewQueue,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime
    ) {
        detectService.deleteRecordsByCondition(imageName, status, batchNo, sourceType, hasDefect,
                qualityGrade, minQualityScore, maxQualityScore,
                modelVersion, reviewStatus, reviewQueue, startTime, endTime);
        return Result.success("已按筛选条件删除全部记录");
    }


    /**
     * 按筛选条件导出 CSV
     */
    @GetMapping("/export/csv")
    public void exportCsv(
            @RequestParam(required = false) String imageName,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String batchNo,
            @RequestParam(required = false) String sourceType,
            @RequestParam(required = false) String hasDefect,
            @RequestParam(required = false) String qualityGrade,
            @RequestParam(required = false) Double minQualityScore,
            @RequestParam(required = false) Double maxQualityScore,
            @RequestParam(required = false) String modelVersion,
            @RequestParam(required = false) String reviewStatus,
            @RequestParam(required = false) String reviewQueue,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            HttpServletResponse response
    ) {
        detectService.exportHistoryCsv(imageName, status, batchNo, sourceType, hasDefect,
                qualityGrade, minQualityScore, maxQualityScore,
                modelVersion, reviewStatus, reviewQueue, startTime, endTime, response);
    }

    @GetMapping("/export/excel")
    public void exportExcel(
            @RequestParam(required = false) String imageName,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String batchNo,
            @RequestParam(required = false) String sourceType,
            @RequestParam(required = false) String hasDefect,
            @RequestParam(required = false) String qualityGrade,
            @RequestParam(required = false) Double minQualityScore,
            @RequestParam(required = false) Double maxQualityScore,
            @RequestParam(required = false) String modelVersion,
            @RequestParam(required = false) String reviewStatus,
            @RequestParam(required = false) String reviewQueue,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            HttpServletResponse response
    ) {
        detectService.exportHistoryExcel(imageName, status, batchNo, sourceType, hasDefect,
                qualityGrade, minQualityScore, maxQualityScore,
                modelVersion, reviewStatus, reviewQueue, startTime, endTime, response);
    }

    @PostMapping("/camera-upload")
    public Result<DetectResponseVO> cameraUpload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(defaultValue = "STANDARD") String modelMode,
            @RequestParam(defaultValue = "0.25") Double confidenceThreshold,
            @RequestParam(defaultValue = "AUTO") String precision) {
        DetectResponseVO vo = detectService.cameraUploadAndDetect(
                file, new DetectionOptionsDTO(modelMode, confidenceThreshold, precision));
        return Result.success("摄像头图片识别成功", vo);
    }

    @GetMapping("/export/images")
    public void exportImages(
            @RequestParam(required = false) String imageName,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String batchNo,
            @RequestParam(required = false) String sourceType,
            @RequestParam(required = false) String hasDefect,
            @RequestParam(required = false) String qualityGrade,
            @RequestParam(required = false) Double minQualityScore,
            @RequestParam(required = false) Double maxQualityScore,
            @RequestParam(required = false) String modelVersion,
            @RequestParam(required = false) String reviewStatus,
            @RequestParam(required = false) String reviewQueue,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            HttpServletResponse response
    ) {
        detectService.exportHistoryImagesZip(
                imageName, status, batchNo, sourceType, hasDefect,
                qualityGrade, minQualityScore, maxQualityScore,
                modelVersion, reviewStatus, reviewQueue, startTime, endTime, response
        );
    }
}
