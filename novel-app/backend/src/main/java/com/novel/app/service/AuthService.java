package com.novel.app.service;

import com.novel.app.model.UserEntity;
import com.novel.app.repository.UserRepository;
import com.novel.app.security.JwtTokenService;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class AuthService {
    private final UserRepository userRepository;
    private final JwtTokenService jwtTokenService;

    public AuthService(UserRepository userRepository, JwtTokenService jwtTokenService) {
        this.userRepository = userRepository;
        this.jwtTokenService = jwtTokenService;
    }

    public Map<String, Object> smsLogin(String phone, String code) {
        if (!"123456".equals(code)) {
            throw new IllegalArgumentException("invalid code");
        }
        UserEntity user = userRepository.findByPhone(phone).orElseGet(() -> {
            UserEntity entity = new UserEntity();
            entity.setPhone(phone);
            entity.setNickname("书友" + phone.substring(Math.max(0, phone.length() - 4)));
            return userRepository.save(entity);
        });
        String accessToken = jwtTokenService.generateAccessToken(user.getId());
        String refreshToken = jwtTokenService.generateRefreshToken(user.getId());
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("userId", user.getId());
        data.put("nickname", user.getNickname());
        data.put("accessToken", accessToken);
        data.put("refreshToken", refreshToken);
        return data;
    }

    public Map<String, Object> refresh(String refreshToken) {
        Long userId = Long.valueOf(jwtTokenService.parse(refreshToken).getSubject());
        UserEntity user = userRepository.findById(userId).orElseThrow();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("userId", user.getId());
        data.put("accessToken", jwtTokenService.generateAccessToken(userId));
        return data;
    }

    public UserEntity profile(Long userId) {
        return userRepository.findById(userId).orElseThrow();
    }
}
