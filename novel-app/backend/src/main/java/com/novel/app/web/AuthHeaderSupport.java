package com.novel.app.web;

import com.novel.app.security.JwtTokenService;
import io.jsonwebtoken.Claims;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

@Component
public class AuthHeaderSupport {
    private final JwtTokenService jwtTokenService;

    public AuthHeaderSupport(JwtTokenService jwtTokenService) {
        this.jwtTokenService = jwtTokenService;
    }

    public Long requiredUserId(String authorization) {
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "missing token");
        }
        String token = authorization.substring("Bearer ".length());
        Claims claims = jwtTokenService.parse(token);
        return Long.valueOf(claims.getSubject());
    }
}
