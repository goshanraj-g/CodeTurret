package com.codeturret.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "fix_prs")
@Data
@NoArgsConstructor
public class FixPr {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "scan_id", nullable = false)
    private Scan scan;

    @Column(name = "pr_url")
    private String prUrl;

    @Column(name = "branch_name")
    private String branchName;

    @Column(name = "files_fixed")
    private int filesFixed = 0;

    @Column(name = "findings_fixed")
    private int findingsFixed = 0;

    @Column(nullable = false)
    private String status = "OPEN";

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt = Instant.now();
}
