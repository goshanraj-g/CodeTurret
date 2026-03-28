package com.codeturret.api;

import com.codeturret.api.dto.AskRequest;
import com.codeturret.repository.FindingRepo;
import com.codeturret.service.CortexService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/ask")
@RequiredArgsConstructor
public class AskController {

    private final FindingRepo findingRepo;
    private final CortexService cortexService;

    @PostMapping
    public Map<String, String> ask(@Valid @RequestBody AskRequest request) {
        var findings = findingRepo.findByScan_Id(UUID.fromString(request.getScanId()));
        String answer = cortexService.askAboutFindings(findings, request.getQuestion());
        return Map.of("answer", answer);
    }
}
