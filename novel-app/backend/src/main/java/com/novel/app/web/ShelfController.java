package com.novel.app.web;

import com.novel.app.service.ShelfService;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/shelf")
public class ShelfController {
    private final ShelfService shelfService;
    private final AuthHeaderSupport authHeaderSupport;

    public ShelfController(ShelfService shelfService, AuthHeaderSupport authHeaderSupport) {
        this.shelfService = shelfService;
        this.authHeaderSupport = authHeaderSupport;
    }

    @GetMapping("/list")
    public ApiResponse<?> list(@RequestHeader("Authorization") String authorization) {
        Long userId = authHeaderSupport.requiredUserId(authorization);
        return ApiResponse.ok(shelfService.list(userId));
    }

    @PostMapping("/add")
    public ApiResponse<?> add(@RequestHeader("Authorization") String authorization, @RequestBody Map<String, String> body) {
        Long userId = authHeaderSupport.requiredUserId(authorization);
        shelfService.add(userId, body.get("bookId"), body.get("bookTitle"));
        return ApiResponse.ok(Map.of("success", true));
    }

    @PostMapping("/remove")
    public ApiResponse<?> remove(@RequestHeader("Authorization") String authorization, @RequestBody Map<String, String> body) {
        Long userId = authHeaderSupport.requiredUserId(authorization);
        shelfService.remove(userId, body.get("bookId"));
        return ApiResponse.ok(Map.of("success", true));
    }
}
