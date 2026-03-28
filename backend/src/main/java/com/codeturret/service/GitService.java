package com.codeturret.service;

import com.codeturret.config.GitProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.eclipse.jgit.api.Git;
import org.eclipse.jgit.api.errors.GitAPIException;
import org.springframework.stereotype.Service;
import org.springframework.util.FileSystemUtils;

import java.io.File;
import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
@Slf4j
public class GitService {

    private static final Set<String> SCANNABLE_EXTENSIONS = Set.of(".py", ".js", ".ts", ".tsx", ".jsx");
    private static final Set<String> SKIP_DIRS = Set.of("node_modules", "__pycache__", "dist", "build", "vendor");

    private static final Pattern SECURITY_KEYWORDS = Pattern.compile(
        "\\b(fix|bug|vuln|security|auth|inject|xss|csrf|patch|cve|sanitize|escape|validate|exploit|bypass)\\b",
        Pattern.CASE_INSENSITIVE
    );

    private final GitProperties gitProperties;

    /** Clone a public repo into a temp directory and return the path. */
    public Path cloneRepo(String repoUrl) throws GitAPIException, IOException {
        Path tempDir = Files.createTempDirectory("codeturret_");
        log.info("Cloning {} into {}", repoUrl, tempDir);
        Git.cloneRepository()
            .setURI(repoUrl)
            .setDirectory(tempDir.toFile())
            .setDepth(gitProperties.getCloneDepth())
            .setCloneAllBranches(false)
            .call()
            .close();
        return tempDir;
    }

    /** Walk the repo and return all scannable source files as relative paths. */
    public List<FileEntry> listSourceFiles(Path repoDir) throws IOException {
        List<FileEntry> files = new ArrayList<>();
        Files.walkFileTree(repoDir, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                String name = dir.getFileName().toString();
                if (name.startsWith(".") || SKIP_DIRS.contains(name)) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                String name = file.getFileName().toString();
                String ext = getExtension(name);
                if (SCANNABLE_EXTENSIONS.contains(ext)) {
                    String rel = repoDir.relativize(file).toString().replace("\\", "/");
                    files.add(new FileEntry(rel, file));
                }
                return FileVisitResult.CONTINUE;
            }
        });
        return files;
    }

    /**
     * Count how many times each file was changed in the last N commits.
     * Uses ProcessBuilder to call git log (matches Python implementation).
     */
    public Map<String, Integer> getHotFiles(Path repoDir) {
        Map<String, Integer> counts = new HashMap<>();
        try {
            List<String> output = runGit(repoDir,
                "log", "--max-count=" + gitProperties.getMaxCommits(),
                "--name-only", "--pretty=format:");
            for (String line : output) {
                line = line.strip();
                if (!line.isEmpty()) {
                    counts.merge(line, 1, Integer::sum);
                }
            }
        } catch (Exception e) {
            log.warn("getHotFiles failed: {}", e.getMessage());
        }
        return counts;
    }

    /**
     * Find files touched by security-related commits.
     * Returns {filePath -> [commitMessages]}
     */
    public Map<String, List<String>> getSecurityCommits(Path repoDir) {
        Map<String, List<String>> mapping = new HashMap<>();
        try {
            List<String> output = runGit(repoDir,
                "log", "--max-count=" + gitProperties.getMaxCommits(),
                "--pretty=format:__COMMIT__%s", "--name-only");

            String currentMsg = null;
            boolean isSecurity = false;

            for (String line : output) {
                line = line.strip();
                if (line.startsWith("__COMMIT__")) {
                    currentMsg = line.substring("__COMMIT__".length());
                    isSecurity = SECURITY_KEYWORDS.matcher(currentMsg).find();
                } else if (!line.isEmpty() && isSecurity && currentMsg != null) {
                    mapping.computeIfAbsent(line, k -> new ArrayList<>()).add(currentMsg);
                }
            }
        } catch (Exception e) {
            log.warn("getSecurityCommits failed: {}", e.getMessage());
        }
        return mapping;
    }

    /**
     * Get git blame info for a specific line.
     * Returns null if blame fails.
     */
    public BlameInfo blameLine(Path repoDir, String filePath, int lineNumber) {
        if (lineNumber < 1) return null;
        try {
            List<String> output = runGit(repoDir,
                "blame", "-L", lineNumber + "," + lineNumber,
                "--porcelain", "--", filePath);
            if (output.isEmpty()) return null;

            String hash = output.get(0).split(" ")[0];
            String author = "";
            String authorTime = "";

            for (String line : output) {
                if (line.startsWith("author ")) author = line.substring(7).strip();
                else if (line.startsWith("author-time ")) authorTime = line.substring(12).strip();
            }

            String date = "";
            if (!authorTime.isEmpty()) {
                long ts = Long.parseLong(authorTime);
                date = java.time.Instant.ofEpochSecond(ts).toString().substring(0, 10);
            }
            return new BlameInfo(hash, author, date);
        } catch (Exception e) {
            log.debug("blameLine failed for {}:{}: {}", filePath, lineNumber, e.getMessage());
            return null;
        }
    }

    /** Read a project's README and package.json for context. */
    public String getRepoContext(Path repoDir) {
        StringBuilder sb = new StringBuilder();
        for (String name : List.of("README.md", "README.rst", "README.txt", "README")) {
            Path readme = repoDir.resolve(name);
            if (Files.exists(readme)) {
                try {
                    String text = Files.readString(readme);
                    if (text.length() > 2000) text = text.substring(0, 2000);
                    String[] blocks = text.strip().split("\n\n");
                    sb.append(blocks[0]);
                    break;
                } catch (IOException ignored) {}
            }
        }
        Path pkg = repoDir.resolve("package.json");
        if (Files.exists(pkg)) {
            try {
                String json = Files.readString(pkg);
                // Simple extraction without a JSON parser to avoid extra dependency
                extractJsonField(json, "description").ifPresent(d -> sb.append("\nDescription: ").append(d));
            } catch (IOException ignored) {}
        }
        return sb.toString();
    }

    /** Read a file's content, truncating at max size. */
    public String readFileContent(Path file) throws IOException {
        byte[] bytes = Files.readAllBytes(file);
        String content = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
        if (content.length() > gitProperties.getMaxFileSize()) {
            content = content.substring(0, gitProperties.getMaxFileSize());
        }
        return content;
    }

    /** Delete a cloned repo directory. */
    public void cleanup(Path repoDir) {
        try {
            FileSystemUtils.deleteRecursively(repoDir);
        } catch (IOException e) {
            log.warn("Cleanup failed for {}: {}", repoDir, e.getMessage());
        }
    }

    // -- Helpers -------------------------------------------------------------

    private List<String> runGit(Path dir, String... args) throws IOException, InterruptedException {
        List<String> cmd = new ArrayList<>();
        cmd.add("git");
        cmd.addAll(Arrays.asList(args));
        ProcessBuilder pb = new ProcessBuilder(cmd).directory(dir.toFile()).redirectErrorStream(false);
        Process proc = pb.start();
        String out = new String(proc.getInputStream().readAllBytes());
        proc.waitFor();
        return out.isEmpty() ? List.of() : Arrays.asList(out.split("\n"));
    }

    private String getExtension(String filename) {
        int dot = filename.lastIndexOf('.');
        return dot >= 0 ? filename.substring(dot) : "";
    }

    private Optional<String> extractJsonField(String json, String field) {
        String search = "\"" + field + "\"";
        int idx = json.indexOf(search);
        if (idx < 0) return Optional.empty();
        int colon = json.indexOf(':', idx);
        if (colon < 0) return Optional.empty();
        int start = json.indexOf('"', colon + 1);
        if (start < 0) return Optional.empty();
        int end = json.indexOf('"', start + 1);
        if (end < 0) return Optional.empty();
        return Optional.of(json.substring(start + 1, end));
    }

    // -- Value types ---------------------------------------------------------

    public record FileEntry(String relativePath, Path fullPath) {}

    public record BlameInfo(String hash, String author, String date) {}
}
