package com.codeturret.api;

import com.codeturret.messaging.ProgressEvent;
import com.codeturret.messaging.RabbitConfig;
import com.codeturret.model.Scan;
import com.codeturret.repository.ScanRepo;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitAdmin;
import org.springframework.amqp.rabbit.listener.SimpleMessageListenerContainer;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/scans")
@RequiredArgsConstructor
@Slf4j
public class SseController {

    private final ScanRepo scanRepo;
    private final ConnectionFactory connectionFactory;
    private final RabbitAdmin rabbitAdmin;
    private final TopicExchange scanProgressExchange;
    private final ObjectMapper objectMapper;

    @GetMapping(value = "/{id}/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream(@PathVariable UUID id) {
        Scan scan = scanRepo.findById(id)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Scan not found"));

        SseEmitter emitter = new SseEmitter(3_600_000L); // 1 hour

        // Seed event for late-join (client reconnects after scan started)
        try {
            ProgressEvent seed = ProgressEvent.of(id.toString(), "SCAN_STATUS", Map.of(
                "status", scan.getStatus().toString(),
                "totalFiles", scan.getTotalFiles(),
                "findingsCount", scan.getFindingsCount()
            ));
            emitter.send(SseEmitter.event().name("SCAN_STATUS").data(seed));

            // If already terminal, complete immediately
            if (scan.getStatus().name().equals("COMPLETED") || scan.getStatus().name().equals("FAILED")) {
                emitter.complete();
                return emitter;
            }
        } catch (IOException e) {
            emitter.completeWithError(e);
            return emitter;
        }

        // Create per-connection auto-delete queue
        String queueName = "scan.progress." + id + "." + UUID.randomUUID();
        Queue queue = QueueBuilder.nonDurable(queueName).autoDelete().exclusive().build();
        rabbitAdmin.declareQueue(queue);
        rabbitAdmin.declareBinding(BindingBuilder.bind(queue)
            .to(scanProgressExchange)
            .with("scan." + id + ".*"));

        // Listener container forwards RabbitMQ messages to SSE stream
        SimpleMessageListenerContainer container = new SimpleMessageListenerContainer(connectionFactory);
        container.setQueueNames(queueName);
        container.setMessageListener(msg -> {
            try {
                ProgressEvent event = objectMapper.readValue(msg.getBody(), ProgressEvent.class);
                emitter.send(SseEmitter.event().name(event.getEvent()).data(event));

                // Terminal events close the stream
                if (isTerminal(event.getEvent())) {
                    emitter.complete();
                }
            } catch (Exception e) {
                log.warn("SSE send failed for scan {}: {}", id, e.getMessage());
                emitter.completeWithError(e);
            }
        });
        container.start();

        Runnable cleanup = () -> {
            container.stop();
            try { rabbitAdmin.deleteQueue(queueName); } catch (Exception ignored) {}
        };

        emitter.onCompletion(cleanup);
        emitter.onTimeout(cleanup);
        emitter.onError(e -> cleanup.run());

        return emitter;
    }

    private boolean isTerminal(String event) {
        return "SCAN_COMPLETE".equals(event) || "SCAN_FAILED".equals(event) || "PR_CREATED".equals(event);
    }
}
