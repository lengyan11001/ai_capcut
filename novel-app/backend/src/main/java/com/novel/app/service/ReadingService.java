package com.novel.app.service;

import com.novel.app.model.ReadingProgressEntity;
import com.novel.app.repository.ReadingProgressRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Service
public class ReadingService {
    private final ReadingProgressRepository readingProgressRepository;

    public ReadingService(ReadingProgressRepository readingProgressRepository) {
        this.readingProgressRepository = readingProgressRepository;
    }

    public ReadingProgressEntity save(Long userId, String bookId, String chapterId, Integer offsetChar) {
        ReadingProgressEntity entity = readingProgressRepository.findByUserIdAndBookId(userId, bookId)
                .orElseGet(ReadingProgressEntity::new);
        entity.setUserId(userId);
        entity.setBookId(bookId);
        entity.setChapterId(chapterId);
        entity.setOffsetChar(offsetChar == null ? 0 : offsetChar);
        entity.setUpdatedAt(LocalDateTime.now());
        return readingProgressRepository.save(entity);
    }

    public ReadingProgressEntity get(Long userId, String bookId) {
        return readingProgressRepository.findByUserIdAndBookId(userId, bookId).orElse(null);
    }
}
