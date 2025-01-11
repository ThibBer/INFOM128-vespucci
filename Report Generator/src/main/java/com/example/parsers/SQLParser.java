package com.example.parsers;

import com.example.analyzer.DatabaseUsageAnalyzer;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class SQLParser {
  // SQL pattern for INSERT without column-list
  private static final Pattern INSERT_NO_COLS_PATTERN =
      Pattern.compile("(?i)INSERT\\s+INTO\\s+(\\w+)\\s+VALUES\\s*\\(");

  // SQL complexity keywords
  private static final List<String> COMPLEXITY_KEYWORDS =
      Arrays.asList("JOIN", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "UNION",
                    "EXCEPT", "INTERSECT");
  /**
   * Classifies the type of SQL query based on its content and the method used.
   *
   * @param sql    The SQL string.
   * @param method The database method used.
   * @return The classified query type.
   */
  public static String classifyQueryType(String sql, String method) {
    String upper = sql.toUpperCase();
    if (upper.contains("SELECT"))
      return "SELECT";
    if (upper.contains("INSERT INTO"))
      return "INSERT";
    if (upper.contains("UPDATE "))
      return "UPDATE";
    if (upper.contains("DELETE FROM"))
      return "DELETE";
    if (upper.contains("CREATE TABLE"))
      return "CREATE";
    // Fallback by method
    if (method.equals("query") || method.equals("rawQuery") ||
        method.equals("executeQuery"))
      return "SELECT";
    if (method.equals("insert") || method.equals("replace"))
      return "INSERT";
    if (method.equals("update"))
      return "UPDATE";
    if (method.equals("delete"))
      return "DELETE";
    return "UNKNOWN";
  }

  /**
   * Computes a naive complexity score for an SQL query based on keyword
   * occurrences and length.
   *
   * @param sql The SQL string.
   * @return The complexity score.
   */
  public static int computeQueryComplexity(String sql) {
    String upper = sql.toUpperCase();
    int complexity = 0;
    for (String kw : COMPLEXITY_KEYWORDS) {
      int idx = 0;
      while ((idx = upper.indexOf(kw, idx)) != -1) {
        complexity++;
        idx += kw.length();
      }
    }
    complexity += sql.length() / 100; // length factor
    return complexity;
  }

  /**
   * Classifies the type of SQL reference in a code snippet.
   *
   * @param snippet The code snippet containing SQL.
   * @return The classified reference type: "SELECT", "INSERT", "UPDATE",
   *         "DELETE", "CREATE", or "UNKNOWN" if none match.
   */

  public static String classifyReferenceSnippet(String snippet) {
    String upper = snippet.toUpperCase();
    if (upper.contains("SELECT"))
      return "SELECT";
    if (upper.contains("INSERT"))
      return "INSERT";
    if (upper.contains("UPDATE"))
      return "UPDATE";
    if (upper.contains("DELETE"))
      return "DELETE";
    if (upper.contains("CREATE"))
      return "CREATE";
    return "UNKNOWN";
  }
  /**
   * Parses the columns from the CREATE TABLE SQL statement.
   *
   * @param colsStr The string containing column definitions.
   * @return A list of column names.
   */
  public static List<String> parseColumns(String colsStr) {
    colsStr = colsStr.trim();
    if (colsStr.endsWith(")")) {
      colsStr = colsStr.substring(0, colsStr.length() - 1);
    }
    String[] colDefs = colsStr.split(",");
    List<String> cols = new ArrayList<>();
    Set<String> constraintKeywords = new HashSet<>(Arrays.asList(
        "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT", "KEY"));
    for (String cdef : colDefs) {
      cdef = cdef.trim();
      if (cdef.isEmpty())
        continue;
      String first = cdef.split("\\s+")[0]
                         .replaceAll("[\"\\[]", "")
                         .replaceAll("[\\]\"]", "");
      if (!constraintKeywords.contains(first.toUpperCase())) {
        cols.add(first);
      }
    }
    return cols;
  }

  /**
   * Checks if the SQL is an INSERT without column-list, e.g.:
   *   INSERT INTO directories VALUES(...)
   * If so, we can assume it references all columns for that table.
   */
  public static void checkInsertNoColsUsage(String sql, Path file, int lineNo,
                                            String snippet) {
    Matcher m = INSERT_NO_COLS_PATTERN.matcher(sql);
    if (m.find()) {
      String tableName = m.group(1); // e.g. "directories"
      if (DatabaseUsageAnalyzer.createTableStatements.containsKey(tableName)) {
        // Mark table itself as referenced
        DatabaseUsageAnalyzer.addReference(
            DatabaseUsageAnalyzer.tableReferences, tableName, "INSERT", file,
            lineNo, snippet);

        // Mark all columns as referenced
        List<String> cols = DatabaseUsageAnalyzer.tableColumns.getOrDefault(
            tableName, Collections.emptyList());
        for (String col : cols) {
          DatabaseUsageAnalyzer.addColumnReference(tableName, col, file, lineNo,
                                                   snippet);
        }
      }
    }
  }
}
