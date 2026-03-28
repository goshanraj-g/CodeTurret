package com.codeturret.api.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class AskRequest {
    @NotBlank
    private String scanId;
    @NotBlank
    private String question;
}
