package com.novel.app.service;

import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class OpsService {

    public List<Map<String, Object>> banners() {
        return List.of(
                Map.of("id", "bn_1", "imageUrl", "https://example.com/banner1.jpg", "jumpType", "book", "jumpValue", "bk_1001"),
                Map.of("id", "bn_2", "imageUrl", "https://example.com/banner2.jpg", "jumpType", "url", "jumpValue", "https://example.com/activity")
        );
    }

    public List<Map<String, Object>> channels() {
        return List.of(
                Map.of("id", "cn_1", "name", "男生频道"),
                Map.of("id", "cn_2", "name", "女生频道"),
                Map.of("id", "cn_3", "name", "新书速递")
        );
    }
}
