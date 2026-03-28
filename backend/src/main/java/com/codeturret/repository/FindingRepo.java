package com.codeturret.repository;

import com.codeturret.model.Finding;
import com.codeturret.model.Severity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.UUID;

public interface FindingRepo extends JpaRepository<Finding, UUID> {

    @Query("""
        SELECT f FROM Finding f
        WHERE f.scan.id = :scanId
        ORDER BY
          CASE f.severity
            WHEN com.codeturret.model.Severity.CRITICAL THEN 1
            WHEN com.codeturret.model.Severity.HIGH     THEN 2
            WHEN com.codeturret.model.Severity.MEDIUM   THEN 3
            ELSE 4
          END,
          f.confidence DESC
        """)
    List<Finding> findByScanIdOrdered(UUID scanId);

    List<Finding> findByScan_Id(UUID scanId);

    @Query("SELECT f FROM Finding f WHERE f.scan.id = :scanId AND f.fixSuggestion IS NOT NULL AND f.fixSuggestion != ''")
    List<Finding> findFixableByScanId(UUID scanId);
}
