package com.codeturret.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "gemini")
@Data
public class GeminiProperties {
    private String apiKey;
    private String baseUrl;
    private Model model = new Model();
    private int timeoutSeconds = 60;
    private int maxRetries = 2;
    private long rateLimitDelayMs = 7000;
    private double deepScanThreshold = 0.7;

    @Data
    public static class Model {
        private String flash = "gemini-2.0-flash";
        private String pro = "gemini-2.5-pro";
    }
}
