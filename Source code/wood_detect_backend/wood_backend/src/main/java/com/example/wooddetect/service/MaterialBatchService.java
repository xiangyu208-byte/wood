package com.example.wooddetect.service;

import com.example.wooddetect.common.BusinessException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MaterialBatchService {
    private final JdbcTemplate db;

    private final NamedParameterJdbcTemplate named;

    public MaterialBatchService(JdbcTemplate db) {
        this.db = db;
        this.named = new NamedParameterJdbcTemplate(db);
    }

    public List<String> list() {
        return db.queryForList("SELECT code FROM material_batch WHERE merged_into IS NULL ORDER BY created_at DESC, code", String.class);
    }

    public String create(String input) {
        String code = input == null ? "" : input.strip();
        if (!code.matches("[\\p{L}\\p{N}][\\p{L}\\p{N} _.\\-]{0,63}")) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "批次编号限 1–64 个字符，可使用文字、数字、空格、点、横线或下划线");
        }
        try {
            db.update("INSERT INTO material_batch(code) VALUES (?)", code);
        } catch (DuplicateKeyException e) {
            throw new BusinessException(HttpStatus.CONFLICT, "批次编号已使用，请选择已有批次或更换编号");
        }
        return code;
    }

    public String resolve(String input) {
        return destination(input, false);
    }

    // Hold the batch row until the new photo is inserted, including when a camera still uses a merged code.
    public String resolveForCapture(String input) {
        return destination(input, true);
    }

    private String destination(String input, boolean lock) {
        if (input == null || input.isBlank()) return null;
        var matches = db.queryForList("SELECT COALESCE(merged_into, code) FROM material_batch WHERE code = ?"
                + (lock ? " LOCK IN SHARE MODE" : ""), String.class, input.strip());
        if (matches.isEmpty()) throw new BusinessException(HttpStatus.BAD_REQUEST, "所选批次不存在");
        return matches.get(0);
    }

    public record Change(String code, int photoCount) {}

    @Transactional
    public Change assign(List<Long> recordIds, String code, boolean createNew) {
        if (recordIds == null || recordIds.isEmpty() || recordIds.stream().anyMatch(id -> id == null || id <= 0)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "请先勾选要归批的照片");
        }
        var ids = recordIds.stream().distinct().sorted().toList();
        String target = createNew ? create(code) : destination(code, true);
        if (target == null) throw new BusinessException(HttpStatus.BAD_REQUEST, "请选择目标批次");
        var params = Map.of("ids", ids, "target", target);
        var existing = named.queryForList("SELECT id FROM detect_record WHERE id IN (:ids) ORDER BY id FOR UPDATE",
                params, Long.class);
        if (existing.size() != ids.size())
            throw new BusinessException(HttpStatus.CONFLICT, "部分照片已删除，请重新选择");
        named.update("UPDATE detect_record SET material_batch=:target WHERE id IN (:ids)", params);
        return new Change(target, ids.size());
    }

    @Transactional
    public Change merge(String targetCode, List<String> sourceCodes) {
        if (targetCode == null || targetCode.isBlank() || sourceCodes == null || sourceCodes.isEmpty()
                || sourceCodes.stream().anyMatch(s -> s == null || s.isBlank()))
            throw new BusinessException(HttpStatus.BAD_REQUEST, "请选择保留的批次和要并入的批次");
        var sources = sourceCodes.stream().map(String::strip).distinct().toList();
        var codes = new ArrayList<>(sources);
        codes.add(targetCode.strip());
        var active = named.queryForList("SELECT code FROM material_batch WHERE code IN (:codes) "
                + "AND merged_into IS NULL ORDER BY code FOR UPDATE", Map.of("codes", codes), String.class);
        if (active.size() != codes.size())
            throw new BusinessException(HttpStatus.CONFLICT, "请选择不同且仍独立的批次，若已合并请重新选择");
        String target = resolveForCapture(targetCode);
        var params = Map.of("sources", sources, "target", target);
        int moved = named.update("UPDATE detect_record SET material_batch=:target WHERE material_batch IN (:sources)", params);
        named.update("UPDATE material_batch SET merged_into=:target WHERE merged_into IN (:sources) OR code IN (:sources)", params);
        return new Change(target, moved);
    }
}
