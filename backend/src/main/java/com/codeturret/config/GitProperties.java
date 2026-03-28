package com.codeturret.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "git")
@Data
public class GitProperties {
    private int cloneDepth = 50;
    private int maxCommits = 50;
    private int maxScanFiles = 25;
    private int maxFileSize = 50000;
}
