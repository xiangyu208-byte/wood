package com.example.wooddetect.service;

import com.example.wooddetect.common.BusinessException;
import com.example.wooddetect.config.PythonServiceProperties;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.mapper.DetectRecordMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.constraints.*;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class BoardService {
    public record Setup(@NotBlank @Size(max=80) String code, @NotNull @Pattern(regexp="[AB]") String face,
                        @Min(1) @Max(100) int rows, @Min(1) @Max(100) int cols) {}
    public record Board(long id, String code, String face, int rows, int cols, boolean hasReference) {}
    public record Placement(@NotNull @Pattern(regexp="GRID|OVERLAP|UNKNOWN") String mode,
                            Integer row, Integer col, Long anchorId) {}
    public record Rect(double x, double y, double width, double height) {}
    public record Capture(long recordId, String name, String imageUrl, Integer pixelsX, Integer pixelsY,
                          String reviewStatus, Long anchorId, Integer matches, Rect area) {}
    public record Box(long recordId, String category, Rect area) {}
    public record MapView(Board board, List<Capture> captures, List<Box> boxes) {}
    private static final String BOARD_QUERY = "SELECT id,code,face,grid_rows,grid_cols,reference_type IS NOT NULL AS has_ref FROM inspection_board";
    private final JdbcTemplate db;
    private final DetectRecordMapper records;
    private final ObjectMapper json;
    private final URI registrationUri;
    private final HttpClient client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(4)).build();

    public BoardService(JdbcTemplate db, DetectRecordMapper records, ObjectMapper json, PythonServiceProperties python) {
        this.db = db;
        this.records = records;
        this.json = json;
        registrationUri = URI.create(python.getPredictUrl()).resolve("register-local-view");
    }

    private List<Board> queryBoards(String suffix, Object... parameters) {
        return db.query(BOARD_QUERY + suffix, (rs, i) -> new Board(rs.getLong(1), rs.getString(2), rs.getString(3),
                rs.getInt(4), rs.getInt(5), rs.getBoolean(6)), parameters);
    }

    public List<Board> list() { return queryBoards(" ORDER BY id DESC"); }

    public Board find(long id) {
        return queryBoards(" WHERE id=?", id).stream().findFirst()
                .orElseThrow(() -> new BusinessException(HttpStatus.NOT_FOUND, "板材不存在"));
    }

    @Transactional
    public Board create(Setup setup) {
        String code = setup.code().strip();
        try {
            db.update("INSERT INTO inspection_board(code,face,grid_rows,grid_cols) VALUES(?,?,?,?)",
                    code, setup.face(), setup.rows(), setup.cols());
        } catch (DuplicateKeyException e) {
            throw new BusinessException(HttpStatus.CONFLICT, "该板号和板面已存在，请从列表选择");
        }
        return queryBoards(" WHERE code=? AND face=?", code, setup.face()).get(0);
    }

    public DetectRecord success(long recordId) {
        DetectRecord r = records.selectById(recordId);
        if (r == null) throw new BusinessException(HttpStatus.NOT_FOUND, "检测记录不存在");
        if (!"SUCCESS".equals(r.getStatus())) throw new BusinessException(HttpStatus.CONFLICT, "请先完成图片识别");
        return r;
    }

    private record Shift(double shiftX, double shiftY, int matches) {}
    private Shift register(DetectRecord current, DetectRecord anchor) {
        try {
            var body = json.writeValueAsString(Map.of("imagePath", current.getImagePath(), "anchorPath", anchor.getImagePath()));
            var request = HttpRequest.newBuilder(registrationUri).timeout(Duration.ofSeconds(30))
                    .header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(body)).build();
            var response = client.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() == 422)
                throw new BusinessException(HttpStatus.UNPROCESSABLE_ENTITY, json.readTree(response.body()).path("message").asText("局部图无法可靠配准"));
            if (response.statusCode() != 200) throw new BusinessException(HttpStatus.SERVICE_UNAVAILABLE, "配准服务暂时不可用");
            return json.readValue(response.body(), Shift.class);
        } catch (java.io.IOException e) {
            throw new BusinessException(HttpStatus.SERVICE_UNAVAILABLE, "配准服务连接失败");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BusinessException(HttpStatus.SERVICE_UNAVAILABLE, "配准已中断");
        }
    }

    @Transactional
    public void attach(long boardId, long recordId, Placement p) {
        Board b = queryBoards(" WHERE id=? FOR UPDATE", boardId).stream().findFirst()
                .orElseThrow(() -> new BusinessException(HttpStatus.NOT_FOUND, "板材不存在"));
        DetectRecord current = success(recordId);
        Long anchor = null;
        Integer row = null, col = null;
        Shift shift = null;
        if ("GRID".equals(p.mode())) {
            row = p.row(); col = p.col();
            if (row == null || col == null || row < 1 || col < 1 || row > b.rows || col > b.cols)
                throw new BusinessException(HttpStatus.BAD_REQUEST, "拍摄格位超出板面");
        } else if ("OVERLAP".equals(p.mode())) {
            anchor = p.anchorId();
            if (anchor == null || anchor == recordId) throw new BusinessException(HttpStatus.BAD_REQUEST, "请选择另一张格位照片");
            var cells = db.query("SELECT grid_row,grid_col FROM board_capture WHERE board_id=? AND record_id=? AND grid_row IS NOT NULL",
                    (rs,i) -> new int[]{rs.getInt(1),rs.getInt(2)}, boardId, anchor);
            if (cells.isEmpty()) throw new BusinessException(HttpStatus.BAD_REQUEST, "基准照片须来自同一板面的已知格位");
            shift = register(current, success(anchor));
            var cell = cells.get(0);
            if (outside(cell[0]-1+shift.shiftY, b.rows) || outside(cell[1]-1+shift.shiftX, b.cols))
                throw new BusinessException(HttpStatus.UNPROCESSABLE_ENTITY, "配准视野超出板面，请检查基准格位");
        }
        // Claim once; a record cannot silently migrate to another physical board.
        db.update("INSERT INTO board_capture(record_id,board_id) VALUES(?,?) ON DUPLICATE KEY UPDATE record_id=VALUES(record_id)", recordId, boardId);
        Long owner = db.queryForObject("SELECT board_id FROM board_capture WHERE record_id=? FOR UPDATE", Long.class, recordId);
        if (!Objects.equals(owner, boardId)) throw new BusinessException(HttpStatus.CONFLICT, "记录已关联其他板面，请先解除关联");
        // Invalidate dependants only when the anchor actually changes grid cells.
        db.update("""
                UPDATE board_capture child JOIN board_capture parent ON child.anchor_id=parent.record_id
                SET child.anchor_id=NULL,child.shift_x=NULL,child.shift_y=NULL,child.matches_count=NULL
                WHERE parent.record_id=? AND parent.board_id=? AND NOT (parent.grid_row <=> ? AND parent.grid_col <=> ?)
                """,recordId,boardId,row,col);
        db.update("UPDATE board_capture SET grid_row=?,grid_col=?,anchor_id=?,shift_x=?,shift_y=?,matches_count=? WHERE record_id=?",
                row,col,anchor,shift == null ? null : shift.shiftX,shift == null ? null : shift.shiftY,
                shift == null ? null : shift.matches,recordId);
    }

    private static boolean outside(double start, int slots) {
        return !Double.isFinite(start) || start < -0.015 || start + 1 > slots + 0.015;
    }

    @Transactional
    public void detach(long boardId, long recordId) {
        db.queryForList("SELECT id FROM inspection_board WHERE id=? FOR UPDATE", boardId);
        db.update("UPDATE board_capture SET anchor_id=NULL,shift_x=NULL,shift_y=NULL,matches_count=NULL WHERE anchor_id=? AND board_id=?",recordId,boardId);
        db.update("DELETE FROM board_capture WHERE board_id=? AND record_id=?", boardId, recordId);
    }

    @Transactional(readOnly=true)
    public MapView view(long id) {
        Board b = find(id);
        var captures = db.query("""
                SELECT c.record_id,r.image_name,r.image_url,r.image_width,r.image_height,r.review_status,c.anchor_id,c.matches_count,
                       COALESCE(c.grid_row-1,a.grid_row-1+c.shift_y) AS top_pos,
                       COALESCE(c.grid_col-1,a.grid_col-1+c.shift_x) AS left_pos
                FROM board_capture c JOIN detect_record r ON r.id=c.record_id
                LEFT JOIN board_capture a ON a.record_id=c.anchor_id AND a.board_id=c.board_id
                WHERE c.board_id=? ORDER BY c.record_id
                """, (rs,i) -> {
            Number left=(Number)rs.getObject("left_pos"), top=(Number)rs.getObject("top_pos");
            Rect area = left==null || top==null ? null : new Rect(
                    Math.max(0, Math.min(left.doubleValue(), b.cols-1)) / b.cols, Math.max(0, Math.min(top.doubleValue(), b.rows-1)) / b.rows,
                    1.0/b.cols,1.0/b.rows);
            return new Capture(rs.getLong(1),rs.getString(2),rs.getString(3),(Integer)rs.getObject(4),
                    (Integer)rs.getObject(5),rs.getString(6),(Long)rs.getObject(7),(Integer)rs.getObject(8),area);
        }, id);
        Map<Long,Capture> byId = new HashMap<>();
        captures.forEach(c -> byId.put(c.recordId,c));
        var boxes = db.query("""
                SELECT c.record_id,d.class_name,d.x1,d.y1,d.x2,d.y2 FROM board_capture c
                JOIN detect_record r ON r.id=c.record_id JOIN detect_detail d ON c.record_id=d.record_id
                WHERE c.board_id=? AND COALESCE(r.review_status,'UNREVIEWED') NOT IN ('INCORRECT','CORRECTED')
                UNION ALL
                SELECT c.record_id,d.class_name,d.x1,d.y1,d.x2,d.y2 FROM board_capture c
                JOIN detect_record r ON r.id=c.record_id JOIN detect_review_annotation d ON c.record_id=d.record_id
                WHERE c.board_id=? AND r.review_status='CORRECTED' ORDER BY 1,2,3
                """, (rs,i) -> {
            Capture c = byId.get(rs.getLong(1));
            Rect a = c.area, mapped = null;
            if (a != null && c.pixelsX != null && c.pixelsY != null && c.pixelsX > 0 && c.pixelsY > 0) {
                double x1=rs.getDouble(3)/c.pixelsX, y1=rs.getDouble(4)/c.pixelsY;
                double x2=rs.getDouble(5)/c.pixelsX, y2=rs.getDouble(6)/c.pixelsY;
                mapped = new Rect(a.x+x1*a.width,a.y+y1*a.height,(x2-x1)*a.width,(y2-y1)*a.height);
            }
            return new Box(c.recordId,rs.getString(2),mapped);
        }, id,id);
        return new MapView(b,captures,boxes);
    }
}

