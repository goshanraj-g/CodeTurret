package com.codeturret.service;

import com.codeturret.config.GitProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.regex.Pattern;

/**
 * Scores and prioritizes files for scanning.
 * Ported from Python bouncer_logic/risk_assessor.py.
 */
@Service
@RequiredArgsConstructor
public class RiskAssessorService {

    private static final int RISK_SKIP   = 0;
    private static final int RISK_LOW    = 1;
    private static final int RISK_MEDIUM = 2;
    private static final int RISK_HIGH   = 3;

    private static final int GIT_HOT_FILE_BONUS        = 1;
    private static final int GIT_SECURITY_COMMIT_BONUS = 2;
    private static final int GIT_HOT_FILE_THRESHOLD    = 3;

    private static final Set<String> HIGH_RISK_NAMES = Set.of(
        ".env", ".env.local", ".env.production",
        "dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "secrets.json", "credentials.json"
    );

    private static final List<Pattern> HIGH_RISK_PATH_PATTERNS = List.of(
        Pattern.compile("\\.github/workflows/"),
        Pattern.compile("(^|/)auth"),
        Pattern.compile("(^|/)login"),
        Pattern.compile("(^|/)middleware"),
        Pattern.compile("(^|/)api/"),
        Pattern.compile("(^|/)routes?/"),
        Pattern.compile("(^|/)controllers?/"),
        Pattern.compile("(^|/)handlers?/"),
        Pattern.compile("(^|/)db/"),
        Pattern.compile("(^|/)models?/"),
        Pattern.compile("(^|/)config")
    );

    private static final Set<String> RISK_KEYWORDS = Set.of(
        "password", "passwd", "secret", "token", "api_key", "apikey",
        "private_key", "access_key", "credentials",
        "eval(", "exec(", "subprocess", "os.system", "child_process",
        "innerhtml", "dangerouslysetinnerhtml",
        "select ", "insert ", "update ", "delete ",
        "pickle.loads", "yaml.load",
        "verify=false", "ssl=false"
    );

    private static final Set<String> SKIP_NAMES = Set.of(
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
        "changelog.md", "license.md", "license", "license.txt",
        "contributing.md", ".prettierrc", ".eslintrc"
    );

    private static final List<Pattern> SKIP_PATH_PATTERNS = List.of(
        Pattern.compile("(^|/)node_modules/"),
        Pattern.compile("(^|/)\\.git/"),
        Pattern.compile("(^|/)dist/"),
        Pattern.compile("(^|/)build/"),
        Pattern.compile("(^|/)__pycache__/"),
        Pattern.compile("(^|/)vendor/")
    );

    private static final Set<String> SKIP_EXTENSIONS = Set.of(
        ".md", ".txt", ".rst", ".csv", ".svg", ".png", ".jpg", ".gif",
        ".ico", ".woff", ".woff2", ".ttf", ".eot", ".map"
    );

    private static final List<String> SKIP_SUFFIXES = List.of(".d.ts", ".min.js", ".min.css");

    private final GitProperties gitProperties;

    public record ScoredFile(String relativePath, java.nio.file.Path fullPath, int riskScore) {}

    /**
     * Score, filter, and sort files by risk. Returns top max_files entries.
     */
    public List<ScoredFile> prioritize(
        List<GitService.FileEntry> files,
        Map<String, String> contents,
        Map<String, Integer> hotFiles,
        Map<String, List<String>> securityFiles
    ) {
        List<ScoredFile> scored = new ArrayList<>();

        for (GitService.FileEntry f : files) {
            String content = contents.getOrDefault(f.relativePath(), "");
            int risk = assessRisk(f.relativePath(), content);
            if (risk == RISK_SKIP) continue;

            // Apply git signals
            if (hotFiles.getOrDefault(f.relativePath(), 0) >= GIT_HOT_FILE_THRESHOLD) {
                risk += GIT_HOT_FILE_BONUS;
            }
            if (securityFiles.containsKey(f.relativePath())) {
                risk += GIT_SECURITY_COMMIT_BONUS;
            }
            scored.add(new ScoredFile(f.relativePath(), f.fullPath(), risk));
        }

        scored.sort(Comparator.comparingInt(ScoredFile::riskScore).reversed());
        int cap = gitProperties.getMaxScanFiles();
        return scored.size() > cap ? scored.subList(0, cap) : scored;
    }

    public int assessRisk(String filePath, String content) {
        String lower = filePath.toLowerCase();
        String basename = getBasename(lower);
        String ext = getExtension(basename);

        if (SKIP_NAMES.contains(basename)) return RISK_SKIP;
        if (SKIP_EXTENSIONS.contains(ext)) return RISK_SKIP;
        for (String suffix : SKIP_SUFFIXES) {
            if (lower.endsWith(suffix)) return RISK_SKIP;
        }
        for (Pattern p : SKIP_PATH_PATTERNS) {
            if (p.matcher(lower).find()) return RISK_SKIP;
        }

        int score = RISK_LOW;

        if (HIGH_RISK_NAMES.contains(basename)) return RISK_HIGH;

        for (Pattern p : HIGH_RISK_PATH_PATTERNS) {
            if (p.matcher(lower).find()) {
                score = Math.max(score, RISK_HIGH);
                break;
            }
        }

        if (!content.isEmpty()) {
            String lowerContent = content.toLowerCase();
            int matches = (int) RISK_KEYWORDS.stream().filter(lowerContent::contains).count();
            if (matches >= 3) score = Math.max(score, RISK_HIGH);
            else if (matches >= 1) score = Math.max(score, RISK_MEDIUM);
        }

        return score;
    }

    private String getBasename(String path) {
        int slash = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
        return slash >= 0 ? path.substring(slash + 1) : path;
    }

    private String getExtension(String filename) {
        int dot = filename.lastIndexOf('.');
        return dot >= 0 ? filename.substring(dot) : "";
    }
}
