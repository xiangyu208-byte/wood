package com.example.wooddetect.controller;

import com.example.wooddetect.common.Result;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.mapper.DetectRecordMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/test")
@CrossOrigin
public class TestController {

    @Autowired
    private DetectRecordMapper detectRecordMapper;

    @GetMapping("/hello")
    public Result<String> hello() {
        return Result.success("后端启动成功");
    }

    @GetMapping("/records")
    public Result<List<DetectRecord>> getAllRecords() {
        List<DetectRecord> list = detectRecordMapper.selectList(null);
        return Result.success(list);
    }
}