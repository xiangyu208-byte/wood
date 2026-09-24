package com.example.wooddetect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.wooddetect.config.FileUploadProperties;
import com.example.wooddetect.dto.PythonDetectResponseDTO;
import com.example.wooddetect.entity.DetectDetail;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.mapper.DetectDetailMapper;
import com.example.wooddetect.mapper.DetectRecordMapper;
import com.example.wooddetect.service.DetectService;
import com.example.wooddetect.util.FileUtil;
import com.example.wooddetect.util.PythonDetectClient;
import com.example.wooddetect.vo.DetectDetailVO;
import com.example.wooddetect.vo.DetectHistoryVO;
import com.example.wooddetect.vo.DetectResponseVO;
import com.example.wooddetect.vo.PageResultVO;
import jakarta.servlet.http.HttpServletResponse;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import java.io.File;
import java.io.PrintWriter;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.io.FileInputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

@Service
public class DetectServiceImpl implements DetectService {

    @Autowired
    private DetectRecordMapper detectRecordMapper;

    @Autowired
    private DetectDetailMapper detectDetailMapper;

    @Autowired
    private FileUploadProperties fileUploadProperties;

    @Autowired
    private PythonDetectClient pythonDetectClient;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public DetectResponseVO uploadAndDetect(MultipartFile file) {
        return processSingleFile(file, null, "UPLOAD");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public DetectResponseVO cameraUploadAndDetect(MultipartFile file) {
        String batchNo = "CAMERA_" + System.currentTimeMillis();
        return processSingleFile(file, batchNo, "CAMERA");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public List<DetectResponseVO> batchUploadAndDetect(MultipartFile[] files) {
        if (files == null || files.length == 0) {
            throw new RuntimeException("上传文件不能为空");
        }

        List<DetectResponseVO> resultList = new ArrayList<>();
        String batchNo = "UPLOAD_" + System.currentTimeMillis();

        for (MultipartFile file : files) {
            if (file == null || file.isEmpty()) {
                continue;
            }
            DetectResponseVO result = processSingleFile(file, batchNo, "UPLOAD");
            resultList.add(result);
        }

        return resultList;
    }

    /**
     * 单张图片处理公共方法
     */
    private DetectResponseVO processSingleFile(MultipartFile file, String batchNo, String sourceType) {
        DetectResponseVO result = new DetectResponseVO();

        if (file == null || file.isEmpty()) {
            result.setStatus("FAIL");
            result.setErrorMessage("上传文件不能为空");
            return result;
        }

        LocalDateTime now = LocalDateTime.now();
        String imagePath = null;
        String imageUrl = null;

        try {
            // 1. 保存原图
            String originalRelativePath = FileUtil.saveImage(
                    file,
                    fileUploadProperties.getUploadPath(),
                    "original"
            );

            imagePath = buildDiskPath(originalRelativePath);
            imageUrl = buildAccessUrl(originalRelativePath);

            // 2. 插入主表
            DetectRecord record = new DetectRecord();
            record.setImageName(file.getOriginalFilename());
            record.setImagePath(imagePath);
            record.setImageUrl(imageUrl);
            record.setResultImagePath(null);
            record.setResultImageUrl(null);
            record.setTotalCount(0);
            record.setStatus("PROCESSING");
            record.setErrorMessage(null);
            record.setBatchNo(batchNo);
            record.setSourceType(sourceType);
            record.setCreateTime(now);
            record.setUpdateTime(now);

            detectRecordMapper.insert(record);
            Long recordId = record.getId();

            // 3. 调 Python 推理
            PythonDetectResponseDTO detectResult = pythonDetectClient.detect(imagePath);

            if (detectResult == null || detectResult.getSuccess() == null || !detectResult.getSuccess()) {
                record.setStatus("FAIL");
                record.setErrorMessage("Python 推理失败");
                record.setUpdateTime(LocalDateTime.now());
                detectRecordMapper.updateById(record);

                result.setStatus("FAIL");
                result.setErrorMessage("Python 推理失败");
                result.setImageName(file.getOriginalFilename());
                result.setImageUrl(imageUrl);
                return result;
            }

            // 4. 更新主表
            record.setResultImagePath(detectResult.getResultImagePath());
            record.setResultImageUrl(detectResult.getResultImageUrl());
            record.setTotalCount(detectResult.getTotalCount() == null ? 0 : detectResult.getTotalCount());
            record.setStatus("SUCCESS");
            record.setErrorMessage(null);
            record.setUpdateTime(LocalDateTime.now());

            detectRecordMapper.updateById(record);

            // 5. 保存缺陷明细
            saveDetectDetails(recordId, detectResult.getDetails());

            // 6. 返回完整详情
            return getDetail(recordId);

        } catch (Exception e) {
            result.setStatus("FAIL");
            result.setErrorMessage("处理失败: " + e.getMessage());
            result.setImageName(file.getOriginalFilename());
            result.setImageUrl(imageUrl);
            return result;
        }
    }


    @Override
    public PageResultVO<DetectHistoryVO> getHistory(
            Integer page,
            Integer size,
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime
    ) {
        if (page == null || page < 1) {
            page = 1;
        }
        if (size == null || size < 1) {
            size = 10;
        }

        List<DetectRecord> allRecords = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime
        );
        Long total = (long) allRecords.size();

        int fromIndex = (page - 1) * size;
        int toIndex = Math.min(fromIndex + size, allRecords.size());

        List<DetectRecord> pageRecords = new ArrayList<>();
        if (fromIndex < allRecords.size()) {
            pageRecords = allRecords.subList(fromIndex, toIndex);
        }

        List<DetectHistoryVO> recordVOList = new ArrayList<>();
        for (DetectRecord record : pageRecords) {
            DetectHistoryVO vo = new DetectHistoryVO();
            vo.setRecordId(record.getId());
            vo.setBatchNo(record.getBatchNo());
            vo.setSourceType(record.getSourceType());
            vo.setImageName(record.getImageName());
            vo.setImageUrl(record.getImageUrl());
            vo.setResultImageUrl(record.getResultImageUrl());
            vo.setTotalCount(record.getTotalCount());
            vo.setStatus(record.getStatus());
            vo.setCreateTime(record.getCreateTime());
            recordVOList.add(vo);
        }

        PageResultVO<DetectHistoryVO> pageResult = new PageResultVO<>();
        pageResult.setRecords(recordVOList);
        pageResult.setTotal(total);
        pageResult.setPage(page);
        pageResult.setSize(size);

        return pageResult;
    }

    @Override
    public DetectResponseVO getDetail(Long id) {
        DetectRecord record = detectRecordMapper.selectById(id);
        if (record == null) {
            throw new RuntimeException("识别记录不存在，ID=" + id);
        }

        QueryWrapper<DetectDetail> detailQueryWrapper = new QueryWrapper<>();
        detailQueryWrapper.eq("record_id", id);

        List<DetectDetail> detailList = detectDetailMapper.selectList(detailQueryWrapper);

        DetectResponseVO vo = new DetectResponseVO();
        vo.setRecordId(record.getId());
        vo.setImageName(record.getImageName());
        vo.setImageUrl(record.getImageUrl());
        vo.setResultImageUrl(record.getResultImageUrl());
        vo.setTotalCount(record.getTotalCount());
        vo.setStatus(record.getStatus());
        vo.setErrorMessage(record.getErrorMessage());
        vo.setSourceType(record.getSourceType());
        vo.setCreateTime(record.getCreateTime());

        List<DetectDetailVO> detailVOList = new ArrayList<>();
        for (DetectDetail detail : detailList) {
            DetectDetailVO detailVO = new DetectDetailVO();
            detailVO.setClassName(detail.getClassName());
            detailVO.setConfidence(detail.getConfidence());
            detailVO.setX1(detail.getX1());
            detailVO.setY1(detail.getY1());
            detailVO.setX2(detail.getX2());
            detailVO.setY2(detail.getY2());
            detailVOList.add(detailVO);
        }

        vo.setDetails(detailVOList);
        return vo;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteRecord(Long id) {
        DetectRecord record = detectRecordMapper.selectById(id);
        if (record == null) {
            throw new RuntimeException("要删除的记录不存在，ID=" + id);
        }

        // 删除明细
        QueryWrapper<DetectDetail> detailQueryWrapper = new QueryWrapper<>();
        detailQueryWrapper.eq("record_id", id);
        detectDetailMapper.delete(detailQueryWrapper);

        // 删除主表
        detectRecordMapper.deleteById(id);

        // 删除文件
        deleteFileIfExists(record.getImagePath());
        deleteFileIfExists(record.getResultImagePath());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void batchDeleteRecords(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            throw new RuntimeException("要删除的记录ID不能为空");
        }

        for (Long id : ids) {
            if (id == null) {
                continue;
            }
            deleteRecord(id);
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteRecordsByCondition(
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime
    ) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime
        );

        if (records == null || records.isEmpty()) {
            throw new RuntimeException("没有符合条件的记录可删除");
        }

        for (DetectRecord record : records) {
            if (record != null && record.getId() != null) {
                deleteRecord(record.getId());
            }
        }
    }

    @Override
    public void exportHistoryCsv(
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime,
            HttpServletResponse response
    ) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime
        );

        response.setContentType("text/csv;charset=UTF-8");
        response.setCharacterEncoding("UTF-8");
        response.setHeader("Content-Disposition", "attachment; filename=detect_history.csv");

        try (PrintWriter writer = response.getWriter()) {
            writer.write('\uFEFF');
            writer.println("记录ID,批次号,来源类型,图片名称,原图URL,结果图URL,缺陷数,状态,创建时间");

            for (DetectRecord record : records) {
                writer.printf("%d,%s,%s,%s,%s,%s,%d,%s,%s%n",
                        record.getId(),
                        safeCsv(record.getBatchNo()),
                        safeCsv(record.getSourceType()),
                        safeCsv(record.getImageName()),
                        safeCsv(record.getImageUrl()),
                        safeCsv(record.getResultImageUrl()),
                        record.getTotalCount() == null ? 0 : record.getTotalCount(),
                        safeCsv(record.getStatus()),
                        record.getCreateTime() == null ? "" : record.getCreateTime().toString()
                );
            }
        } catch (Exception e) {
            throw new RuntimeException("导出 CSV 失败：" + e.getMessage(), e);
        }
    }

    @Override
    public void exportHistoryExcel(
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime,
            HttpServletResponse response
    ) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime
        );

        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setHeader("Content-Disposition", "attachment; filename=detect_history.xlsx");

        try (XSSFWorkbook workbook = new XSSFWorkbook()) {
            Sheet sheet = workbook.createSheet("历史记录");

            Row headerRow = sheet.createRow(0);
            headerRow.createCell(0).setCellValue("记录ID");
            headerRow.createCell(1).setCellValue("批次号");
            headerRow.createCell(2).setCellValue("来源类型");
            headerRow.createCell(3).setCellValue("图片名称");
            headerRow.createCell(4).setCellValue("原图URL");
            headerRow.createCell(5).setCellValue("结果图URL");
            headerRow.createCell(6).setCellValue("缺陷数");
            headerRow.createCell(7).setCellValue("状态");
            headerRow.createCell(8).setCellValue("创建时间");

            int rowNum = 1;
            for (DetectRecord record : records) {
                Row row = sheet.createRow(rowNum++);
                row.createCell(0).setCellValue(record.getId() == null ? 0 : record.getId());
                row.createCell(1).setCellValue(nullToEmpty(record.getBatchNo()));
                row.createCell(2).setCellValue(nullToEmpty(record.getSourceType()));
                row.createCell(3).setCellValue(nullToEmpty(record.getImageName()));
                row.createCell(4).setCellValue(nullToEmpty(record.getImageUrl()));
                row.createCell(5).setCellValue(nullToEmpty(record.getResultImageUrl()));
                row.createCell(6).setCellValue(record.getTotalCount() == null ? 0 : record.getTotalCount());
                row.createCell(7).setCellValue(nullToEmpty(record.getStatus()));
                row.createCell(8).setCellValue(record.getCreateTime() == null ? "" : record.getCreateTime().toString());
            }

            for (int i = 0; i < 9; i++) {
                sheet.autoSizeColumn(i);
            }

            workbook.write(response.getOutputStream());
        } catch (Exception e) {
            throw new RuntimeException("导出 Excel 失败：" + e.getMessage(), e);
        }
    }

    /**
     * 保存缺陷明细到 detect_detail 表
     */
    private void saveDetectDetails(Long recordId, List<PythonDetectResponseDTO.DetectItemDTO> details) {
        if (details == null || details.isEmpty()) {
            return;
        }

        for (PythonDetectResponseDTO.DetectItemDTO item : details) {
            DetectDetail detail = new DetectDetail();
            detail.setRecordId(recordId);
            detail.setClassName(item.getClassName());
            detail.setConfidence(item.getConfidence());
            detail.setX1(item.getX1());
            detail.setY1(item.getY1());
            detail.setX2(item.getX2());
            detail.setY2(item.getY2());
            detail.setCreateTime(LocalDateTime.now());

            detectDetailMapper.insert(detail);
        }
    }

    /**
     * 查询符合筛选条件的全部记录
     */
    private List<DetectRecord> listHistoryRecords(
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime
    ) {
        QueryWrapper<DetectRecord> queryWrapper = buildHistoryQueryWrapper(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime
        );
        return detectRecordMapper.selectList(queryWrapper);
    }

    /**
     * 构建历史记录筛选条件
     */
    private QueryWrapper<DetectRecord> buildHistoryQueryWrapper(
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime
    ) {
        QueryWrapper<DetectRecord> queryWrapper = new QueryWrapper<>();

        if (imageName != null && !imageName.trim().isEmpty()) {
            queryWrapper.like("image_name", imageName.trim());
        }

        if (status != null && !status.trim().isEmpty()) {
            queryWrapper.eq("status", status.trim());
        }

        if (batchNo != null && !batchNo.trim().isEmpty()) {
            queryWrapper.like("batch_no", batchNo.trim());
        }

        if (sourceType != null && !sourceType.trim().isEmpty()) {
            queryWrapper.eq("source_type", sourceType.trim());
        }

        // 新增：是否有缺陷
        if (hasDefect != null && !hasDefect.trim().isEmpty()) {
            if ("YES".equalsIgnoreCase(hasDefect.trim())) {
                queryWrapper.gt("total_count", 0);
            } else if ("NO".equalsIgnoreCase(hasDefect.trim())) {
                queryWrapper.eq("total_count", 0);
            }
        }

        if (startTime != null && !startTime.trim().isEmpty()) {
            queryWrapper.ge("create_time", startTime.trim());
        }

        if (endTime != null && !endTime.trim().isEmpty()) {
            queryWrapper.le("create_time", endTime.trim());
        }

        queryWrapper.orderByDesc("create_time");
        return queryWrapper;
    }

    /**
     * 拼接图片磁盘真实路径
     */
    private String buildDiskPath(String relativePath) {
        String uploadRootPath = fileUploadProperties.getUploadPath();
        uploadRootPath = uploadRootPath.replace("\\", "/");

        if (!uploadRootPath.endsWith("/")) {
            uploadRootPath = uploadRootPath + "/";
        }

        return uploadRootPath + relativePath.replace("\\", "/");
    }

    /**
     * 拼接图片访问 URL
     */
    private String buildAccessUrl(String relativePath) {
        String prefix = fileUploadProperties.getAccessUrlPrefix();

        if (!prefix.endsWith("/")) {
            prefix = prefix + "/";
        }

        return prefix + relativePath.replace("\\", "/");
    }

    /**
     * 删除文件
     */
    private void deleteFileIfExists(String filePath) {
        if (filePath == null || filePath.trim().isEmpty()) {
            return;
        }

        try {
            File file = new File(filePath);
            if (file.exists() && file.isFile()) {
                boolean deleted = file.delete();
                if (!deleted) {
                    System.out.println("文件删除失败：" + filePath);
                }
            }
        } catch (Exception e) {
            System.out.println("删除文件时发生异常：" + filePath + "，原因：" + e.getMessage());
        }
    }

    private String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private String safeCsv(String value) {
        if (value == null) {
            return "";
        }
        String escaped = value.replace("\"", "\"\"");
        return "\"" + escaped + "\"";
    }

    @Override
    public void exportHistoryImagesZip(
            String imageName,
            String status,
            String batchNo,
            String sourceType,
            String hasDefect,
            String startTime,
            String endTime,
            HttpServletResponse response
    ) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime
        );

        if (records == null || records.isEmpty()) {
            throw new RuntimeException("没有符合条件的记录可下载");
        }

        response.setContentType("application/zip");
        response.setHeader("Content-Disposition", "attachment; filename=detect_images.zip");

        try (ZipOutputStream zos = new ZipOutputStream(response.getOutputStream())) {
            for (DetectRecord record : records) {
                if (record == null) {
                    continue;
                }

                String zipFileName = buildSafeFileName(record);
                addFileToZip(zos, record.getImagePath(), "original/", zipFileName);
                addFileToZip(zos, record.getResultImagePath(), "result/", zipFileName);
            }

            zos.finish();
        } catch (Exception e) {
            throw new RuntimeException("导出图片 ZIP 失败：" + e.getMessage(), e);
        }
    }

    private void addFileToZip(ZipOutputStream zos, String filePath, String folder, String fileName) {
        if (filePath == null || filePath.trim().isEmpty()) {
            return;
        }

        File file = new File(filePath);
        if (!file.exists() || !file.isFile()) {
            return;
        }

        try (FileInputStream fis = new FileInputStream(file)) {
            ZipEntry zipEntry = new ZipEntry(folder + fileName);
            zos.putNextEntry(zipEntry);

            byte[] buffer = new byte[4096];
            int len;
            while ((len = fis.read(buffer)) != -1) {
                zos.write(buffer, 0, len);
            }

            zos.closeEntry();
        } catch (Exception e) {
            System.out.println("打包文件失败：" + filePath + "，原因：" + e.getMessage());
        }
    }

    private String buildSafeFileName(DetectRecord record) {
        String originalName = record.getImageName();
        if (originalName == null || originalName.trim().isEmpty()) {
            return "unknown.jpg";
        }
        return originalName.replaceAll("[\\\\/:*?\"<>|]", "_");
    }
}