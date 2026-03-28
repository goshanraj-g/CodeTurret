package com.codeturret.api;

import com.codeturret.model.Finding;
import com.codeturret.repository.FindingRepo;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/findings")
@RequiredArgsConstructor
public class FindingController {

    private final FindingRepo findingRepo;

    @GetMapping("/{scanId}")
    public List<Map<String, Object>> getFindingsForScan(@PathVariable UUID scanId) {
        return findingRepo.findByScanIdOrdered(scanId).stream()
            .map(this::toMap)
            .toList();
    }

    private Map<String, Object> toMap(Finding f) {
        return Map.ofEntries(
            Map.entry("id",           f.getId()),
            Map.entry("scanId",       f.getScan().getId()),
            Map.entry("filePath",     f.getFilePath()),
            Map.entry("lineNumber",   f.getLineNumber() != null ? f.getLineNumber() : 0),
            Map.entry("severity",     f.getSeverity()),
            Map.entry("vulnType",     f.getVulnType()),
            Map.entry("description",  f.getDescription() != null ? f.getDescription() : ""),
            Map.entry("fixSuggestion",f.getFixSuggestion() != null ? f.getFixSuggestion() : ""),
            Map.entry("codeSnippet",  f.getCodeSnippet() != null ? f.getCodeSnippet() : ""),
            Map.entry("modelUsed",    f.getModelUsed() != null ? f.getModelUsed() : ""),
            Map.entry("confidence",   f.getConfidence() != null ? f.getConfidence() : 0.0),
            Map.entry("commitHash",   f.getCommitHash() != null ? f.getCommitHash() : ""),
            Map.entry("commitAuthor", f.getCommitAuthor() != null ? f.getCommitAuthor() : ""),
            Map.entry("createdAt",    f.getCreatedAt())
        );
    }
}
