package com.example.wooddetect.util;

import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;

public class FileUtil {

    /**
     * 保存图片到本地
     * 保持原文件名不变，同名则覆盖
     *
     * @param file 上传文件
     * @param uploadRootPath 上传根目录
     * @param subDir 子目录，比如 original
     * @return 相对路径，例如 original/wood1.jpg
     */
    public static String saveImage(MultipartFile file, String uploadRootPath, String subDir) throws IOException {
        if (file == null || file.isEmpty()) {
            throw new RuntimeException("上传文件不能为空");
        }

        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null || originalFilename.trim().isEmpty()) {
            throw new RuntimeException("原始文件名不能为空");
        }

        // 处理文件名中的非法字符
        String safeFileName = originalFilename.replaceAll("[\\\\/:*?\"<>|]", "_");

        String rootPath = uploadRootPath.replace("\\", "/");
        if (!rootPath.endsWith("/")) {
            rootPath += "/";
        }

        String dirPath = rootPath + subDir;
        File dir = new File(dirPath);
        if (!dir.exists()) {
            dir.mkdirs();
        }

        File destFile = new File(dir, safeFileName);

        // transferTo 会覆盖已有同名文件
        file.transferTo(destFile);

        return subDir + "/" + safeFileName;
    }
}