package com.novel.app.service;

import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class ContentService {
    private final ContentProviderClient contentProviderClient;

    public ContentService(ContentProviderClient contentProviderClient) {
        this.contentProviderClient = contentProviderClient;
    }

    @Cacheable(cacheNames = "homeFeed", key = "'home'")
    public List<Map<String, Object>> homeFeed() {
        return contentProviderClient.homeFeed();
    }

    @Cacheable(cacheNames = "bookDetail", key = "#bookId")
    public Map<String, Object> bookDetail(String bookId) {
        return contentProviderClient.bookDetail(bookId);
    }

    @Cacheable(cacheNames = "chapters", key = "#bookId")
    public List<Map<String, Object>> chapterList(String bookId) {
        return contentProviderClient.chapterList(bookId);
    }

    @Cacheable(cacheNames = "chapterContent", key = "#chapterId")
    public Map<String, Object> chapterContent(String chapterId) {
        return contentProviderClient.chapterContent(chapterId);
    }

    public List<String> suggest(String keyword) {
        return contentProviderClient.suggest(keyword);
    }

    public List<Map<String, Object>> search(String keyword) {
        return contentProviderClient.search(keyword);
    }
}
