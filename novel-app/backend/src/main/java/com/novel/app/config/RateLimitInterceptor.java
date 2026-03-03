package com.novel.app.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

@Component
public class RateLimitInterceptor implements HandlerInterceptor {
    private final NovelProperties novelProperties;
    private final Map<String, WindowCounter> counters = new ConcurrentHashMap<>();

    public RateLimitInterceptor(NovelProperties novelProperties) {
        this.novelProperties = novelProperties;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String key = request.getRemoteAddr();
        long minute = System.currentTimeMillis() / 60000;
        WindowCounter counter = counters.computeIfAbsent(key, k -> new WindowCounter(minute));
        synchronized (counter) {
            if (counter.minute != minute) {
                counter.minute = minute;
                counter.count.set(0);
            }
            if (counter.count.incrementAndGet() > novelProperties.getRateLimit().getRequestsPerMinute()) {
                response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
                response.setContentType("application/json;charset=UTF-8");
                response.getWriter().write("{\"code\":429,\"message\":\"too many requests\",\"data\":null}");
                return false;
            }
        }
        return true;
    }

    private static class WindowCounter {
        long minute;
        AtomicInteger count = new AtomicInteger(0);

        WindowCounter(long minute) {
            this.minute = minute;
        }
    }
}
