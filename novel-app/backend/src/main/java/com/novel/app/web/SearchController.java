package com.novel.app.web;

import com.novel.app.service.ContentService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class SearchController {
    private final ContentService contentService;

    public SearchController(ContentService contentService) {
        this.contentService = contentService;
    }

    @GetMapping("/search/suggest")
    public ApiResponse<?> suggest(@RequestParam String keyword) {
        return ApiResponse.ok(contentService.suggest(keyword));
    }

    @GetMapping("/search/result")
    public ApiResponse<?> result(@RequestParam String keyword) {
        return ApiResponse.ok(contentService.search(keyword));
    }
}
