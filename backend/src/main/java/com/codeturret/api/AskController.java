package com.codeturret.api;

import com.codeturret.api.dto.AskRequest;
import com.codeturret.model.Finding;
import com.codeturret.repository.FindingRepo;
import com.codeturret.service.GeminiService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/ask")
@RequiredArgsConstructor
public class AskController {

    private final FindingRepo findingRepo;
    private final GeminiService geminiService;

    @PostMapping
    public Map<String, String> ask(@Valid @RequestBody AskRequest request) {
        List<Finding> findings = findingRepo.findByScan_Id(UUID.fromString(request.getScanId()));

        StringBuilder summary = new StringBuilder();
        summary.append("Total findings: ").append(findings.size()).append("\n\n");
        for (Finding f : findings) {
            summary.append("[").append(f.getSeverity()).append("] ")
                .append(f.getVulnType()).append(" in ").append(f.getFilePath());
            if (f.getLineNumber() != null) summary.append(":").append(f.getLineNumber());
            summary.append("\n").append(f.getDescription()).append("\n");
            if (f.getCommitAuthor() != null && !f.getCommitAuthor().isBlank()) {
                summary.append("Last modified by: ").append(f.getCommitAuthor()).append("\n");
            }
            summary.append("\n");
        }

        String answer = geminiService.askAboutFindings(summary.toString(), request.getQuestion());
        return Map.of("answer", answer);
    }
}
