package com.example.wooddetect.controller;

import com.example.wooddetect.common.Result;
import com.example.wooddetect.dto.DetectionOptionsDTO;
import com.example.wooddetect.service.FileStorageService;
import com.example.wooddetect.util.PythonDetectClient;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/detect")
public class CameraPreviewController {
    private final FileStorageService files;
    private final PythonDetectClient client;

    public CameraPreviewController(FileStorageService files, PythonDetectClient client) {
        this.files = files;
        this.client = client;
    }

    @PostMapping("/camera-preview")
    public Result<?> preview(@RequestParam MultipartFile file,
                             @RequestParam(defaultValue="FAST") String modelMode,
                             @RequestParam(defaultValue="0.25") double confidenceThreshold,
                             @RequestParam(defaultValue="AUTO") String precision) {
        var frame = files.storeImage(file, "preview");
        try {
            return Result.success(client.detect(frame.absolutePath(),
                    new DetectionOptionsDTO(modelMode, confidenceThreshold, precision), true));
        } finally {
            files.deleteManagedFile(frame.absolutePath());
        }
    }
}

