package com.novel.app.model;

import jakarta.persistence.*;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "reading_progress", uniqueConstraints = {
        @UniqueConstraint(name = "uk_user_book_progress", columnNames = {"userId", "bookId"})
})
public class ReadingProgressEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long userId;

    @Column(nullable = false, length = 64)
    private String bookId;

    @Column(nullable = false, length = 64)
    private String chapterId;

    @Column(nullable = false)
    private Integer offsetChar = 0;

    @Column(nullable = false)
    private LocalDateTime updatedAt = LocalDateTime.now();
}
