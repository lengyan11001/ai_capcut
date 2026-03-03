package com.novel.app.security;

import com.novel.app.config.NovelProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.Map;

@Service
public class JwtTokenService {
    private final NovelProperties properties;
    private SecretKey key;

    public JwtTokenService(NovelProperties properties) {
        this.properties = properties;
    }

    @PostConstruct
    void init() {
        byte[] bytes = properties.getJwt().getSecret().getBytes(StandardCharsets.UTF_8);
        this.key = Keys.hmacShaKeyFor(bytes);
    }

    public String generateAccessToken(Long userId) {
        Instant expireAt = Instant.now().plus(properties.getJwt().getAccessExpireMinutes(), ChronoUnit.MINUTES);
        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claims(Map.of("type", "access"))
                .issuedAt(new Date())
                .expiration(Date.from(expireAt))
                .signWith(key)
                .compact();
    }

    public String generateRefreshToken(Long userId) {
        Instant expireAt = Instant.now().plus(properties.getJwt().getRefreshExpireDays(), ChronoUnit.DAYS);
        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claims(Map.of("type", "refresh"))
                .issuedAt(new Date())
                .expiration(Date.from(expireAt))
                .signWith(key)
                .compact();
    }

    public Claims parse(String token) {
        return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
    }
}
