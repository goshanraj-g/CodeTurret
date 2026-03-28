package com.codeturret.messaging;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ProgressEvent {
    private String scanId;
    private String event;
    private Instant timestamp = Instant.now();
    private Map<String, Object> data;

    public static ProgressEvent of(String scanId, String event, Map<String, Object> data) {
        return new ProgressEvent(scanId, event, Instant.now(), data);
    }
}
