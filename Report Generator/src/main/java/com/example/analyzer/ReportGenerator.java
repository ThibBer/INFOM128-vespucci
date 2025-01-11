package com.example.analyzer;

import com.example.models.CodeReference;
import com.example.models.QueryInfo;
import com.example.models.TableDefinition;
import com.example.parsers.SQLParser;
import com.example.utils.HtmlUtils;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class ReportGenerator {
  // Store queries for complexity analysis
  public static List<QueryInfo> queries = new ArrayList<>();
  /**
   * Generates an HTML report summarizing the analysis.
   *
   * @param outputPath    The path to the output HTML file.
   * @param repoWebUrl    The web URL of the repository (for linking in the
   *     report).
   * @param repoDir       The directory of the cloned repository.
   * @param unusedTables  A list of unused tables.
   * @param unusedCols    A map of unused columns per table.
   * @param branch        The default branch of the repository.
   * @throws IOException If an I/O error occurs.
   */
  public static void generateHtmlReport(Path outputPath, String repoWebUrl,
                                        Path repoDir,
                                        List<TableDefinition> unusedTables,
                                        Map<String, List<String>> unusedCols,
                                        String branch) throws IOException {
    try (BufferedWriter w =
             Files.newBufferedWriter(outputPath, StandardCharsets.UTF_8)) {
      w.write("<html><head><title>Database Table Usage "
              + "Report</title></head><body>");
      w.write("<h1>Database Table Usage Report</h1>");

      // Summary
      w.write("<h2>Summary</h2>");
      w.write("<p>Total tables: " +
              DatabaseUsageAnalyzer.createTableStatements.size() + "</p>");
      w.write("<p>Unused tables: " + unusedTables.size() + "</p>");
      if (!unusedTables.isEmpty()) {
        w.write("<ul>");
        for (TableDefinition td : unusedTables) {
          String link = HtmlUtils.buildFileLink(repoWebUrl, repoDir, td.file,
                                                td.lineNumber, branch);
          String dateStr =
              (td.creationDate != null)
                  ? td.creationDate.format(DateTimeFormatter.ISO_LOCAL_DATE)
                  : "Unknown";
          w.write("<li>" + td.tableName + " (Defined in: <a href=\"" + link +
                  "\">" + repoDir.relativize(td.file) + ": line " +
                  td.lineNumber + "</a>"
                  + ", Created on: " + dateStr + ")</li>");
        }
        w.write("</ul>");
      }

      int totalUnusedColumns =
          unusedCols.values().stream().mapToInt(List::size).sum();
      w.write("<p>Unused columns: " + totalUnusedColumns + "</p>");
      if (totalUnusedColumns > 0) {
        w.write("<ul>");
        for (Map.Entry<String, List<String>> e : unusedCols.entrySet()) {
          w.write("<li><strong>" + e.getKey() +
                  "</strong>: " + String.join(", ", e.getValue()) + "</li>");
        }
        w.write("</ul>");
      }

      // Detailed Table Usage
      w.write("<h2>Detailed Table Usage</h2>");
      for (String table :
           DatabaseUsageAnalyzer.createTableStatements.keySet()) {
        w.write("<h3 id='" + table + "'>" + table + "</h3>");
        TableDefinition def =
            DatabaseUsageAnalyzer.createTableStatements.get(table);
        String defLink = HtmlUtils.buildFileLink(repoWebUrl, repoDir, def.file,
                                                 def.lineNumber, branch);
        String dateStr =
            (def.creationDate != null)
                ? def.creationDate.format(DateTimeFormatter.ISO_LOCAL_DATE)
                : "Unknown";
        w.write("<p>Defined in: <a href=\"" + defLink + "\">" +
                repoDir.relativize(def.file) + ": line " + def.lineNumber +
                "</a>"
                + ", Created on: " + dateStr + "</p>");

        // Columns
        w.write("<h4>Columns</h4><ul>");
        List<String> cols = DatabaseUsageAnalyzer.tableColumns.getOrDefault(
            table, Collections.emptyList());
        for (String col : cols) {
          boolean used =
              DatabaseUsageAnalyzer.columnReferences.containsKey(table) &&
              DatabaseUsageAnalyzer.columnReferences.get(table).containsKey(
                  col) &&
              !DatabaseUsageAnalyzer.columnReferences.get(table)
                   .get(col)
                   .isEmpty();
          if (used) {
            w.write("<li>" + col + "</li>");
          } else {
            w.write("<li>" + col + " - <strong>UNUSED</strong></li>");
          }
        }
        w.write("</ul>");

        // References
        List<CodeReference> refs =
            DatabaseUsageAnalyzer.tableReferences.get(table);
        if (refs != null && !refs.isEmpty()) {
          Map<String, Integer> typeCounts = new LinkedHashMap<>();
          for (CodeReference cr : refs) {
            String refType = SQLParser.classifyReferenceSnippet(cr.snippet);
            typeCounts.put(refType, typeCounts.getOrDefault(refType, 0) + 1);
          }

          // Summary table
          w.write("<h4>Reference Summary</h4>");
          w.write("<table border='1' cellpadding='4' cellspacing='0'>");
          w.write("<tr><th>Type</th><th>Count</th></tr>");
          for (Map.Entry<String, Integer> entry : typeCounts.entrySet()) {
            w.write("<tr><td>" + entry.getKey() + "</td><td>" +
                    entry.getValue() + "</td></tr>");
          }
          w.write("</table>");

          // References listing
          w.write("<h4>References</h4><ul>");
          for (CodeReference cr : refs) {
            String refLink = HtmlUtils.buildFileLink(
                repoWebUrl, repoDir, cr.file, cr.lineNumber, branch);
            w.write("<li><a href=\"" + refLink + "\">" +
                    repoDir.relativize(cr.file) + ": line " + cr.lineNumber +
                    "</a> - " + HtmlUtils.escapeHtml(cr.snippet) + "</li>");
          }
          w.write("</ul>");

        } else {
          w.write("<p>No references found.</p>");
        }
        w.write("<hr>");
      }

      // Global Query Statistics
      generateQueryStatisticsSection(w, repoWebUrl, repoDir, branch);

      w.write("</body></html>");
    }
  }
  /**
   * Generates the Query Statistics section of the HTML report.
   *
   * @param w          The BufferedWriter to write to.
   * @param repoWebUrl The web URL of the repository (for linking in the
   *     report).
   * @param repoDir    The directory of the cloned repository.
   * @param branch     The branch name.
   * @throws IOException If an I/O error occurs.
   */
  private static void
  generateQueryStatisticsSection(BufferedWriter w, String repoWebUrl,
                                 Path repoDir, String branch)
      throws IOException {
    w.write("<h2>Query Statistics</h2>");

    // Queries by type
    Map<String, List<QueryInfo>> queriesByType = new HashMap<>();
    for (QueryInfo qi : queries) {
      queriesByType.computeIfAbsent(qi.type, t -> new ArrayList<>()).add(qi);
    }

    // Overall summary
    int totalQueryCount = queries.size();
    w.write("<p>Total queries found: " + totalQueryCount + "</p>");

    // Summarize queries by type
    w.write("<h3>Queries by Type</h3><ul>");
    for (Map.Entry<String, List<QueryInfo>> e : queriesByType.entrySet()) {
      w.write("<li><strong>" + e.getKey() +
              "</strong>: " + e.getValue().size() + "</li>");
    }
    w.write("</ul>");

    // Summarize complexity
    w.write("<h3>Complexity Statistics</h3>");
    w.write("<table border='1'><tr><th>Query "
            + "Type</th><th>Count</th><th>Average Complexity</th></tr>");
    for (Map.Entry<String, List<QueryInfo>> e : queriesByType.entrySet()) {
      double avg = e.getValue()
                       .stream()
                       .mapToInt(q -> q.complexity)
                       .average()
                       .orElse(0.0);
      w.write("<tr><td>" + e.getKey() + "</td><td>" + e.getValue().size() +
              "</td><td>" + String.format("%.2f", avg) + "</td></tr>");
    }
    w.write("</table>");

    // *** Distribution by File ***
    w.write("<h3>Distribution by File</h3>");
    // Group queries by file, then count them
    Map<Path, Long> countByFile = queries.stream().collect(
        Collectors.groupingBy(q -> q.file, Collectors.counting()));

    // Sort descending by count
    List<Map.Entry<Path, Long>> sortedByCount =
        countByFile.entrySet()
            .stream()
            .sorted((a, b) -> Long.compare(b.getValue(), a.getValue()))
            .toList();

    w.write("<table border='1'>");
    w.write("<tr><th>File</th><th>Query Count</th></tr>");
    for (Map.Entry<Path, Long> entry : sortedByCount) {
      Path file = entry.getKey();
      long count = entry.getValue();
      String fileLink =
          HtmlUtils.buildFileLink(repoWebUrl, repoDir, file, 1, branch);

      w.write("<tr>");
      w.write("<td><a href=\"" + fileLink + "\">" + repoDir.relativize(file) +
              "</a></td>");
      w.write("<td>" + count + "</td>");
      w.write("</tr>");
    }
    w.write("</table>");

    // Detailed usage by type
    w.write("<h3>Detailed Query Usage</h3>");
    for (Map.Entry<String, List<QueryInfo>> entry : queriesByType.entrySet()) {
      String qtype = entry.getKey();
      w.write("<h4 id='querytype_" + qtype + "'>" + qtype + " Queries</h4>");
      List<QueryInfo> typedQueries = entry.getValue();

      if (typedQueries.isEmpty()) {
        w.write("<p>No queries found for this type.</p>");
        continue;
      }

      w.write("<ul>");
      for (QueryInfo qi : typedQueries) {
        String fileLink = HtmlUtils.buildFileLink(repoWebUrl, repoDir, qi.file,
                                                  qi.lineNumber, branch);
        w.write("<li>");
        w.write("<a href=\"" + fileLink + "\">" + repoDir.relativize(qi.file) +
                ": line " + qi.lineNumber + "</a>");
        w.write(" - <strong>Complexity:</strong> " + qi.complexity);
        w.write("<br/>" + HtmlUtils.escapeHtml(qi.snippet));
        w.write("</li>");
      }
      w.write("</ul>");
    }
  }
}
