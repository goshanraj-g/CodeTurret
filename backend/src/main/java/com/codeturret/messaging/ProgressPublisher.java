package com.codeturret.messaging;

import lombok.RequiredArgsConstructor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
@RequiredArgsConstructor
public class ProgressPublisher {

    private final RabbitTemplate rabbitTemplate;

    /** Publish a progress event for a scan. Routing key: scan.{scanId}.{eventType} */
    public void publish(String scanId, String eventType, Map<String, Object> data) {
        ProgressEvent event = ProgressEvent.of(scanId, eventType, data);
        String routingKey = "scan." + scanId + "." + eventType.toLowerCase();
        rabbitTemplate.convertAndSend(RabbitConfig.SCAN_PROGRESS_EXCHANGE, routingKey, event);
    }

    public void scanStarted(String scanId, int totalFiles) {
        publish(scanId, "SCAN_STARTED", Map.of("totalFiles", totalFiles));
    }

    public void fileScanned(String scanId, String file, int findings, String topSeverity) {
        publish(scanId, "FILE_SCANNED", Map.of(
            "file", file,
            "findings", findings,
            "severity", topSeverity != null ? topSeverity : "NONE"
        ));
    }

    public void fileSkipped(String scanId, String file, String reason) {
        publish(scanId, "FILE_SKIPPED", Map.of("file", file, "reason", reason));
    }

    public void scanComplete(String scanId, int totalFindings) {
        publish(scanId, "SCAN_COMPLETE", Map.of("totalFindings", totalFindings));
    }

    public void scanFailed(String scanId, String error) {
        publish(scanId, "SCAN_FAILED", Map.of("error", error));
    }

    public void fixStarted(String scanId, int filesToFix) {
        publish(scanId, "FIX_STARTED", Map.of("filesToFix", filesToFix));
    }

    public void fileFixed(String scanId, String file, int findingsFixed) {
        publish(scanId, "FILE_FIXED", Map.of("file", file, "findingsFixed", findingsFixed));
    }

    public void fixFailed(String scanId, String file, String error) {
        publish(scanId, "FIX_FAILED", Map.of("file", file, "error", error));
    }

    public void prCreated(String scanId, String prUrl, String branch, int filesFixed) {
        publish(scanId, "PR_CREATED", Map.of("prUrl", prUrl, "branch", branch, "filesFixed", filesFixed));
    }
}
