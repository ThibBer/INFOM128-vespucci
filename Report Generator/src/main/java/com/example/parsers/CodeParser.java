package com.example.parsers;

import com.example.analyzer.DatabaseUsageAnalyzer;
import com.example.analyzer.ReportGenerator;
import com.example.models.QueryInfo;
import com.example.models.TableDefinition;
import com.example.utils.StringResolver;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.VariableDeclarator;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class CodeParser {
  private static final Logger logger =
      LoggerFactory.getLogger(CodeParser.class);
  // For certain DB methods, the first argument is a table name
  private static final Map<String, Boolean> TABLE_NAME_METHODS =
      new HashMap<>();
  static {
    TABLE_NAME_METHODS.put("insert", true);
    TABLE_NAME_METHODS.put("update", true);
    TABLE_NAME_METHODS.put("delete", true);
    TABLE_NAME_METHODS.put("replace", true);
  }

  // Patterns to identify CREATE TABLE statements inside SQL strings.
  private static final Pattern CREATE_TABLE_PATTERN =
      Pattern.compile("CREATE\\s+TABLE\\s+(IF\\s+NOT\\s+EXISTS\\s+)?([A-Za-"
                          + "z0-9_]+)\\s*\\((.*?)\\)",
                      Pattern.CASE_INSENSITIVE | Pattern.DOTALL);
  // Set of known DB invocation methods to identify queries
  private static final List<String> DB_METHODS = Arrays.asList(
      "execSQL", "rawQuery", "query", "insert", "update", "delete", "replace",
      "compileStatement", "execute", "prepareStatement", "executeQuery");
  /**
   * Processes a Java file to extract constants and identify CREATE TABLE
   * statements.
   *
   * @param javaFile The path to the Java file.
   */
  public static void processFileForDefinitions(Path javaFile) {
    try {
      CompilationUnit cu = StaticJavaParser.parse(javaFile);
      // Extract constants: look for static final String fields
      cu.findAll(FieldDeclaration.class).forEach(fd -> {
        for (VariableDeclarator variable : fd.getVariables()) {
          if (variable.getType().asString().equals("String") && fd.isStatic() &&
              fd.isFinal()) {
            variable.getInitializer().ifPresent(init -> {
              String value = StringResolver.resolveStringFromInitializer(init);
              if (value != null) {
                DatabaseUsageAnalyzer.constantsMap.put(
                    variable.getNameAsString(), value);
              }
            });
          }
        }
      });

      // Find CREATE TABLE statements inside execSQL calls
      cu.accept(new VoidVisitorAdapter<Void>() {
        @Override
        public void visit(MethodCallExpr mce, Void arg) {
          super.visit(mce, arg);
          if (mce.getNameAsString().equals("execSQL")) {
            mce.getArguments().stream().findFirst().ifPresent(expr -> {
              String sql = StringResolver.resolveStringValue(expr);
              if (sql != null) {
                Matcher matcher = CREATE_TABLE_PATTERN.matcher(sql);
                if (matcher.find()) {
                  String tableName = matcher.group(2);
                  String cols = matcher.group(3);
                  List<String> columns = SQLParser.parseColumns(cols);
                  DatabaseUsageAnalyzer.createTableStatements.put(
                      tableName,
                      new TableDefinition(
                          tableName, javaFile,
                          mce.getRange().map(r -> r.begin.line).orElse(1)));
                  DatabaseUsageAnalyzer.tableColumns.put(tableName, columns);
                }
              }
            });
          }
        }
      }, null);

    } catch (Exception e) {
      logger.error("Failed to parse file for definitions: {}", javaFile);
    }
  }

  /**
   * Processes a Java file to find references to tables and columns, and
   * collects query statistics.
   *
   * @param javaFile The path to the Java file.
   */
  public static void processFileForReferences(Path javaFile) {
    try {
      CompilationUnit cu = StaticJavaParser.parse(javaFile);
      cu.accept(new VoidVisitorAdapter<Void>() {
        @Override
        public void visit(MethodCallExpr mce, Void arg) {
          super.visit(mce, arg);
          String methodName = mce.getNameAsString();
          if (DB_METHODS.contains(methodName)) {
            // We'll parse the actual SQL from recognized DB methods
            String sql = extractPotentialSQL(mce);
            String qtype = SQLParser.classifyQueryType(sql, methodName);
            int complexity = SQLParser.computeQueryComplexity(sql);
            int lineNo = mce.getRange().map(r -> r.begin.line).orElse(1);
            String lineSnippet = mce.toString();

            // Store the query info
            if (!sql.isEmpty()) {
              ReportGenerator.queries.add(new QueryInfo(
                  qtype, javaFile, lineNo, lineSnippet, complexity));
            }

            SQLParser.checkInsertNoColsUsage(sql, javaFile, lineNo,
                                             lineSnippet);

            // CASE 1: "insert", "update", "delete", "replace" pass table name
            // as the first argument
            if (TABLE_NAME_METHODS.containsKey(methodName) &&
                !mce.getArguments().isEmpty()) {
              String tableArgValue =
                  StringResolver.resolveStringValue(mce.getArgument(0));
              if (tableArgValue != null &&
                  DatabaseUsageAnalyzer.createTableStatements.containsKey(
                      tableArgValue)) {
                DatabaseUsageAnalyzer.addReference(
                    DatabaseUsageAnalyzer.tableReferences, tableArgValue, qtype,
                    javaFile, lineNo, lineSnippet);
                // For columns in these calls, we still do a quick
                // check if any known columns appear in the SQL
                List<String> knownCols =
                    DatabaseUsageAnalyzer.tableColumns.getOrDefault(
                        tableArgValue, Collections.emptyList());
                for (String col : knownCols) {
                  if (lineSnippet.contains(col) ||
                      DatabaseUsageAnalyzer.lineSnippetContainsConstantForValue(
                          lineSnippet, col)) {
                    DatabaseUsageAnalyzer.addColumnReference(
                        tableArgValue, col, javaFile, lineNo, lineSnippet);
                  }
                }
              }
            }
            // CASE 2: For raw SQL methods like rawQuery, query, execSQL, etc.,
            // we parse the extracted SQL string
            else {
              if (!sql.isEmpty()) {
                for (String table :
                     DatabaseUsageAnalyzer.createTableStatements.keySet()) {
                  // Only record if the table is found in actual
                  // SQL usage
                  if (DatabaseUsageAnalyzer.lineSnippetContainsTableOrConstant(
                          lineSnippet, table)) {
                    DatabaseUsageAnalyzer.addReference(
                        DatabaseUsageAnalyzer.tableReferences, table, qtype,
                        javaFile, lineNo, lineSnippet);
                    // Then check if we have any known columns
                    // from that table
                    List<String> knownCols =
                        DatabaseUsageAnalyzer.tableColumns.getOrDefault(
                            table, Collections.emptyList());
                    for (String col : knownCols) {
                      if (lineSnippet.contains(col) ||
                          DatabaseUsageAnalyzer
                              .lineSnippetContainsConstantForValue(lineSnippet,
                                                                   col)) {
                        DatabaseUsageAnalyzer.addColumnReference(
                            table, col, javaFile, lineNo, lineSnippet);
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }, null);
    } catch (Exception e) {
      logger.error("Failed to parse file for references: {}", javaFile);
    }
  }

  /**
   * Extracts potential SQL from a MethodCallExpr.
   *
   * @param mce The method call expression.
   * @return The extracted SQL string, or an empty string if not found.
   */
  public static String extractPotentialSQL(MethodCallExpr mce) {
    for (Expression arg : mce.getArguments()) {
      String val = StringResolver.resolveStringValue(arg);
      if (val != null) {
        String upper = val.toUpperCase();
        if (upper.contains("SELECT") || upper.contains("INSERT") ||
            upper.contains("UPDATE") || upper.contains("DELETE") ||
            upper.contains("CREATE TABLE")) {
          return val;
        }
      }
    }
    return "";
  }
}
