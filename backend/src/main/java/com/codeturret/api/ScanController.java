package com.codeturret.api;

import com.codeturret.api.dto.ScanRequest;
import com.codeturret.messaging.RabbitConfig;
import com.codeturret.messaging.ScanJobMessage;
import com.codeturret.model.Repository;
import com.codeturret.model.Scan;
import com.codeturret.model.ScanStatus;
import com.codeturret.repository.RepositoryRepo;
import com.codeturret.repository.ScanRepo;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/scans")
@RequiredArgsConstructor
public class ScanController {

    private final ScanRepo scanRepo;
    private final RepositoryRepo repoRepo;
    private final RabbitTemplate rabbitTemplate;

    @PostMapping
    public ResponseEntity<Map<String, Object>> triggerScan(@Valid @RequestBody ScanRequest request) {
        // Find or create repo record
        String repoName = request.getRepoName() != null && !request.getRepoName().isBlank()
            ? request.getRepoName()
            : extractRepoName(request.getRepoUrl());

        Repository repo = repoRepo.findByName(repoName).orElseGet(() -> {
            Repository r = new Repository();
            r.setName(repoName);
            r.setUrl(request.getRepoUrl());
            return repoRepo.save(r);
        });

        // Create scan record (QUEUED)
        Scan scan = new Scan();
        scan.setRepository(repo);
        scan.setStatus(ScanStatus.QUEUED);
        scan.setScanType(request.isDeepScan() ? "DEEP" : "FULL");
        scan = scanRepo.save(scan);

        // Enqueue job
        ScanJobMessage msg = new ScanJobMessage(scan.getId().toString(), repo.getId().toString(), request.isDeepScan());
        rabbitTemplate.convertAndSend(RabbitConfig.SCAN_REQUESTS_EXCHANGE, RabbitConfig.SCAN_ROUTING_KEY, msg);

        return ResponseEntity.status(HttpStatus.ACCEPTED).body(Map.of(
            "scanId", scan.getId(),
            "status", "QUEUED",
            "streamUrl", "/api/scans/" + scan.getId() + "/stream"
        ));
    }

    @GetMapping
    public List<Map<String, Object>> listScans(@RequestParam(defaultValue = "10") int limit) {
        int cap = Math.min(Math.max(limit, 1), 100);
        return scanRepo.findRecentScans(PageRequest.of(0, cap)).stream()
            .map(s -> Map.<String, Object>of(
                "scanId", s.getId(),
                "repoName", s.getRepository().getName(),
                "repoUrl", s.getRepository().getUrl(),
                "status", s.getStatus(),
                "scanType", s.getScanType(),
                "totalFiles", s.getTotalFiles(),
                "findingsCount", s.getFindingsCount(),
                "startedAt", s.getStartedAt() != null ? s.getStartedAt() : "",
                "completedAt", s.getCompletedAt() != null ? s.getCompletedAt() : ""
            ))
            .toList();
    }

    @GetMapping("/{id}")
    public Map<String, Object> getScan(@PathVariable UUID id) {
        Scan s = scanRepo.findById(id)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Scan not found"));
        return Map.of(
            "scanId", s.getId(),
            "repoName", s.getRepository().getName(),
            "status", s.getStatus(),
            "scanType", s.getScanType(),
            "totalFiles", s.getTotalFiles(),
            "findingsCount", s.getFindingsCount(),
            "startedAt", s.getStartedAt() != null ? s.getStartedAt() : "",
            "completedAt", s.getCompletedAt() != null ? s.getCompletedAt() : "",
            "errorMessage", s.getErrorMessage() != null ? s.getErrorMessage() : ""
        );
    }

    private String extractRepoName(String url) {
        String trimmed = url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
        int slash = trimmed.lastIndexOf('/');
        return slash >= 0 ? trimmed.substring(slash + 1) : trimmed;
    }
}
