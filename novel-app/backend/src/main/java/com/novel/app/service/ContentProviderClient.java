package com.novel.app.service;

import com.novel.app.config.NovelProperties;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.*;

@Component
public class ContentProviderClient {
    private final NovelProperties novelProperties;
    private final RestClient restClient;

    public ContentProviderClient(NovelProperties novelProperties) {
        this.novelProperties = novelProperties;
        this.restClient = RestClient.builder()
                .baseUrl(novelProperties.getContent().getBaseUrl())
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .build();
    }

    public List<Map<String, Object>> homeFeed() {
        return fallback(() -> restClient.get()
                .uri("/home/feed")
                .header("X-App-Key", novelProperties.getContent().getAppKey())
                .retrieve()
                .body(new ParameterizedTypeReference<>() {}), mockFeed());
    }

    public Map<String, Object> bookDetail(String bookId) {
        return fallback(() -> restClient.get()
                .uri("/books/{bookId}", bookId)
                .header("X-App-Key", novelProperties.getContent().getAppKey())
                .retrieve()
                .body(new ParameterizedTypeReference<>() {}), book(bookId, "示例小说 " + bookId, "都市", "https://example.com/cover-default.jpg"));
    }

    public List<Map<String, Object>> chapterList(String bookId) {
        return fallback(() -> restClient.get()
                .uri("/books/{bookId}/chapters", bookId)
                .header("X-App-Key", novelProperties.getContent().getAppKey())
                .retrieve()
                .body(new ParameterizedTypeReference<>() {}), mockChapters(bookId));
    }

    public Map<String, Object> chapterContent(String chapterId) {
        return fallback(() -> restClient.get()
                .uri("/chapters/{chapterId}/content", chapterId)
                .header("X-App-Key", novelProperties.getContent().getAppKey())
                .retrieve()
                .body(new ParameterizedTypeReference<>() {}), Map.of(
                "chapterId", chapterId,
                "title", chapterId + " 标题",
                "content", "这是章节内容示例。为了演示阅读器和缓存流程，这里返回了 mock 文本。\n\n可替换为第三方正版内容 API 的真实响应。"
        ));
    }

    public List<String> suggest(String keyword) {
        return fallback(() -> restClient.get()
                .uri(uriBuilder -> uriBuilder.path("/search/suggest").queryParam("keyword", keyword).build())
                .header("X-App-Key", novelProperties.getContent().getAppKey())
                .retrieve()
                .body(new ParameterizedTypeReference<>() {}), List.of(keyword + "推荐1", keyword + "推荐2", keyword + "推荐3"));
    }

    public List<Map<String, Object>> search(String keyword) {
        return fallback(() -> restClient.get()
                .uri(uriBuilder -> uriBuilder.path("/search/result").queryParam("keyword", keyword).build())
                .header("X-App-Key", novelProperties.getContent().getAppKey())
                .retrieve()
                .body(new ParameterizedTypeReference<>() {}), List.of(
                book("search_1", keyword + " 相关小说A", "都市", "https://example.com/s1.jpg"),
                book("search_2", keyword + " 相关小说B", "玄幻", "https://example.com/s2.jpg")
        ));
    }

    private List<Map<String, Object>> mockFeed() {
        return List.of(
                book("bk_1001", "万古第一神", "玄幻", "https://example.com/cover1.jpg"),
                book("bk_1002", "剑来", "仙侠", "https://example.com/cover2.jpg"),
                book("bk_1003", "诡秘之主", "奇幻", "https://example.com/cover3.jpg")
        );
    }

    private List<Map<String, Object>> mockChapters(String bookId) {
        List<Map<String, Object>> list = new ArrayList<>();
        for (int i = 1; i <= 30; i++) {
            list.add(Map.of("chapterId", bookId + "_ch_" + i, "title", "第" + i + "章", "wordCount", 2200 + i * 3));
        }
        return list;
    }

    private Map<String, Object> book(String id, String title, String category, String coverUrl) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("bookId", id);
        data.put("title", title);
        data.put("category", category);
        data.put("coverUrl", coverUrl);
        data.put("author", "作者示例");
        data.put("intro", "这是一本用于 MVP 验证的示例书籍。");
        return data;
    }

    private <T> T fallback(SupplierWithException<T> supplier, T fallback) {
        try {
            T result = supplier.get();
            return result == null ? fallback : result;
        } catch (Exception ignored) {
            return fallback;
        }
    }

    @FunctionalInterface
    private interface SupplierWithException<T> {
        T get() throws Exception;
    }
}
