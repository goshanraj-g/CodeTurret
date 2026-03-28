package com.codeturret.api.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class RepoRequest {
    @NotBlank
    private String name;
    @NotBlank
    private String url;
    private String githubToken; // Optional; required for auto-fix PRs
}
