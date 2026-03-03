package com.novel.app.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "novel")
public class NovelProperties {
    private Jwt jwt = new Jwt();
    private Content content = new Content();
    private Payment payment = new Payment();
    private RateLimit rateLimit = new RateLimit();

    @Data
    public static class Jwt {
        private String secret;
        private long accessExpireMinutes;
        private long refreshExpireDays;
    }

    @Data
    public static class Content {
        private String baseUrl;
        private String appKey;
        private String appSecret;
        private int timeoutMillis;
    }

    @Data
    public static class Payment {
        private String callbackSecret;
    }

    @Data
    public static class RateLimit {
        private int requestsPerMinute;
    }
}
