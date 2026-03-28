package com.codeturret.messaging;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ScanJobMessage {
    private String scanId;
    private String repoId;
    private boolean deepScan;
}
