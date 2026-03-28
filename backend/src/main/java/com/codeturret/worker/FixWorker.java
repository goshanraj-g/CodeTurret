package com.codeturret.worker;

import com.codeturret.messaging.FixJobMessage;
import com.codeturret.messaging.ProgressPublisher;
import com.codeturret.messaging.RabbitConfig;
import com.codeturret.model.Finding;
import com.codeturret.model.FixPr;
import com.codeturret.model.Repository;
import com.codeturret.model.Scan;
import com.codeturret.repository.FindingRepo;
import com.codeturret.repository.FixPrRepo;
import com.codeturret.repository.ScanRepo;
import com.codeturret.service.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.*;

@Component
@RequiredArgsConstructor
@Slf4j
public class FixWorker {

    private final ScanRepo scanRepo;
    private final FindingRepo findingRepo;
    private final FixPrRepo fixPrRepo;
    private final AutoFixService autoFixService;
    private final GitHubService gitHubService;
    private final GitService gitService;
    private final EncryptionService encryptionService;
    private final ProgressPublisher progress;

    @RabbitListener(queues = RabbitConfig.FIX_QUEUE)
    @Transactional
    public void handleFixJob(FixJobMessage msg) {
        String scanId = msg.getScanId();
        log.info("Starting fix job for scan: {}", scanId);

        Scan scan = scanRepo.findById(UUID.fromString(scanId)).orElse(null);
        if (scan == null) {
            log.error("Scan not found for fix job: {}", scanId);
            return;
        }

        Repository repo = scan.getRepository();

        // Require a GitHub token
        if (repo.getGithubToken() == null || repo.getGithubToken().isBlank()) {
            log.error("No GitHub token for repo {}", repo.getName());
            progress.fixFailed(scanId, "all", "No GitHub token configured for this repository");
            return;
        }

        String pat = encryptionService.decrypt(repo.getGithubToken());
        String[] ownerRepo = gitHubService.parseOwnerRepo(repo.getUrl());
        String owner = ownerRepo[0];
        String repoName = ownerRepo[1];

        // Load fixable findings (those with fix_suggestion)
        List<Finding> fixableFindings = findingRepo.findFixableByScanId(UUID.fromString(scanId));
        if (fixableFindings.isEmpty()) {
            log.info("No fixable findings for scan {}", scanId);
            return;
        }

        Map<String, List<Finding>> byFile = autoFixService.groupByFile(fixableFindings);
        progress.fixStarted(scanId, byFile.size());

        // Fetch current file contents from GitHub
        Map<String, String> fileContents = new HashMap<>();
        for (String filePath : byFile.keySet()) {
            try {
                String content = fetchFileFromGitHub(owner, repoName, filePath, pat);
                fileContents.put(filePath, content);
            } catch (Exception e) {
                log.warn("Could not fetch {} from GitHub: {}", filePath, e.getMessage());
            }
        }

        // Generate AI patches
        List<AutoFixService.FileFixResult> fixResults = autoFixService.generateFixes(byFile, fileContents);

        // Create branch
        String scanIdShort = scanId.substring(0, 8);
        String branchName;
        try {
            branchName = gitHubService.createFixBranch(owner, repoName, pat, scanIdShort);
        } catch (Exception e) {
            log.error("Failed to create fix branch: {}", e.getMessage());
            progress.fixFailed(scanId, "branch", "Could not create branch: " + e.getMessage());
            persistFailedPr(scan, "FAILED");
            return;
        }

        // Push each fixed file
        int filesFixed = 0;
        int findingsFixed = 0;
        for (AutoFixService.FileFixResult result : fixResults) {
            if (result.patchedContent() == null) {
                progress.fixFailed(scanId, result.filePath(), result.error());
                continue;
            }
            try {
                gitHubService.pushFile(owner, repoName, pat, branchName,
                    result.filePath(), result.patchedContent(),
                    "fix: security patch for " + result.filePath());
                filesFixed++;
                findingsFixed += result.findingsFixed();
                progress.fileFixed(scanId, result.filePath(), result.findingsFixed());
            } catch (Exception e) {
                log.warn("Failed to push fix for {}: {}", result.filePath(), e.getMessage());
                progress.fixFailed(scanId, result.filePath(), e.getMessage());
            }
        }

        if (filesFixed == 0) {
            persistFailedPr(scan, "FAILED");
            return;
        }

        // Open PR
        String prTitle = "[CodeTurret] Security fixes — " + LocalDate.now();
        String prBody = autoFixService.buildPrBody(fixResults, scanId);

        try {
            String prUrl = gitHubService.openPullRequest(owner, repoName, pat, branchName, prTitle, prBody);
            log.info("PR created: {}", prUrl);

            FixPr fixPr = new FixPr();
            fixPr.setScan(scan);
            fixPr.setPrUrl(prUrl);
            fixPr.setBranchName(branchName);
            fixPr.setFilesFixed(filesFixed);
            fixPr.setFindingsFixed(findingsFixed);
            fixPr.setStatus("OPEN");
            fixPrRepo.save(fixPr);

            progress.prCreated(scanId, prUrl, branchName, filesFixed);
        } catch (Exception e) {
            log.error("PR creation failed: {}", e.getMessage());
            persistFailedPr(scan, "FAILED");
            progress.fixFailed(scanId, "pr", "PR creation failed: " + e.getMessage());
        }
    }

    private String fetchFileFromGitHub(String owner, String repo, String filePath, String pat) {
        return gitHubService.getFileContent(owner, repo, filePath, pat);
    }

    private void persistFailedPr(Scan scan, String status) {
        FixPr fixPr = new FixPr();
        fixPr.setScan(scan);
        fixPr.setStatus(status);
        fixPrRepo.save(fixPr);
    }
}
