package com.codeturret.service;

import org.springframework.stereotype.Service;

import java.util.*;
import java.util.regex.Pattern;

/**
 * Extracts security-relevant code snippets from source files.
 * Ported from Python bouncer_logic/code_extractor.py.
 */
@Service
public class CodeExtractorService {

    private static final List<SecurityPattern> SECURITY_PATTERNS = List.of(
        new SecurityPattern(Pattern.compile("(?:import|from)\\s+(?:subprocess|os|pickle|yaml|sqlite3|hashlib|hmac|jwt|bcrypt)"), "dangerous import"),
        new SecurityPattern(Pattern.compile("(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\\s", Pattern.CASE_INSENSITIVE), "SQL query"),
        new SecurityPattern(Pattern.compile("(?:password|passwd|token|secret|api_key|apikey|credential|private_key)", Pattern.CASE_INSENSITIVE), "sensitive data"),
        new SecurityPattern(Pattern.compile("(?:eval|exec)\\s*\\("), "code execution"),
        new SecurityPattern(Pattern.compile("(?:os\\.system|subprocess\\.|child_process|spawn|execFile)"), "command execution"),
        new SecurityPattern(Pattern.compile("(?:innerHTML|dangerouslySetInnerHTML|\\.html\\()"), "DOM manipulation"),
        new SecurityPattern(Pattern.compile("(?:req\\.|request\\.|res\\.|response\\.)"), "HTTP handling"),
        new SecurityPattern(Pattern.compile("(?:open\\(|readFile|writeFile|unlink|rmdir|fs\\.)"), "file I/O"),
        new SecurityPattern(Pattern.compile("(?:pickle\\.loads|yaml\\.load|deserialize|unserialize)"), "deserialization"),
        new SecurityPattern(Pattern.compile("(?:verify\\s*=\\s*False|ssl\\s*=\\s*False|rejectUnauthorized\\s*:\\s*false)", Pattern.CASE_INSENSITIVE), "TLS/SSL bypass"),
        new SecurityPattern(Pattern.compile("(?:\\.query\\(|\\.execute\\(|\\.raw\\(|\\.exec\\()"), "database call"),
        new SecurityPattern(Pattern.compile("(?:cors|cookie|session|csrf|helmet|auth|login|logout|signup|register)", Pattern.CASE_INSENSITIVE), "auth/security")
    );

    public record Snippet(String name, int startLine, int endLine, String code, List<String> matchReasons) {}
    private record SecurityPattern(Pattern pattern, String reason) {}

    /** Extract security-relevant snippets from a file. */
    public List<Snippet> extractSnippets(String content, String filePath) {
        List<Snippet> snippets;
        if (filePath.endsWith(".py")) {
            snippets = extractLineWindows(content); // Python AST not available in Java; use line windows
        } else if (filePath.endsWith(".js") || filePath.endsWith(".ts")
                || filePath.endsWith(".jsx") || filePath.endsWith(".tsx")) {
            snippets = extractJsTsSnippets(content);
        } else {
            snippets = List.of();
        }
        if (snippets.isEmpty()) {
            snippets = extractLineWindows(content);
        }
        return snippets;
    }

    /** Format snippets into a condensed string for the LLM prompt. */
    public String buildFocusedContent(List<Snippet> snippets) {
        if (snippets.isEmpty()) return "";
        StringBuilder sb = new StringBuilder();
        for (Snippet s : snippets) {
            if (!sb.isEmpty()) sb.append("\n\n");
            sb.append("=== ").append(s.name())
              .append(" (lines ").append(s.startLine()).append("-").append(s.endLine()).append(") ===\n")
              .append("[Flagged: ").append(String.join(", ", s.matchReasons())).append("]\n\n")
              .append(s.code());
        }
        return sb.toString();
    }

    // -- Private extraction methods ------------------------------------------

    private List<Snippet> extractJsTsSnippets(String content) {
        Pattern funcPattern = Pattern.compile(
            "(?:^|\\n)(?:export\\s+)?(?:default\\s+)?(?:" +
            "(?:async\\s+)?function\\s+(\\w+)|" +
            "(?:const|let|var)\\s+(\\w+)\\s*=\\s*(?:async\\s*)?\\(?|" +
            "class\\s+(\\w+)|" +
            "(\\w+)\\s*\\([^)]*\\)\\s*\\{)",
            Pattern.MULTILINE
        );

        String[] lines = content.split("\n", -1);
        List<Snippet> snippets = new ArrayList<>();

        var matcher = funcPattern.matcher(content);
        while (matcher.find()) {
            String name = firstNonNull(matcher.group(1), matcher.group(2), matcher.group(3), matcher.group(4));
            if (name == null) continue;

            int startLine = countNewlines(content, matcher.start()) + 1;
            int endLine = findBlockEnd(lines, startLine - 1);

            String code = joinLines(lines, startLine - 1, endLine);
            List<String> reasons = matchSecurityPatterns(code);
            if (!reasons.isEmpty()) {
                snippets.add(new Snippet("function: " + name, startLine, endLine, code, reasons));
            }
        }
        return snippets;
    }

    private List<Snippet> extractLineWindows(String content) {
        String[] lines = content.split("\n", -1);
        List<int[]> flagged = new ArrayList<>(); // [lineIndex, ...]

        for (int i = 0; i < lines.length; i++) {
            if (!matchSecurityPatterns(lines[i]).isEmpty()) {
                flagged.add(new int[]{i});
            }
        }
        if (flagged.isEmpty()) return List.of();

        int WINDOW = 10;
        List<Snippet> windows = new ArrayList<>();
        int curStart = Math.max(0, flagged.get(0)[0] - WINDOW);
        int curEnd = Math.min(lines.length, flagged.get(0)[0] + WINDOW + 1);
        List<String> allReasons = new ArrayList<>(matchSecurityPatterns(lines[flagged.get(0)[0]]));

        for (int k = 1; k < flagged.size(); k++) {
            int lineIdx = flagged.get(k)[0];
            int wStart = Math.max(0, lineIdx - WINDOW);
            int wEnd = Math.min(lines.length, lineIdx + WINDOW + 1);

            if (wStart <= curEnd) {
                curEnd = wEnd;
                for (String r : matchSecurityPatterns(lines[lineIdx])) {
                    if (!allReasons.contains(r)) allReasons.add(r);
                }
            } else {
                windows.add(new Snippet(
                    "lines " + (curStart + 1) + "-" + curEnd,
                    curStart + 1, curEnd,
                    joinLines(lines, curStart, curEnd),
                    new ArrayList<>(allReasons)
                ));
                curStart = wStart;
                curEnd = wEnd;
                allReasons = new ArrayList<>(matchSecurityPatterns(lines[lineIdx]));
            }
        }
        windows.add(new Snippet(
            "lines " + (curStart + 1) + "-" + curEnd,
            curStart + 1, curEnd,
            joinLines(lines, curStart, curEnd),
            allReasons
        ));
        return windows;
    }

    private List<String> matchSecurityPatterns(String text) {
        List<String> reasons = new ArrayList<>();
        for (SecurityPattern sp : SECURITY_PATTERNS) {
            if (sp.pattern().matcher(text).find() && !reasons.contains(sp.reason())) {
                reasons.add(sp.reason());
            }
        }
        return reasons;
    }

    private int findBlockEnd(String[] lines, int startIdx) {
        int depth = 0;
        boolean foundOpen = false;
        int end = Math.min(startIdx + 100, lines.length);
        for (int i = startIdx; i < end; i++) {
            for (char c : lines[i].toCharArray()) {
                if (c == '{') { depth++; foundOpen = true; }
                else if (c == '}') depth--;
            }
            if (foundOpen && depth <= 0) return i + 1;
        }
        return Math.min(startIdx + 50, lines.length);
    }

    private int countNewlines(String text, int upTo) {
        int count = 0;
        for (int i = 0; i < upTo && i < text.length(); i++) {
            if (text.charAt(i) == '\n') count++;
        }
        return count;
    }

    private String joinLines(String[] lines, int from, int to) {
        return String.join("\n", Arrays.copyOfRange(lines, from, Math.min(to, lines.length)));
    }

    @SafeVarargs
    private <T> T firstNonNull(T... values) {
        for (T v : values) if (v != null) return v;
        return null;
    }
}
