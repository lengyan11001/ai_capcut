package com.novel.app.web;

import com.novel.app.service.ReadingService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/reading/progress")
public class ReadingController {
    private final ReadingService readingService;
    private final AuthHeaderSupport authHeaderSupport;

    public ReadingController(ReadingService readingService, AuthHeaderSupport authHeaderSupport) {
        this.readingService = readingService;
        this.authHeaderSupport = authHeaderSupport;
    }

    @PostMapping("/save")
    public ApiResponse<?> save(@RequestHeader("Authorization") String authorization, @RequestBody Map<String, Object> body) {
        Long userId = authHeaderSupport.requiredUserId(authorization);
        String bookId = String.valueOf(body.get("bookId"));
        String chapterId = String.valueOf(body.get("chapterId"));
        Integer offsetChar = body.get("offsetChar") == null ? 0 : Integer.parseInt(String.valueOf(body.get("offsetChar")));
        return ApiResponse.ok(readingService.save(userId, bookId, chapterId, offsetChar));
    }

    @GetMapping("/get")
    public ApiResponse<?> get(@RequestHeader("Authorization") String authorization, @RequestParam String bookId) {
        Long userId = authHeaderSupport.requiredUserId(authorization);
        return ApiResponse.ok(readingService.get(userId, bookId));
    }
}
