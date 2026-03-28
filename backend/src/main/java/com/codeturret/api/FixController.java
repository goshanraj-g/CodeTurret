package com.codeturret.api;

import com.codeturret.messaging.FixJobMessage;
import com.codeturret.messaging.RabbitConfig;
import com.codeturret.model.FixPr;
import com.codeturret.model.Scan;
import com.codeturret.model.ScanStatus;
import com.codeturret.repository.FixPrRepo;
import com.codeturret.repository.ScanRepo;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@RestController
@RequestMapping("/api/scans")
@RequiredArgsConstructor
public class FixController {

    private final ScanRepo scanRepo;
    private final FixPrRepo fixPrRepo;
    private final RabbitTemplate rabbitTemplate;

    /** Trigger auto-fix PR generation for a completed scan. */
    @PostMapping("/{id}/fix")
    public ResponseEntity<Map<String, Object>> triggerFix(@PathVariable UUID id) {
        Scan scan = scanRepo.findById(id)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Scan not found"));

        if (scan.getStatus() != ScanStatus.COMPLETED) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Scan is not completed yet");
        }

        if (scan.getFindingsCount() == 0) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Scan has no findings to fix");
        }

        // Check if a fix PR already exists
        Optional<FixPr> existing = fixPrRepo.findByScan_Id(id);
        if (existing.isPresent() && !"FAILED".equals(existing.get().getStatus())) {
            return ResponseEntity.ok(Map.of(
                "message", "Fix PR already exists",
                "prUrl", existing.get().getPrUrl() != null ? existing.get().getPrUrl() : "",
                "status", existing.get().getStatus()
            ));
        }

        FixJobMessage msg = new FixJobMessage(id.toString(), scan.getRepository().getId().toString());
        rabbitTemplate.convertAndSend(RabbitConfig.FIX_REQUESTS_EXCHANGE, RabbitConfig.FIX_ROUTING_KEY, msg);

        return ResponseEntity.status(HttpStatus.ACCEPTED).body(Map.of(
            "message", "Fix job queued",
            "scanId", id,
            "streamUrl", "/api/scans/" + id + "/stream"
        ));
    }

    /** Get the fix PR status for a scan. */
    @GetMapping("/{id}/fix")
    public Map<String, Object> getFixStatus(@PathVariable UUID id) {
        FixPr pr = fixPrRepo.findByScan_Id(id)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "No fix PR found for this scan"));

        return Map.of(
            "id", pr.getId(),
            "scanId", id,
            "prUrl", pr.getPrUrl() != null ? pr.getPrUrl() : "",
            "branchName", pr.getBranchName() != null ? pr.getBranchName() : "",
            "filesFixed", pr.getFilesFixed(),
            "findingsFixed", pr.getFindingsFixed(),
            "status", pr.getStatus(),
            "createdAt", pr.getCreatedAt()
        );
    }
}
