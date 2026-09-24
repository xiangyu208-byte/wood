package com.example.wooddetect.service;

import com.example.wooddetect.common.BusinessException;
import com.example.wooddetect.config.FileUploadProperties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockMultipartFile;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FileStorageServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void sameOriginalNameIsStoredWithDifferentUuidNames() throws Exception {
        FileStorageService service = serviceWithLimits(100, 100, 10_000);
        byte[] png = imageBytes(20, 20, "png");
        MockMultipartFile first = new MockMultipartFile("file", "same.png", "image/png", png);
        MockMultipartFile second = new MockMultipartFile("file", "same.png", "image/png", png);

        FileStorageService.StoredImage firstStored = service.storeImage(first, "original");
        FileStorageService.StoredImage secondStored = service.storeImage(second, "original");

        assertThat(firstStored.originalName()).isEqualTo("same.png");
        assertThat(firstStored.absolutePath()).isNotEqualTo(secondStored.absolutePath());
        assertThat(Path.of(firstStored.absolutePath())).isRegularFile();
        assertThat(Path.of(secondStored.absolutePath())).isRegularFile();
    }

    @Test
    void rejectsMismatchedDeclaredMimeAndRealFormat() throws Exception {
        FileStorageService service = serviceWithLimits(100, 100, 10_000);
        MockMultipartFile file = new MockMultipartFile(
                "file", "fake.jpg", "image/jpeg", imageBytes(10, 10, "png"));

        assertThatThrownBy(() -> service.validateImage(file))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getStatus()).isEqualTo(HttpStatus.UNSUPPORTED_MEDIA_TYPE));
    }

    @Test
    void rejectsImageOverDimensionLimit() throws Exception {
        FileStorageService service = serviceWithLimits(10, 10, 100);
        MockMultipartFile file = new MockMultipartFile(
                "file", "large.png", "image/png", imageBytes(11, 10, "png"));

        assertThatThrownBy(() -> service.validateImage(file))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getStatus()).isEqualTo(HttpStatus.PAYLOAD_TOO_LARGE));
    }

    @Test
    void stagedDeletionCanBeRestoredOrFinalized() throws Exception {
        FileStorageService service = serviceWithLimits(100, 100, 10_000);
        MockMultipartFile file = new MockMultipartFile(
                "file", "restore.png", "image/png", imageBytes(10, 10, "png"));
        FileStorageService.StoredImage stored = service.storeImage(file, "original");
        Path original = Path.of(stored.absolutePath());

        List<FileStorageService.StagedDeletion> firstStage = service.stageForDeletion(List.of(stored.absolutePath()));
        assertThat(original).doesNotExist();
        service.restore(firstStage);
        assertThat(original).isRegularFile();

        List<FileStorageService.StagedDeletion> secondStage = service.stageForDeletion(List.of(stored.absolutePath()));
        service.finalizeDeletion(secondStage);
        assertThat(original).doesNotExist();
        assertThat(secondStage.get(0).stagedPath()).doesNotExist();
    }

    private FileStorageService serviceWithLimits(int maxWidth, int maxHeight, long maxPixels) {
        FileUploadProperties properties = new FileUploadProperties();
        properties.setUploadPath(tempDir.toString());
        properties.setAccessUrlPrefix("/static/");
        properties.setAllowedExtensions(List.of("jpg", "jpeg", "png", "bmp"));
        properties.setMaxWidth(maxWidth);
        properties.setMaxHeight(maxHeight);
        properties.setMaxPixels(maxPixels);
        return new FileStorageService(properties);
    }

    private byte[] imageBytes(int width, int height, String format) throws Exception {
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        try (ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            ImageIO.write(image, format, output);
            return output.toByteArray();
        }
    }
}
