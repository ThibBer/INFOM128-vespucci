package com.example.utils;

import java.io.File;
import java.nio.file.Path;

public class HtmlUtils {
  /**
   * Builds a hyperlink to a specific line in a file within the repository.
   *
   * @param repoWebUrl The base web URL of the repository.
   * @param repoDir    The local clone directory of the repository.
   * @param file       The file path within the repository.
   * @param line       The line number to link to.
   * @param branch     The branch name.
   * @return A string representing the full URL to the specified line in the
   *     file.
   */
  public static String buildFileLink(String repoWebUrl, Path repoDir, Path file,
                                     int line, String branch) {
    Path relativePath = repoDir.relativize(file);
    String urlPath = relativePath.toString().replace(File.separatorChar, '/');
    return repoWebUrl + "/blob/" + branch + "/" + urlPath + "#L" + line;
  }

  /**
   * Escapes HTML characters in a string to prevent rendering issues.
   *
   * @param snippet The string to escape.
   * @return The escaped string.
   */
  public static String escapeHtml(String snippet) {
    return snippet.replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;");
  }
}
