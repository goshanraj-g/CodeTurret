package com.codeturret.repository;

import com.codeturret.model.Repository;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface RepositoryRepo extends JpaRepository<Repository, UUID> {
    Optional<Repository> findByName(String name);
    boolean existsByName(String name);
}
