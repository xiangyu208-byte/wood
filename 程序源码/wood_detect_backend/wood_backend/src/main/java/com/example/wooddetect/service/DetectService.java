package com.example.wooddetect.service;

import com.example.wooddetect.vo.DetectHistoryVO;
import com.example.wooddetect.vo.DetectResponseVO;
import com.example.wooddetect.vo.PageResultVO;
import com.example.wooddetect.vo.BatchTaskVO;
import com.example.wooddetect.dto.DetectionOptionsDTO;
import org.springframework.web.multipart.MultipartFile;

import jakarta.servlet.http.HttpServletResponse;
import java.util.List;

public interface DetectService {

    /**
     * 单张图片上传并识别
     */
    DetectResponseVO uploadAndDetect(MultipartFile file, DetectionOptionsDTO options);

    /**
     * 摄像头图片上传并识别
     */
    DetectResponseVO cameraUploadAndDetect(MultipartFile file, DetectionOptionsDTO options);

    /**
     * 批量图片上传并识别
     */
    List<DetectResponseVO> batchUploadAndDetect(MultipartFile[] files, DetectionOptionsDTO options);

    /**
     * 创建异步批量任务，调用方可通过批次号轮询进度
     */
    BatchTaskVO createAsyncBatch(MultipartFile[] files, DetectionOptionsDTO options);

    /**
     * 查询批量任务及逐项状态
     */
    BatchTaskVO getBatchStatus(String batchNo);

    /** 取消尚未完成的异步批量任务。 */
    BatchTaskVO cancelBatch(String batchNo);

    /** 重新执行批次中失败或已取消的项目。 */
    BatchTaskVO retryBatch(String batchNo);

    /**
     * 分页查询历史记录（支持筛选）
     */
    PageResultVO<DetectHistoryVO> getHistory(
            Integer page,
            Integer size,
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime
    );

    /**
     * 查询单条记录详情
     */
    DetectResponseVO getDetail(Long id);

    /**
     * 删除单条历史记录
     */
    void deleteRecord(Long id);

    /**
     * 按勾选ID批量删除
     */
    void batchDeleteRecords(List<Long> ids);

    /**
     * 按筛选条件一键删除全部记录
     */
    void deleteRecordsByCondition(
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime
    );

    /**
     * 按筛选条件导出 CSV
     */
    void exportHistoryCsv(
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime,
            HttpServletResponse response
    );

    /**
     * 按筛选条件导出 Excel
     */
    void exportHistoryExcel(
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime,
            HttpServletResponse response
    );

    /**
     * 按筛选条件导出图片 ZIP
     */
    void exportHistoryImagesZip(
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime,
            HttpServletResponse response
    );
}
