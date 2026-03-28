package com.codeturret.service;

import com.codeturret.config.SnowflakeProperties;
import com.codeturret.model.Finding;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.List;
import java.util.Properties;

/**
 * Calls Snowflake Cortex COMPLETE for natural-language Q&A over scan findings.
 * Falls back to a plain-text response if Snowflake is not configured.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class CortexService {

    private final SnowflakeProperties snowflakeProperties;
    private final ObjectMapper objectMapper;

    /**
     * Answer a natural-language question about a scan's findings using Cortex.
     */
    public String askAboutFindings(List<Finding> findings, String question) {
        if (!snowflakeProperties.isConfigured()) {
            log.warn("Snowflake not configured — Cortex unavailable");
            return "Snowflake Cortex is not configured. Add SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_PASSWORD to your .env to enable this feature.";
        }

        String prompt = buildPrompt(findings, question);

        try (Connection conn = getConnection()) {
            String sql = "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS RESPONSE";
            try (PreparedStatement stmt = conn.prepareStatement(sql)) {
                stmt.setString(1, snowflakeProperties.getCortexModel());
                stmt.setString(2, prompt);
                try (ResultSet rs = stmt.executeQuery()) {
                    if (rs.next()) {
                        return parseResponse(rs.getString("RESPONSE"));
                    }
                }
            }
        } catch (Exception e) {
            log.error("Cortex call failed: {}", e.getMessage());
            return "Cortex query failed: " + e.getMessage();
        }
        return "No response from Cortex.";
    }

    // -- Helpers -------------------------------------------------------------

    private String buildPrompt(List<Finding> findings, String question) {
        StringBuilder sb = new StringBuilder();
        sb.append("You are a security consultant. The following vulnerabilities were found in a code scan.\n\n");
        sb.append("FINDINGS (").append(findings.size()).append(" total):\n");

        for (Finding f : findings) {
            sb.append("- [").append(f.getSeverity()).append("] ")
              .append(f.getVulnType()).append(" in ").append(f.getFilePath());
            if (f.getLineNumber() != null) sb.append(":").append(f.getLineNumber());
            sb.append("\n  ").append(f.getDescription());
            if (f.getCommitAuthor() != null && !f.getCommitAuthor().isBlank()) {
                sb.append("\n  Last modified by: ").append(f.getCommitAuthor());
            }
            sb.append("\n");
        }

        sb.append("\nQUESTION: ").append(question)
          .append("\n\nProvide a clear, concise answer based on the findings above.");
        return sb.toString();
    }

    private String parseResponse(String raw) {
        if (raw == null) return "No response.";
        try {
            JsonNode node = objectMapper.readTree(raw);
            if (node.has("choices")) {
                JsonNode msg = node.path("choices").get(0).path("messages");
                return msg.asText(raw);
            }
        } catch (Exception ignored) {}
        return raw;
    }

    private Connection getConnection() throws Exception {
        String url = "jdbc:snowflake://" + snowflakeProperties.getAccount() + ".snowflakecomputing.com/";
        Properties props = new Properties();
        props.put("user", snowflakeProperties.getUser());
        props.put("password", snowflakeProperties.getPassword());
        props.put("warehouse", snowflakeProperties.getWarehouse());
        props.put("db", snowflakeProperties.getDatabase());
        props.put("schema", snowflakeProperties.getSchema());
        return DriverManager.getConnection(url, props);
    }
}
