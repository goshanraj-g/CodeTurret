package com.codeturret.api;

import com.codeturret.api.dto.RepoRequest;
import com.codeturret.model.Repository;
import com.codeturret.repository.RepositoryRepo;
import com.codeturret.service.EncryptionService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/repos")
@RequiredArgsConstructor
public class RepoController {

    private final RepositoryRepo repoRepo;
    private final EncryptionService encryptionService;

    @GetMapping
    public List<Map<String, Object>> list() {
        return repoRepo.findAll().stream()
            .map(r -> Map.<String, Object>of(
                "id", r.getId(),
                "name", r.getName(),
                "url", r.getUrl(),
                "hasToken", r.getGithubToken() != null,
                "createdAt", r.getCreatedAt()
            ))
            .toList();
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> create(@Valid @RequestBody RepoRequest request) {
        if (repoRepo.existsByName(request.getName())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Repository name already exists");
        }

        Repository repo = new Repository();
        repo.setName(request.getName());
        repo.setUrl(request.getUrl());

        if (request.getGithubToken() != null && !request.getGithubToken().isBlank()) {
            repo.setGithubToken(encryptionService.encrypt(request.getGithubToken()));
        }

        repo = repoRepo.save(repo);
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of(
            "id", repo.getId(),
            "name", repo.getName(),
            "url", repo.getUrl()
        ));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable UUID id) {
        if (!repoRepo.existsById(id)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Repository not found");
        }
        repoRepo.deleteById(id);
        return ResponseEntity.noContent().build();
    }
}
