package com.example.utils;

import com.example.analyzer.DatabaseUsageAnalyzer;
import com.example.models.TableDefinition;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.eclipse.jgit.api.BlameCommand;
import org.eclipse.jgit.api.CloneCommand;
import org.eclipse.jgit.api.Git;
import org.eclipse.jgit.api.errors.GitAPIException;
import org.eclipse.jgit.blame.BlameResult;
import org.eclipse.jgit.lib.PersonIdent;
import org.eclipse.jgit.lib.Repository;
import org.eclipse.jgit.revwalk.RevCommit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class GitUtils {
  private static final Logger logger = LoggerFactory.getLogger(GitUtils.class);
  public static void cloneRepository(String repoUrl, String commitHash)
      throws IOException {
    Path cloneDir = Paths.get("repo_clone");
    String repoWebUrl = null;
    String defaultBranch = null;
    DatabaseUsageAnalyzer dbAnalyzer = new DatabaseUsageAnalyzer();
    if (!Files.exists(cloneDir)) {
      try {
        logger.info("Cloning repository from {} to {}", repoUrl, cloneDir);
        CloneCommand cloneCommand = Git.cloneRepository()
                                        .setURI(repoUrl)
                                        .setDirectory(cloneDir.toFile())
                                        .setCloneAllBranches(true);
        try (Git git = cloneCommand.call()) {
          logger.info("Cloning completed.");
          // Checkout specific commit
          if (commitHash != null) {
            git.checkout().setName(commitHash).call();
            logger.info("Checked out specific commit: {}", commitHash);
          }
          Repository repository = git.getRepository();
          defaultBranch = repository.getBranch();
          logger.info("Default branch detected: {}", defaultBranch);
          repoWebUrl = deriveWebUrl(repoUrl);
          dbAnalyzer.runAnalysis(cloneDir, repoWebUrl, defaultBranch,
                                 repository);
        }
      } catch (GitAPIException e) {
        logger.error("Failed to clone repository: {}", e.getMessage());
        e.printStackTrace();
        return;
      }
    } else {
      logger.info("Opening existing repository at {}", cloneDir);
      try (Git git = Git.open(cloneDir.toFile())) {
        Repository repository = git.getRepository();
        defaultBranch = repository.getBranch();
        logger.info("Default branch detected: {}", defaultBranch);
        repoWebUrl = deriveWebUrl(repoUrl);
        dbAnalyzer.runAnalysis(cloneDir, repoWebUrl, defaultBranch, repository);
      } catch (IOException e) {
        logger.error("Failed to open existing repository: {}", e.getMessage());
        e.printStackTrace();
        return;
      }
    }

    if (repoWebUrl == null) {
      logger.error("Unsupported repository URL format: {}", repoUrl);
    }
  }
  /**
   * Derives the web URL from the repository clone URL.
   * Handles HTTPS and SSH URLs for GitHub.
   *
   * @param repoUrl The clone URL of the repository.
   * @return The base web URL for accessing files, or null if the format is
   *     unsupported.
   */
  private static String deriveWebUrl(String repoUrl) {
    // Handle HTTPS URLs
    if (repoUrl.startsWith("https://github.com/")) {
      // Example: https://github.com/user/repo.git ->
      // https://github.com/user/repo
      if (repoUrl.endsWith(".git")) {
        return repoUrl.substring(0, repoUrl.length() - 4);
      } else {
        return repoUrl;
      }
    }
    // Handle SSH URLs
    else if (repoUrl.startsWith("git@github.com:")) {
      // Example: git@github.com:user/repo.git -> https://github.com/user/repo
      String webUrl = repoUrl.replace("git@github.com:", "https://github.com/");
      if (webUrl.endsWith(".git")) {
        webUrl = webUrl.substring(0, webUrl.length() - 4);
      }
      return webUrl;
    }
    // Unsupported URL format
    else {
      return null;
    }
  }

  /**
   * Assigns creation dates to table definitions using Git blame.
   *
   * @param repoDir    The root directory of the repository.
   * @param repository The Git repository object.
   */
  public static void assignCreationDates(Path repoDir, Repository repository) {
    // Group table definitions by file
    Map<Path, List<TableDefinition>> tablesByFile =
        DatabaseUsageAnalyzer.createTableStatements.values().stream().collect(
            Collectors.groupingBy(td -> td.file));

    for (Map.Entry<Path, List<TableDefinition>> entry :
         tablesByFile.entrySet()) {
      Path file = entry.getKey();
      List<TableDefinition> tables = entry.getValue();
      String relativePath =
          repoDir.relativize(file).toString().replace(File.separatorChar, '/');

      try {
        BlameCommand blamer = new BlameCommand(repository);
        blamer.setFilePath(relativePath);
        BlameResult blame = blamer.call();

        if (blame == null) {
          logger.error("Blame result is null for file: {}", relativePath);
          continue;
        }

        for (TableDefinition td : tables) {
          int line = td.lineNumber;
          if (line < 1 || line > blame.getResultContents().size()) {
            logger.error("Invalid line number {} for file: {}", line,
                         relativePath);
            continue;
          }
          RevCommit commit = blame.getSourceCommit(line);
          if (commit != null) {
            PersonIdent author = commit.getCommitterIdent();
            Instant commitInstant = author.getWhenAsInstant();
            ZoneId zone = author.getZoneId();
            LocalDateTime commitDate =
                LocalDateTime.ofInstant(commitInstant, zone);
            td.creationDate = commitDate;
          } else {
            logger.error("No commit found for file: {} at line: {}",
                         relativePath, line);
          }
        }
      } catch (Exception e) {
        logger.error("Failed to perform blame on file: {}", relativePath);
        e.printStackTrace();
      }
    }
  }
}
