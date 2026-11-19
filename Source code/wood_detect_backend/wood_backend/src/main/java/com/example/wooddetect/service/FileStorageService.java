package com.example.wooddetect.service;

import com.example.wooddetect.common.BusinessException;
import com.example.wooddetect.config.FileUploadProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

@Service
public class FileStorageService {

    private static final Logger log = LoggerFactory.getLogger(FileStorageService.class);

    private final FileUploadProperties properties;

    public FileStorageService(FileUploadProperties properties) {
        this.properties = properties;
        ImageIO.setUseCache(false);
    }

    public ImageMetadata validateImage(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "上传文件不能为空");
        }

        String originalName = sanitizeOriginalName(file.getOriginalFilename());
        String extension = extensionOf(originalName);
        if (!properties.getAllowedExtensions().stream().map(String::toLowerCase).toList().contains(extension)) {
            throw new BusinessException(HttpStatus.UNSUPPORTED_MEDIA_TYPE,
                    "不支持的图片扩展名，仅支持：" + String.join(", ", properties.getAllowedExtensions()));
        }

        String detectedMime;
        try (InputStream input = file.getInputStream()) {
            byte[] header = input.readNBytes(16);
            detectedMime = detectMime(header);
        } catch (IOException e) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "无法读取上传文件", e);
        }

        if (detectedMime == null || !extensionMatchesMime(extension, detectedMime)) {
            throw new BusinessException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "文件扩展名与真实图片格式不一致");
        }

        String declaredMime = file.getContentType();
        if (declaredMime != null && !declaredMime.isBlank() && !mimeEquivalent(declaredMime, detectedMime)) {
            throw new BusinessException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "声明的 MIME 类型与文件内容不一致");
        }

        BufferedImage image;
        try (InputStream input = file.getInputStream()) {
            image = ImageIO.read(input);
        } catch (IOException e) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "图片解码失败", e);
        }
        if (image == null || image.getWidth() <= 0 || image.getHeight() <= 0) {
            throw new BusinessException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "文件不是可解码的有效图片");
        }

        long pixels = (long) image.getWidth() * image.getHeight();
        if (image.getWidth() > properties.getMaxWidth()
                || image.getHeight() > properties.getMaxHeight()
                || pixels > properties.getMaxPixels()) {
            throw new BusinessException(HttpStatus.PAYLOAD_TOO_LARGE,
                    "图片尺寸超过限制，最大宽高为 " + properties.getMaxWidth() + "×" + properties.getMaxHeight()
                            + "，最大像素数为 " + properties.getMaxPixels());
        }

        return new ImageMetadata(originalName, extension, detectedMime, image.getWidth(), image.getHeight());
    }

    public StoredImage storeImage(MultipartFile file, String subDirectory) {
        ImageMetadata metadata = validateImage(file);
        Path root = uploadRoot();
        Path directory = root.resolve(subDirectory).normalize();
        if (!directory.startsWith(root)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "非法的存储目录");
        }

        String storedName = UUID.randomUUID().toString().replace("-", "") + "." + metadata.extension();
        Path destination = directory.resolve(storedName).normalize();
        Path temporary = directory.resolve(storedName + ".uploading").normalize();

        try {
            Files.createDirectories(directory);
            try (InputStream input = file.getInputStream()) {
                Files.copy(input, temporary, StandardCopyOption.REPLACE_EXISTING);
            }
            move(temporary, destination);
        } catch (IOException e) {
            deleteQuietly(temporary);
            deleteQuietly(destination);
            throw new BusinessException(HttpStatus.INTERNAL_SERVER_ERROR, "保存上传图片失败", e);
        }

        String relative = root.relativize(destination).toString().replace('\\', '/');
        return new StoredImage(metadata.originalName(), relative, destination.toString().replace('\\', '/'));
    }

    public List<StagedDeletion> stageForDeletion(List<String> paths) {
        Path root = uploadRoot();
        Path trash = root.resolve(".trash");
        List<StagedDeletion> staged = new ArrayList<>();
        Set<Path> seen = new HashSet<>();

        try {
            Files.createDirectories(trash);
            for (String rawPath : paths) {
                if (rawPath == null || rawPath.isBlank()) {
                    continue;
                }
                Path original = Path.of(rawPath).toAbsolutePath().normalize();
                if (!original.startsWith(root) || !seen.add(original) || !Files.isRegularFile(original)) {
                    continue;
                }
                Path stagedPath = trash.resolve(UUID.randomUUID() + "-" + original.getFileName()).normalize();
                move(original, stagedPath);
                staged.add(new StagedDeletion(original, stagedPath));
            }
            return staged;
        } catch (Exception e) {
            restore(staged);
            throw new BusinessException(HttpStatus.INTERNAL_SERVER_ERROR, "暂存待删除文件失败", e);
        }
    }

    public void restore(List<StagedDeletion> staged) {
        for (int i = staged.size() - 1; i >= 0; i--) {
            StagedDeletion item = staged.get(i);
            try {
                if (Files.exists(item.stagedPath())) {
                    Files.createDirectories(item.originalPath().getParent());
                    move(item.stagedPath(), item.originalPath());
                }
            } catch (IOException e) {
                log.error("恢复文件失败: {}", item.originalPath(), e);
            }
        }
    }

    public void finalizeDeletion(List<StagedDeletion> staged) {
        for (StagedDeletion item : staged) {
            deleteQuietly(item.stagedPath());
        }
    }

    public void deleteManagedFile(String path) {
        if (path == null || path.isBlank()) {
            return;
        }
        Path normalized = Path.of(path).toAbsolutePath().normalize();
        if (normalized.startsWith(uploadRoot())) {
            deleteQuietly(normalized);
        }
    }

    public Path resolveManagedFile(String path) {
        if (path == null || path.isBlank()) {
            return null;
        }
        Path normalized = Path.of(path).toAbsolutePath().normalize();
        return normalized.startsWith(uploadRoot()) ? normalized : null;
    }

    private Path uploadRoot() {
        return Path.of(properties.getUploadPath()).toAbsolutePath().normalize();
    }

    private String sanitizeOriginalName(String rawName) {
        if (rawName == null || rawName.isBlank()) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "原始文件名不能为空");
        }
        String normalized = rawName.replace('\\', '/');
        String name = normalized.substring(normalized.lastIndexOf('/') + 1).trim();
        if (name.isBlank() || name.contains("..") || name.length() > 255) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "文件名不合法");
        }
        return name.replaceAll("[\\p{Cntrl}]", "_");
    }

    private String extensionOf(String name) {
        int dot = name.lastIndexOf('.');
        if (dot <= 0 || dot == name.length() - 1) {
            throw new BusinessException(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "图片文件缺少扩展名");
        }
        return name.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    private String detectMime(byte[] header) {
        if (header.length >= 3 && (header[0] & 0xff) == 0xff && (header[1] & 0xff) == 0xd8
                && (header[2] & 0xff) == 0xff) {
            return "image/jpeg";
        }
        if (header.length >= 8 && (header[0] & 0xff) == 0x89 && header[1] == 0x50 && header[2] == 0x4e
                && header[3] == 0x47 && header[4] == 0x0d && header[5] == 0x0a
                && header[6] == 0x1a && header[7] == 0x0a) {
            return "image/png";
        }
        if (header.length >= 2 && header[0] == 0x42 && header[1] == 0x4d) {
            return "image/bmp";
        }
        return null;
    }

    private boolean extensionMatchesMime(String extension, String mime) {
        return switch (mime) {
            case "image/jpeg" -> extension.equals("jpg") || extension.equals("jpeg");
            case "image/png" -> extension.equals("png");
            case "image/bmp" -> extension.equals("bmp");
            default -> false;
        };
    }

    private boolean mimeEquivalent(String declared, String detected) {
        String normalized = declared.toLowerCase(Locale.ROOT);
        if (normalized.equals("image/jpg")) {
            normalized = "image/jpeg";
        }
        return normalized.equals(detected);
    }

    private void move(Path source, Path target) throws IOException {
        try {
            Files.move(source, target, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } catch (AtomicMoveNotSupportedException e) {
            Files.move(source, target, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private void deleteQuietly(Path path) {
        if (path == null) {
            return;
        }
        try {
            Files.deleteIfExists(path);
        } catch (IOException e) {
            log.warn("清理文件失败: {}", path, e);
        }
    }

    public record ImageMetadata(String originalName, String extension, String mimeType, int width, int height) {
    }

    public record StoredImage(String originalName, String relativePath, String absolutePath) {
    }

    public record StagedDeletion(Path originalPath, Path stagedPath) {
    }
}
