package com.codeturret.worker;

import com.codeturret.config.GeminiProperties;
import com.codeturret.messaging.ProgressPublisher;
import com.codeturret.messaging.RabbitConfig;
import com.codeturret.messaging.ScanJobMessage;
import com.codeturret.model.*;
import com.codeturret.repository.FindingRepo;
import com.codeturret.repository.RepositoryRepo;
import com.codeturret.repository.ScanRepo;
import com.codeturret.service.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.nio.file.Path;
import java.time.Instant;
import java.util.*;

@Component
@RequiredArgsConstructor
@Slf4j
public class ScanWorker {

    private final ScanRepo scanRepo;
    private final RepositoryRepo repositoryRepo;
    private final FindingRepo findingRepo;
    private final GitService gitService;
    private final CodeExtractorService codeExtractor;
    private final RiskAssessorService riskAssessor;
    private final GeminiService geminiService;
    private final ProgressPublisher progress;
    private final GeminiProperties geminiProperties;

    @RabbitListener(queues = RabbitConfig.SCAN_QUEUE)
    @Transactional
    public void handleScanJob(ScanJobMessage msg) {
        String scanId = msg.getScanId();
        log.info("Starting scan job: {}", scanId);

        Scan scan = scanRepo.findById(UUID.fromString(scanId)).orElse(null);
        if (scan == null) {
            log.error("Scan not found: {}", scanId);
            return;
        }

        Repository repo = scan.getRepository();
        Path repoDir = null;

        try {
            scan.setStatus(ScanStatus.RUNNING);
            scan.setStartedAt(Instant.now());
            scanRepo.save(scan);

            // Clone
            log.info("Cloning {}", repo.getUrl());
            repoDir = gitService.cloneRepo(repo.getUrl());

            // Git intelligence
            Map<String, Integer> hotFiles       = gitService.getHotFiles(repoDir);
            Map<String, List<String>> secFiles  = gitService.getSecurityCommits(repoDir);
            String repoContext                  = gitService.getRepoContext(repoDir);

            // List and read files
            List<GitService.FileEntry> allFiles = gitService.listSourceFiles(repoDir);
            Map<String, String> contents = new LinkedHashMap<>();
            for (GitService.FileEntry f : allFiles) {
                contents.put(f.relativePath(), gitService.readFileContent(f.fullPath()));
            }

            // Prioritize
            List<RiskAssessorService.ScoredFile> files = riskAssessor.prioritize(allFiles, contents, hotFiles, secFiles);
            progress.scanStarted(scanId, files.size());

            List<Finding> allFindings = new ArrayList<>();

            for (RiskAssessorService.ScoredFile sf : files) {
                String path    = sf.relativePath();
                String content = contents.get(path);

                // Extract focused snippets
                List<CodeExtractorService.Snippet> snippets = codeExtractor.extractSnippets(content, path);
                String focused = codeExtractor.buildFocusedContent(snippets);
                String scanContent = !focused.isBlank() ? focused : content;

                // Build git context string
                String gitContext = buildGitContext(path, hotFiles, secFiles);

                // Pass 1 — Flash triage
                GeminiService.TriageResult triage = geminiService.triageWithFlash(scanContent, path, repoContext, gitContext);
                List<GeminiService.FindingRaw> findingsForFile = triage.findings();
                String modelUsed = geminiProperties.getModel().getFlash();

                // Pass 2 — Pro deep analysis if warranted
                boolean needsDeep = msg.isDeepScan() || findingsForFile.stream().anyMatch(f ->
                    f.confidence() < geminiProperties.getDeepScanThreshold()
                    || "CRITICAL".equals(f.severity()) || "HIGH".equals(f.severity())
                );

                if (needsDeep && !findingsForFile.isEmpty()) {
                    GeminiService.DeepResult deep = geminiService.deepAnalyzeWithPro(scanContent, path, findingsForFile, repoContext, gitContext);
                    if (deep != null) {
                        findingsForFile = deep.findings();
                        modelUsed = geminiProperties.getModel().getPro();
                    }
                }

                // Persist findings
                for (GeminiService.FindingRaw raw : findingsForFile) {
                    Finding f = new Finding();
                    f.setScan(scan);
                    f.setRepository(repo);
                    f.setFilePath(path);
                    f.setLineNumber(raw.lineNumber());
                    f.setSeverity(parseSeverity(raw.severity()));
                    f.setVulnType(raw.vulnType());
                    f.setDescription(raw.description());
                    f.setFixSuggestion(raw.fixSuggestion());
                    f.setCodeSnippet(raw.codeSnippet());
                    f.setModelUsed(modelUsed);
                    f.setConfidence(raw.confidence());

                    // Git blame
                    if (raw.lineNumber() != null && raw.lineNumber() > 0) {
                        GitService.BlameInfo blame = gitService.blameLine(repoDir, path, raw.lineNumber());
                        if (blame != null) {
                            f.setCommitHash(blame.hash());
                            f.setCommitAuthor(blame.author());
                            if (!blame.date().isBlank()) {
                                f.setCommitDate(Instant.parse(blame.date() + "T00:00:00Z"));
                            }
                        }
                    }
                    allFindings.add(f);
                }

                String topSeverity = findingsForFile.stream()
                    .map(GeminiService.FindingRaw::severity)
                    .findFirst().orElse(null);
                progress.fileScanned(scanId, path, findingsForFile.size(), topSeverity);

                // Rate limit between API calls
                if (files.indexOf(sf) < files.size() - 1) {
                    Thread.sleep(geminiProperties.getRateLimitDelayMs());
                }
            }

            findingRepo.saveAll(allFindings);

            scan.setStatus(ScanStatus.COMPLETED);
            scan.setCompletedAt(Instant.now());
            scan.setTotalFiles(files.size());
            scan.setFindingsCount(allFindings.size());
            scanRepo.save(scan);

            progress.scanComplete(scanId, allFindings.size());
            log.info("Scan {} complete: {} findings in {} files", scanId, allFindings.size(), files.size());

        } catch (Exception e) {
            log.error("Scan {} failed: {}", scanId, e.getMessage(), e);
            scan.setStatus(ScanStatus.FAILED);
            scan.setCompletedAt(Instant.now());
            scan.setErrorMessage(e.getMessage());
            scanRepo.save(scan);
            progress.scanFailed(scanId, e.getMessage());
        } finally {
            if (repoDir != null) gitService.cleanup(repoDir);
        }
    }

    private String buildGitContext(String path, Map<String, Integer> hotFiles, Map<String, List<String>> secFiles) {
        List<String> parts = new ArrayList<>();
        int changes = hotFiles.getOrDefault(path, 0);
        if (changes > 0) parts.add("Modified " + changes + " times in recent history");
        List<String> msgs = secFiles.getOrDefault(path, List.of());
        if (!msgs.isEmpty()) parts.add("Security-related commits: " + String.join("; ", msgs.subList(0, Math.min(3, msgs.size()))));
        return String.join(". ", parts);
    }

    private Severity parseSeverity(String s) {
        try { return Severity.valueOf(s.toUpperCase()); } catch (Exception e) { return Severity.MEDIUM; }
    }
}
