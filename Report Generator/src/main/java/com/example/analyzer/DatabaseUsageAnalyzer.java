package com.example.analyzer;

import com.example.models.CodeReference;
import com.example.models.TableDefinition;
import com.example.parsers.CodeParser;
import com.example.utils.FileUtils;
import com.example.utils.GitUtils;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.eclipse.jgit.lib.Repository;

public class DatabaseUsageAnalyzer {
  private static final org.slf4j.Logger logger =
      org.slf4j.LoggerFactory.getLogger(DatabaseUsageAnalyzer.class);
  // Where tables are referenced: table_name -> list of references
  public static Map<String, List<CodeReference>> tableReferences =
      new HashMap<>();
  // Column references: table_name -> column_name -> references
  public static Map<String, Map<String, List<CodeReference>>> columnReferences =
      new HashMap<>();

  // Maps from table name to file/line where it is defined
  public static Map<String, TableDefinition> createTableStatements =
      new HashMap<>();
  // Maps from table name to its columns
  public static Map<String, List<String>> tableColumns = new HashMap<>();
  // Maps from constants to their literal values
  public static Map<String, String> constantsMap = new HashMap<>();

  /**
   * Runs the analysis by processing Java files, identifying table and column
   * usages, and generating an HTML report.
   *
   * @param repoDir      The directory containing the cloned repository.
   * @param repoWebUrl   The web URL of the repository (for linking in the
   *     report).
   * @param defaultBranch The default branch of the repository.
   * @param repository   The Git repository object.
   * @throws IOException If an I/O error occurs.
   */
  public void runAnalysis(Path repoDir, String repoWebUrl, String defaultBranch,
                          Repository repository) throws IOException {
    // 1. Find all Java files in repoDir
    List<Path> javaFiles = FileUtils.findJavaFiles(repoDir);

    // 2. Configure symbol solver
    configureSymbolSolver(repoDir);

    // 3. First pass: extract constants and find CREATE TABLE statements
    for (Path javaFile : javaFiles) {
      CodeParser.processFileForDefinitions(javaFile);
    }

    // 4. Perform Git blame to get creation dates for table definitions
    GitUtils.assignCreationDates(repoDir, repository);

    // 5. Second pass: find references (tables, columns, queries)
    for (Path javaFile : javaFiles) {
      CodeParser.processFileForReferences(javaFile);
    }

    // Identify unused tables
    List<TableDefinition> unusedTables = findUnusedTables();

    // Identify unused columns
    Map<String, List<String>> unusedCols = findUnusedColumns();

    // Generate HTML Report
    Path outputReport =
        Paths.get("database_usage_report.html"); // Write to the folder where
                                                 // the script is run
    ReportGenerator.generateHtmlReport(outputReport, repoWebUrl, repoDir,
                                       unusedTables, unusedCols, defaultBranch);

    logger.info("Report generated at: {}", outputReport.toAbsolutePath());
  }

  /**
   * Identifies tables that are defined but never referenced.
   *
   * @return A list of unused TableDefinition objects.
   */
  private List<TableDefinition> findUnusedTables() {
    List<TableDefinition> unused = new ArrayList<>();
    for (Map.Entry<String, TableDefinition> entry :
         createTableStatements.entrySet()) {
      String table = entry.getKey();
      List<CodeReference> refs = tableReferences.get(table);

      // If there are no references at all, the table is obviously unused
      if (refs == null || refs.isEmpty()) {
        unused.add(createTableStatements.get(table));
        continue;
      }

      // Filter out references that are creation references only
      // i.e., references whose refType is "CREATE" or whose snippet
      // specifically includes "CREATE TABLE"
      List<CodeReference> nonCreationRefs =
          refs.stream().filter(cr -> !isCreationReference(cr)).toList();

      // If after filtering, we have 0 references left, it's unused
      if (nonCreationRefs.isEmpty()) {
        unused.add(createTableStatements.get(table));
      }
    }
    return unused;
  }

  /**
   * Identifies columns that are defined but never referenced.
   *
   * @return A map of table names to lists of unused column names.
   */
  private Map<String, List<String>> findUnusedColumns() {
    Map<String, List<String>> unused = new HashMap<>();
    for (Map.Entry<String, List<String>> e : tableColumns.entrySet()) {
      String table = e.getKey();
      for (String col : e.getValue()) {
        if (!columnReferences.containsKey(table) ||
            !columnReferences.get(table).containsKey(col) ||
            columnReferences.get(table).get(col).isEmpty()) {
          unused.computeIfAbsent(table, t -> new ArrayList<>()).add(col);
        }
      }
    }
    return unused;
  }
  /**
   * Adds a reference to the tableReferences map.
   *
   * @param map     The map to update.
   * @param table   The table name.
   * @param file    The file where the reference occurs.
   * @param line    The line number of the reference.
   * @param snippet The code snippet containing the reference.
   */
  public static void addReference(Map<String, List<CodeReference>> map,
                                  String table, String refType, Path file,
                                  int line, String snippet) {
    map.computeIfAbsent(table, k -> new ArrayList<>())
        .add(new CodeReference(file, line, snippet, refType));
  }

  /**
   * Adds a reference to the columnReferences map.
   *
   * @param table   The table name.
   * @param column  The column name.
   * @param file    The file where the reference occurs.
   * @param line    The line number of the reference.
   * @param snippet The code snippet containing the reference.
   */
  public static void addColumnReference(String table, String column, Path file,
                                        int line, String snippet) {
    columnReferences.computeIfAbsent(table, t -> new HashMap<>())
        .computeIfAbsent(column, c -> new ArrayList<>())
        .add(new CodeReference(file, line, snippet, "COLUMN_REF"));
  }

  /**
   * Decide if a reference is just table creation (i.e. we want to exclude it
   * from usage).
   */
  private boolean isCreationReference(CodeReference cr) {
    // If the code reference type is "CREATE", we treat it as creation.
    // OR if the snippet itself contains "CREATE TABLE" (case-insensitive).
    String snippetUpper = cr.snippet.toUpperCase();
    if (cr.refType.equalsIgnoreCase("CREATE")) {
      return true;
    }
    return snippetUpper.contains("CREATE TABLE");
  }

  /**
   * Checks if a line snippet contains a given table name or a constant whose
   * value is the table name.
   *
   * @param line  The line of code to check.
   * @param table The table name to look for.
   * @return True if the table is referenced, otherwise false.
   */
  public static boolean lineSnippetContainsTableOrConstant(String line,
                                                           String table) {
    if (line.contains(table)) {
      return true;
    }
    return lineSnippetContainsConstantForValue(line, table);
  }

  /**
   * Checks if a line snippet contains a constant whose value matches the
   * provided value.
   *
   * @param line  The line of code to check.
   * @param value The value to match against constants.
   * @return True if a matching constant is found in the line, otherwise false.
   */
  public static boolean lineSnippetContainsConstantForValue(String line,
                                                            String value) {
    // Check if line references a constant whose value equals 'value'
    for (Map.Entry<String, String> e : constantsMap.entrySet()) {
      if (e.getValue().equals(value) && line.contains(e.getKey())) {
        return true;
      }
    }
    return false;
  }

  /**
   * Configures the JavaSymbolSolver with the project's source code.
   * This enables the resolver to find and understand symbols across the
   * codebase.
   *
   * @param sourceRoot The root directory of the source code.
   */
  public void configureSymbolSolver(Path sourceRoot) {
    CombinedTypeSolver combinedTypeSolver = new CombinedTypeSolver();
    combinedTypeSolver.add(new ReflectionTypeSolver());
    // Add a JavaParserTypeSolver to resolve symbols from source code in repo
    combinedTypeSolver.add(new JavaParserTypeSolver(sourceRoot.toFile()));

    JavaSymbolSolver symbolSolver = new JavaSymbolSolver(combinedTypeSolver);
    ParserConfiguration config =
        new ParserConfiguration().setSymbolResolver(symbolSolver);
    StaticJavaParser.setConfiguration(config);
  }
}
