package com.codeturret.service;

import com.codeturret.config.GeminiProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.*;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
@Slf4j
public class GeminiService {

    private static final Pattern FILE_ROLE_PATTERNS_API   = Pattern.compile("(^|/)api/",          Pattern.CASE_INSENSITIVE);
    private static final Pattern FILE_ROLE_PATTERNS_ROUTE = Pattern.compile("(^|/)routes?/",       Pattern.CASE_INSENSITIVE);
    private static final Pattern FILE_ROLE_PATTERNS_CTRL  = Pattern.compile("(^|/)controllers?/",  Pattern.CASE_INSENSITIVE);
    private static final Pattern FILE_ROLE_PATTERNS_AUTH  = Pattern.compile("(^|/)auth",            Pattern.CASE_INSENSITIVE);
    private static final Pattern FILE_ROLE_PATTERNS_DB    = Pattern.compile("(^|/)db/",             Pattern.CASE_INSENSITIVE);
    private static final Pattern FILE_ROLE_PATTERNS_CFG   = Pattern.compile("(^|/)config",          Pattern.CASE_INSENSITIVE);
    private static final Pattern FILE_ROLE_PATTERNS_SVC   = Pattern.compile("(^|/)services?/",      Pattern.CASE_INSENSITIVE);
    private static final Pattern FILE_ROLE_PATTERNS_MDL   = Pattern.compile("(^|/)models?/",        Pattern.CASE_INSENSITIVE);

    private final GeminiProperties geminiProperties;
    private final WebClient webClient;
    private final ObjectMapper objectMapper;

    public record TriageResult(List<GeminiService.FindingRaw> findings, double fileRiskScore, String summary) {}
    public record DeepResult(List<GeminiService.FindingRaw> findings, String summary) {}
    public record FindingRaw(
        Integer lineNumber, String severity, String vulnType,
        String description, String fixSuggestion, Double confidence,
        String codeSnippet, String attackVector, String cweId
    ) {}

    /** Pass 1: fast triage with Gemini Flash. */
    public TriageResult triageWithFlash(String content, String filePath, String repoContext, String gitContext) {
        String prompt = buildTriagePrompt(content, filePath, repoContext, gitContext);
        JsonNode response = callGemini(geminiProperties.getModel().getFlash(), prompt);
        return parseTriageResult(response);
    }

    /** Pass 2: deep analysis with Gemini Pro. Returns null on failure (caller falls back to flash). */
    public DeepResult deepAnalyzeWithPro(String content, String filePath, List<FindingRaw> triageFindings,
                                          String repoContext, String gitContext) {
        try {
            String prompt = buildDeepPrompt(content, filePath, triageFindings, repoContext, gitContext);
            JsonNode response = callGemini(geminiProperties.getModel().getPro(), prompt);
            return parseDeepResult(response);
        } catch (Exception e) {
            log.warn("Pro analysis failed for {}, keeping flash results: {}", filePath, e.getMessage());
            return null;
        }
    }

    /** Generate a corrected version of a file given findings. Returns patched content or null. */
    public String generateFix(String fileContent, String filePath, List<FindingRaw> findings) {
        StringBuilder findingsText = new StringBuilder();
        for (int i = 0; i < findings.size(); i++) {
            FindingRaw f = findings.get(i);
            findingsText.append(i + 1).append(". ")
                .append(f.severity()).append(" - ").append(f.vulnType())
                .append(" at line ").append(f.lineNumber() != null ? f.lineNumber() : "?").append("\n")
                .append("   Description: ").append(f.description()).append("\n");
            if (f.fixSuggestion() != null) {
                findingsText.append("   Suggested fix: ").append(f.fixSuggestion()).append("\n");
            }
        }

        String prompt = "You are a security engineer. The following file has security vulnerabilities.\n\n" +
            "File: " + filePath + "\n\n" +
            "VULNERABILITIES TO FIX:\n" + findingsText + "\n" +
            "SOURCE CODE:\n```\n" + fileContent + "\n```\n\n" +
            "Return ONLY the complete corrected file content with all vulnerabilities fixed. " +
            "Do not include any explanation, markdown, or code fences. " +
            "Return only the raw source code.";

        try {
            JsonNode response = callGemini(geminiProperties.getModel().getPro(), prompt);
            String text = extractText(response);
            // Strip markdown code fences if present
            text = text.strip();
            if (text.startsWith("```")) {
                text = text.replaceFirst("```[a-zA-Z]*\\n?", "");
                int end = text.lastIndexOf("```");
                if (end >= 0) text = text.substring(0, end).strip();
            }
            return text;
        } catch (Exception e) {
            log.warn("Fix generation failed for {}: {}", filePath, e.getMessage());
            return null;
        }
    }

    /** Ask a question about a repo's findings. */
    public String askAboutFindings(String findingsSummary, String question) {
        String prompt = "You are a security consultant analyzing scan results.\n\n" +
            "SCAN FINDINGS SUMMARY:\n" + findingsSummary + "\n\n" +
            "QUESTION: " + question + "\n\n" +
            "Provide a clear, concise answer based on the findings above.";
        try {
            JsonNode response = callGemini(geminiProperties.getModel().getFlash(), prompt);
            return extractText(response);
        } catch (Exception e) {
            return "Unable to answer: " + e.getMessage();
        }
    }

    // -- API call ------------------------------------------------------------

    private JsonNode callGemini(String model, String prompt) {
        String url = geminiProperties.getBaseUrl() + "/models/" + model + ":generateContent?key=" + geminiProperties.getApiKey();

        Map<String, Object> body = Map.of(
            "contents", List.of(Map.of("parts", List.of(Map.of("text", prompt)))),
            "generationConfig", Map.of(
                "responseMimeType", "application/json",
                "temperature", 0.1
            )
        );

        for (int attempt = 1; attempt <= geminiProperties.getMaxRetries() + 1; attempt++) {
            try {
                String json = webClient.post()
                    .uri(url)
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(String.class)
                    .timeout(Duration.ofSeconds(geminiProperties.getTimeoutSeconds()))
                    .block();
                return objectMapper.readTree(json);
            } catch (Exception e) {
                log.warn("Gemini attempt {}/{} failed: {}", attempt, geminiProperties.getMaxRetries() + 1, e.getMessage());
                if (attempt <= geminiProperties.getMaxRetries()) {
                    try { Thread.sleep(2000L * attempt); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
                } else {
                    throw new RuntimeException("Gemini call failed after " + attempt + " attempts: " + e.getMessage(), e);
                }
            }
        }
        throw new RuntimeException("Gemini call failed");
    }

    // -- Parsers -------------------------------------------------------------

    private TriageResult parseTriageResult(JsonNode response) {
        try {
            String text = extractText(response);
            JsonNode root = objectMapper.readTree(text);
            List<FindingRaw> findings = parseFindings(root.path("findings"));
            double riskScore = root.path("file_risk_score").asDouble(0.0);
            String summary = root.path("summary").asText("");
            return new TriageResult(findings, riskScore, summary);
        } catch (Exception e) {
            log.warn("Failed to parse triage result: {}", e.getMessage());
            return new TriageResult(List.of(), 0.0, "");
        }
    }

    private DeepResult parseDeepResult(JsonNode response) {
        try {
            String text = extractText(response);
            JsonNode root = objectMapper.readTree(text);
            List<FindingRaw> findings = parseFindings(root.path("findings"));
            String summary = root.path("summary").asText("");
            return new DeepResult(findings, summary);
        } catch (Exception e) {
            log.warn("Failed to parse deep result: {}", e.getMessage());
            return new DeepResult(List.of(), "");
        }
    }

    private List<FindingRaw> parseFindings(JsonNode arr) {
        List<FindingRaw> result = new ArrayList<>();
        if (arr == null || !arr.isArray()) return result;
        for (JsonNode n : arr) {
            result.add(new FindingRaw(
                n.path("line_number").isMissingNode() ? null : n.path("line_number").asInt(),
                n.path("severity").asText("MEDIUM"),
                n.path("vuln_type").asText("Unknown"),
                n.path("description").asText(""),
                n.path("fix_suggestion").asText(null),
                n.path("confidence").asDouble(0.5),
                n.path("code_snippet").asText(null),
                n.path("attack_vector").asText(null),
                n.path("cwe_id").asText(null)
            ));
        }
        return result;
    }

    private String extractText(JsonNode response) {
        return response.path("candidates").get(0)
            .path("content").path("parts").get(0)
            .path("text").asText();
    }

    // -- Prompt builders -----------------------------------------------------

    private String buildTriagePrompt(String content, String filePath, String repoContext, String gitContext) {
        String role = inferFileRole(filePath);
        StringBuilder ctx = new StringBuilder();
        if (!repoContext.isBlank()) ctx.append("Project: ").append(repoContext).append("\n");
        ctx.append("File: ").append(filePath).append("\nRole: ").append(role).append("\n");
        if (!gitContext.isBlank()) ctx.append("Git history: ").append(gitContext).append("\n");

        return "You are a security auditor. Analyze the following code for real, exploitable vulnerabilities.\n\n" +
            ctx + "\n" +
            "Focus on: SQL Injection, Command Injection, XSS, SSRF, Broken Auth, " +
            "Sensitive Data Exposure, Insecure Deserialization, Security Misconfiguration, Path Traversal.\n\n" +
            "Only report REAL vulnerabilities with HIGH confidence. " +
            "Return empty findings array if nothing found.\n\n" +
            "SOURCE CODE:\n```\n" + content + "\n```\n\n" +
            "Return JSON: {\"findings\": [{\"line_number\": int, \"severity\": \"CRITICAL|HIGH|MEDIUM|LOW\", " +
            "\"vuln_type\": string, \"description\": string, \"confidence\": float, \"code_snippet\": string}], " +
            "\"file_risk_score\": float, \"summary\": string}";
    }

    private String buildDeepPrompt(String content, String filePath, List<FindingRaw> triageFindings,
                                    String repoContext, String gitContext) {
        String role = inferFileRole(filePath);
        StringBuilder ctx = new StringBuilder();
        if (!repoContext.isBlank()) ctx.append("Project: ").append(repoContext).append("\n");
        ctx.append("File: ").append(filePath).append("\nRole: ").append(role).append("\n");
        if (!gitContext.isBlank()) ctx.append("Git history: ").append(gitContext).append("\n");

        StringBuilder findingsJson = new StringBuilder("[");
        for (int i = 0; i < triageFindings.size(); i++) {
            if (i > 0) findingsJson.append(", ");
            FindingRaw f = triageFindings.get(i);
            findingsJson.append("{\"severity\":\"").append(f.severity())
                .append("\",\"vuln_type\":\"").append(f.vulnType())
                .append("\",\"description\":\"").append(f.description().replace("\"", "'"))
                .append("\",\"confidence\":").append(f.confidence()).append("}");
        }
        findingsJson.append("]");

        return "You are an expert application security researcher.\n\n" +
            ctx + "\n" +
            "PRELIMINARY FINDINGS:\n" + findingsJson + "\n\n" +
            "SOURCE CODE:\n```\n" + content + "\n```\n\n" +
            "1. CONFIRM or REJECT each finding. 2. Provide working code fixes. " +
            "3. Identify missed vulnerabilities. 4. Assign CWE IDs.\n\n" +
            "Return JSON: {\"findings\": [{\"line_number\": int, \"severity\": string, \"vuln_type\": string, " +
            "\"description\": string, \"fix_suggestion\": string, \"confidence\": float, " +
            "\"code_snippet\": string, \"attack_vector\": string, \"cwe_id\": string}], \"summary\": string}";
    }

    private String inferFileRole(String filePath) {
        if (FILE_ROLE_PATTERNS_API.matcher(filePath).find())   return "API endpoint handler";
        if (FILE_ROLE_PATTERNS_ROUTE.matcher(filePath).find()) return "Route handler";
        if (FILE_ROLE_PATTERNS_CTRL.matcher(filePath).find())  return "Controller";
        if (FILE_ROLE_PATTERNS_AUTH.matcher(filePath).find())  return "Authentication module";
        if (FILE_ROLE_PATTERNS_DB.matcher(filePath).find())    return "Database access layer";
        if (FILE_ROLE_PATTERNS_CFG.matcher(filePath).find())   return "Configuration file";
        if (FILE_ROLE_PATTERNS_SVC.matcher(filePath).find())   return "Service layer";
        if (FILE_ROLE_PATTERNS_MDL.matcher(filePath).find())   return "Data model";
        return "Source file";
    }
}
