package com.codeturret.repository;

import com.codeturret.model.FixPr;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface FixPrRepo extends JpaRepository<FixPr, UUID> {
    Optional<FixPr> findByScan_Id(UUID scanId);
}
