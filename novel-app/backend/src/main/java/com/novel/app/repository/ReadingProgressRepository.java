package com.novel.app.repository;

import com.novel.app.model.ReadingProgressEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface ReadingProgressRepository extends JpaRepository<ReadingProgressEntity, Long> {
    Optional<ReadingProgressEntity> findByUserIdAndBookId(Long userId, String bookId);
}
