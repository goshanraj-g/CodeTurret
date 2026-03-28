package com.codeturret.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;
import java.util.Map;

/**
 * Calls the GitHub REST API to create branches, push file changes, and open PRs.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class GitHubService {

    private final WebClient webClient;

    @Value("${github.api-url}")
    private String apiUrl;

    /**
     * Create a new branch off the default branch.
     * Returns the new branch name.
     */
    public String createFixBranch(String owner, String repo, String pat, String scanIdShort) {
        String branchName = "codeturret/fix/" + scanIdShort;
        String token = "Bearer " + pat;

        // Get the SHA of the default branch HEAD
        Map<?, ?> refData = webClient.get()
            .uri(apiUrl + "/repos/{owner}/{repo}/git/ref/heads/main", owner, repo)
            .header(HttpHeaders.AUTHORIZATION, token)
            .retrieve()
            .bodyToMono(Map.class)
            .onErrorResume(e -> {
                // Try 'master' if 'main' doesn't exist
                return webClient.get()
                    .uri(apiUrl + "/repos/{owner}/{repo}/git/ref/heads/master", owner, repo)
                    .header(HttpHeaders.AUTHORIZATION, token)
                    .retrieve()
                    .bodyToMono(Map.class);
            })
            .block();

        String sha = ((Map<?, ?>) ((Map<?, ?>) refData).get("object")).get("sha").toString();

        // Create the new branch
        webClient.post()
            .uri(apiUrl + "/repos/{owner}/{repo}/git/refs", owner, repo)
            .header(HttpHeaders.AUTHORIZATION, token)
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(Map.of("ref", "refs/heads/" + branchName, "sha", sha))
            .retrieve()
            .bodyToMono(String.class)
            .block();

        log.info("Created branch {} in {}/{}", branchName, owner, repo);
        return branchName;
    }

    /**
     * Push a file update to a branch via the GitHub Contents API.
     */
    public void pushFile(String owner, String repo, String pat, String branch,
                         String filePath, String newContent, String commitMessage) {
        String token = "Bearer " + pat;

        // Get current file SHA (needed for the update)
        String currentSha = null;
        try {
            Map<?, ?> fileData = webClient.get()
                .uri(apiUrl + "/repos/{owner}/{repo}/contents/{path}?ref={branch}", owner, repo, filePath, branch)
                .header(HttpHeaders.AUTHORIZATION, token)
                .retrieve()
                .bodyToMono(Map.class)
                .block();
            currentSha = fileData.get("sha").toString();
        } catch (WebClientResponseException.NotFound e) {
            log.warn("File {} not found on branch {}, will create new", filePath, branch);
        }

        String encoded = Base64.getEncoder().encodeToString(newContent.getBytes(StandardCharsets.UTF_8));

        Map<String, Object> body = currentSha != null
            ? Map.of("message", commitMessage, "content", encoded, "sha", currentSha, "branch", branch)
            : Map.of("message", commitMessage, "content", encoded, "branch", branch);

        webClient.put()
            .uri(apiUrl + "/repos/{owner}/{repo}/contents/{path}", owner, repo, filePath)
            .header(HttpHeaders.AUTHORIZATION, token)
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(body)
            .retrieve()
            .bodyToMono(String.class)
            .block();
    }

    /**
     * Open a pull request and return the PR URL.
     */
    public String openPullRequest(String owner, String repo, String pat,
                                   String branch, String title, String body) {
        String token = "Bearer " + pat;

        Map<?, ?> pr = webClient.post()
            .uri(apiUrl + "/repos/{owner}/{repo}/pulls", owner, repo)
            .header(HttpHeaders.AUTHORIZATION, token)
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(Map.of(
                "title", title,
                "body", body,
                "head", branch,
                "base", "main"
            ))
            .retrieve()
            .bodyToMono(Map.class)
            .onErrorResume(e -> {
                // Try 'master' base if 'main' fails
                return webClient.post()
                    .uri(apiUrl + "/repos/{owner}/{repo}/pulls", owner, repo)
                    .header(HttpHeaders.AUTHORIZATION, token)
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(Map.of(
                        "title", title,
                        "body", body,
                        "head", branch,
                        "base", "master"
                    ))
                    .retrieve()
                    .bodyToMono(Map.class);
            })
            .block();

        return pr.get("html_url").toString();
    }

    /**
     * Fetch a file's decoded content from GitHub.
     */
    public String getFileContent(String owner, String repo, String filePath, String pat) {
        String token = "Bearer " + pat;
        Map<?, ?> data = webClient.get()
            .uri(apiUrl + "/repos/{owner}/{repo}/contents/{path}", owner, repo, filePath)
            .header(HttpHeaders.AUTHORIZATION, token)
            .retrieve()
            .bodyToMono(Map.class)
            .block();
        String encoded = data.get("content").toString().replaceAll("\\s", "");
        return new String(Base64.getDecoder().decode(encoded), StandardCharsets.UTF_8);
    }

    /**
     * Get owner and repo name from a GitHub URL.
     * e.g. https://github.com/owner/repo -> ["owner", "repo"]
     */
    public String[] parseOwnerRepo(String repoUrl) {
        String url = repoUrl.endsWith("/") ? repoUrl.substring(0, repoUrl.length() - 1) : repoUrl;
        if (url.endsWith(".git")) url = url.substring(0, url.length() - 4);
        String[] parts = url.split("/");
        return new String[]{parts[parts.length - 2], parts[parts.length - 1]};
    }
}
