package com.codeturret.api.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class ScanRequest {
    @NotBlank
    private String repoUrl;
    private boolean deepScan = false;
    private String repoName;
}
