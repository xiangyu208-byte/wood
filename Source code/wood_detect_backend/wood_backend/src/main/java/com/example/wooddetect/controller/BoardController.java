package com.example.wooddetect.controller;

import com.example.wooddetect.common.*;
import com.example.wooddetect.service.*;
import jakarta.validation.Valid;
import java.io.IOException;
import java.util.List;
import java.util.Map;
import org.springframework.http.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/boards")
public class BoardController {
    private final BoardService boards;
    private final FileStorageService files;
    private final DeepSeekService ai;
    private final JdbcTemplate db;

    public BoardController(BoardService boards, FileStorageService files, DeepSeekService ai, JdbcTemplate db) {
        this.boards=boards; this.files=files; this.ai=ai; this.db=db;
    }

    @GetMapping
    public Result<List<BoardService.Board>> list() {return Result.success(boards.list());}

    @PostMapping
    public Result<BoardService.Board> create(@RequestBody @Valid BoardService.Setup setup) {
        return Result.success(boards.create(setup));
    }

    @GetMapping("/{id}")
    public Result<BoardService.MapView> view(@PathVariable long id) {return Result.success(boards.view(id));}

    @PutMapping("/{id}/records/{recordId}")
    public Result<Void> attach(@PathVariable long id,@PathVariable long recordId,@Valid @RequestBody BoardService.Placement p) {
        boards.attach(id,recordId,p);
        return Result.success(null);
    }

    @DeleteMapping("/{id}/records/{recordId}")
    public Result<Void> detach(@PathVariable long id,@PathVariable long recordId) {
        boards.detach(id,recordId);
        return Result.success(null);
    }

    @PostMapping("/{id}/reference")
    public Result<Void> reference(@PathVariable long id,@RequestParam MultipartFile file) throws IOException {
        boards.find(id);
        if(file.getSize()>6*1024*1024) throw new BusinessException(HttpStatus.PAYLOAD_TOO_LARGE,"参考图上限为 6 MB");
        var info=files.validateImage(file);
        db.update("UPDATE inspection_board SET reference_image=?,reference_type=? WHERE id=?",file.getBytes(),info.mimeType(),id);
        return Result.success(null);
    }

    @GetMapping("/{id}/reference")
    public ResponseEntity<byte[]> reference(@PathVariable long id) {
        var result=db.query("SELECT reference_type,reference_image FROM inspection_board WHERE id=? AND reference_type IS NOT NULL",
                (rs,i)->ResponseEntity.ok().cacheControl(CacheControl.noStore()).contentType(MediaType.parseMediaType(rs.getString(1))).body(rs.getBytes(2)),id);
        return result.stream().findFirst().orElseThrow(()->new BusinessException(HttpStatus.NOT_FOUND,"未上传参考图"));
    }

    @GetMapping("/ai/config")
    public Result<?> config() { return Result.success(Map.of("configured",ai.configured())); }

    @PostMapping("/{id}/report")
    public Result<?> report(@PathVariable long id) {return Result.success(ai.report(boards.view(id)));}

    @PostMapping("/review/{recordId}")
    public Result<?> review(@PathVariable long recordId) {return Result.success(ai.review(boards.success(recordId)));}
}

