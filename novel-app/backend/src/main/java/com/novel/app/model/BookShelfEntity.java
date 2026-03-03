package com.novel.app.model;

import jakarta.persistence.*;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "book_shelf", uniqueConstraints = {
        @UniqueConstraint(name = "uk_user_book", columnNames = {"userId", "bookId"})
})
public class BookShelfEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long userId;

    @Column(nullable = false, length = 64)
    private String bookId;

    @Column(nullable = false, length = 120)
    private String bookTitle;

    @Column(nullable = false)
    private LocalDateTime updatedAt = LocalDateTime.now();
}
