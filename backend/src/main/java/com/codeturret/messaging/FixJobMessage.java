package com.codeturret.messaging;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class FixJobMessage {
    private String scanId;
    private String repoId;
}
