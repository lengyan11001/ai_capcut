package com.novel.app.web;

import com.novel.app.service.ContentService;
import org.springframework.web.bind.annotation.*;

@RestController
public class ContentController {
    private final ContentService contentService;

    public ContentController(ContentService contentService) {
        this.contentService = contentService;
    }

    @GetMapping("/home/feed")
    public ApiResponse<?> feed() {
        return ApiResponse.ok(contentService.homeFeed());
    }

    @GetMapping("/books/{bookId}")
    public ApiResponse<?> bookDetail(@PathVariable String bookId) {
        return ApiResponse.ok(contentService.bookDetail(bookId));
    }

    @GetMapping("/books/{bookId}/chapters")
    public ApiResponse<?> chapterList(@PathVariable String bookId) {
        return ApiResponse.ok(contentService.chapterList(bookId));
    }

    @GetMapping("/chapters/{chapterId}/content")
    public ApiResponse<?> chapterContent(@PathVariable String chapterId) {
        return ApiResponse.ok(contentService.chapterContent(chapterId));
    }
}
