package com.example;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.VariableDeclarator;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;

import com.github.javaparser.resolution.model.SymbolReference;
import com.github.javaparser.resolution.declarations.ResolvedValueDeclaration;
import com.github.javaparser.resolution.declarations.ResolvedFieldDeclaration;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.*;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public class DatabaseUsageAnalyzer {

    // Patterns to identify CREATE TABLE statements inside SQL strings.
    private static final Pattern CREATE_TABLE_PATTERN = Pattern.compile(
            "CREATE\\s+TABLE\\s+(IF\\s+NOT\\s+EXISTS\\s+)?([A-Za-z0-9_]+)\\s*\\((.*?)\\)",
            Pattern.CASE_INSENSITIVE | Pattern.DOTALL
    );

    // SQL complexity keywords
    private static final List<String> COMPLEXITY_KEYWORDS = Arrays.asList(
            "JOIN", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "UNION", "EXCEPT", "INTERSECT"
    );

    // Set of known DB invocation methods to identify queries
    private static final List<String> DB_METHODS = Arrays.asList(
            "execSQL", "rawQuery", "query", "insert", "update", "delete", "replace",
            "compileStatement", "execute", "prepareStatement", "executeQuery"
    );

    // For certain DB methods, the first argument is a table name
    private static final Map<String, Boolean> TABLE_NAME_METHODS = new HashMap<>();
    static {
        TABLE_NAME_METHODS.put("insert", true);
        TABLE_NAME_METHODS.put("update", true);
        TABLE_NAME_METHODS.put("delete", true);
        TABLE_NAME_METHODS.put("replace", true);
    }

    // Maps from table name to file/line where it is defined
    private Map<String, TableDefinition> createTableStatements = new HashMap<>();
    // Maps from table name to its columns
    private Map<String, List<String>> tableColumns = new HashMap<>();
    // Maps from constants to their literal values
    private Map<String, String> constantsMap = new HashMap<>();

    // Where tables are referenced: table_name -> list of references
    private Map<String, List<CodeReference>> tableReferences = new HashMap<>();
    // column references: table_name -> column_name -> references
    private Map<String, Map<String, List<CodeReference>>> columnReferences = new HashMap<>();

    // Store queries for complexity analysis
    private List<QueryInfo> queries = new ArrayList<>();

    public static void main(String[] args) throws IOException {
        // Example usage:
        // Assume repoDir is the path to the local cloned repository
        // and repoUrl is the URL of the repository for linking in the report
        Path repoDir = Paths.get("repo_clone"); // Replace with your actual path
        String repoUrl = "https://github.com/username/repo"; // Replace with your actual repo URL

        DatabaseUsageAnalyzer analyzer = new DatabaseUsageAnalyzer();
        analyzer.configureSymbolSolver(repoDir);
        analyzer.runAnalysis(repoDir, repoUrl);
    }

    /**
     * Configures the JavaSymbolSolver with the project's source code.
     * This enables the resolver to find and understand symbols across the codebase.
     *
     * @param sourceRoot The root directory of the source code.
     */
    public void configureSymbolSolver(Path sourceRoot) {
        CombinedTypeSolver combinedTypeSolver = new CombinedTypeSolver();
        combinedTypeSolver.add(new ReflectionTypeSolver());
        // Add a JavaParserTypeSolver to resolve symbols from source code in repo
        combinedTypeSolver.add(new JavaParserTypeSolver(sourceRoot.toFile()));

        JavaSymbolSolver symbolSolver = new JavaSymbolSolver(combinedTypeSolver);
        ParserConfiguration config = new ParserConfiguration()
                .setSymbolResolver(symbolSolver);
        StaticJavaParser.setConfiguration(config);
    }

    /**
     * Runs the analysis by processing Java files, identifying table and column usages,
     * and generating an HTML report.
     *
     * @param repoDir The directory containing the cloned repository.
     * @param repoUrl The URL of the repository (for linking in the report).
     * @throws IOException If an I/O error occurs.
     */
    public void runAnalysis(Path repoDir, String repoUrl) throws IOException {
        // 1. Find all Java files in repoDir
        List<Path> javaFiles = findJavaFiles(repoDir);

        // 2. First pass: extract constants and find CREATE TABLE statements
        for (Path javaFile : javaFiles) {
            processFileForDefinitions(javaFile);
        }

        // 3. Second pass: find references (tables, columns, queries)
        for (Path javaFile : javaFiles) {
            processFileForReferences(javaFile);
        }

        // Identify unused tables
        List<TableDefinition> unusedTables = findUnusedTables();

        // Identify unused columns
        Map<String, List<String>> unusedCols = findUnusedColumns();

        // Generate HTML Report
        Path outputReport = repoDir.resolve("database_usage_report.html");
        generateHtmlReport(outputReport, repoUrl, repoDir, unusedTables, unusedCols);

        System.out.println("Report generated at: " + outputReport.toAbsolutePath());
    }

    /**
     * Recursively finds all Java files in the given directory.
     *
     * @param rootDir The root directory to search.
     * @return A list of paths to Java files.
     * @throws IOException If an I/O error occurs.
     */
    private List<Path> findJavaFiles(Path rootDir) throws IOException {
        try (Stream<Path> paths = Files.walk(rootDir)) {
            return paths.filter(p -> p.toString().endsWith(".java"))
                        .collect(Collectors.toList());
        }
    }

    /**
     * Processes a Java file to extract constants and identify CREATE TABLE statements.
     *
     * @param javaFile The path to the Java file.
     */
    private void processFileForDefinitions(Path javaFile) {
        try {
            CompilationUnit cu = StaticJavaParser.parse(javaFile);
            // Extract constants: look for static final String fields
            cu.findAll(FieldDeclaration.class).forEach(fd -> {
                for (VariableDeclarator var : fd.getVariables()) {
                    if (var.getType().asString().equals("String") && fd.isStatic() && fd.isFinal()) {
                        var.getInitializer().ifPresent(init -> {
                            String value = resolveStringFromInitializer(init);
                            if (value != null) {
                                constantsMap.put(var.getNameAsString(), value);
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
                            String sql = resolveStringValue(expr);
                            if (sql != null) {
                                Matcher matcher = CREATE_TABLE_PATTERN.matcher(sql);
                                if (matcher.find()) {
                                    String tableName = matcher.group(2);
                                    String cols = matcher.group(3);
                                    List<String> columns = parseColumns(cols);
                                    createTableStatements.put(tableName,
                                            new TableDefinition(tableName, javaFile, mce.getRange().map(r -> r.begin.line).orElse(1)));
                                    tableColumns.put(tableName, columns);
                                }
                            }
                        });
                    }
                }
            }, null);

        } catch (Exception e) {
            // Parsing errors - skip
            System.err.println("Failed to parse file for definitions: " + javaFile);
            e.printStackTrace();
        }
    }

    /**
     * Processes a Java file to find references to tables and columns, and collects query statistics.
     *
     * @param javaFile The path to the Java file.
     */
    private void processFileForReferences(Path javaFile) {
        try {
            CompilationUnit cu = StaticJavaParser.parse(javaFile);
            cu.accept(new VoidVisitorAdapter<Void>() {
                @Override
                public void visit(MethodCallExpr mce, Void arg) {
                    super.visit(mce, arg);
                    String methodName = mce.getNameAsString();
                    if (DB_METHODS.contains(methodName)) {
                        String sql = extractPotentialSQL(mce);
                        String qtype = classifyQueryType(sql, methodName);
                        int complexity = computeQueryComplexity(sql);
                        int lineNo = mce.getRange().map(r -> r.begin.line).orElse(1);
                        String lineSnippet = mce.toString();
                        queries.add(new QueryInfo(qtype, javaFile, lineNo, lineSnippet, complexity));

                        // If method takes a table name as first arg, resolve it
                        if (TABLE_NAME_METHODS.getOrDefault(methodName, false) && !mce.getArguments().isEmpty()) {
                            String tableArgValue = resolveStringValue(mce.getArgument(0));
                            if (tableArgValue != null && createTableStatements.containsKey(tableArgValue)) {
                                addReference(tableReferences, tableArgValue, javaFile, lineNo, lineSnippet);
                                List<String> cols = tableColumns.getOrDefault(tableArgValue, Collections.emptyList());
                                for (String col : cols) {
                                    if (lineSnippet.contains(col) || lineSnippetContainsConstantForValue(lineSnippet, col)) {
                                        addColumnReference(tableArgValue, col, javaFile, lineNo, lineSnippet);
                                    }
                                }
                            }
                        } else {
                            // For raw SQL methods, check if tables appear in snippet
                            for (String table : createTableStatements.keySet()) {
                                if (lineSnippetContainsTableOrConstant(lineSnippet, table)) {
                                    addReference(tableReferences, table, javaFile, lineNo, lineSnippet);
                                    List<String> cols = tableColumns.getOrDefault(table, Collections.emptyList());
                                    for (String col : cols) {
                                        if (lineSnippet.contains(col) || lineSnippetContainsConstantForValue(lineSnippet, col)) {
                                            addColumnReference(table, col, javaFile, lineNo, lineSnippet);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }, null);
        } catch (Exception e) {
            // Parsing errors - skip
            System.err.println("Failed to parse file for references: " + javaFile);
            e.printStackTrace();
        }
    }

    /**
     * Checks if a line snippet contains a given table name or a constant whose value is the table name.
     *
     * @param line  The line of code to check.
     * @param table The table name to look for.
     * @return True if the table is referenced, otherwise false.
     */
    private boolean lineSnippetContainsTableOrConstant(String line, String table) {
        if (line.contains(table)) {
            return true;
        }
        return lineSnippetContainsConstantForValue(line, table);
    }

    /**
     * Checks if a line snippet contains a constant whose value matches the provided value.
     *
     * @param line  The line of code to check.
     * @param value The value to match against constants.
     * @return True if a matching constant is found in the line, otherwise false.
     */
    private boolean lineSnippetContainsConstantForValue(String line, String value) {
        // Check if line references a constant whose value equals 'value'
        for (Map.Entry<String, String> e : constantsMap.entrySet()) {
            if (e.getValue().equals(value)) {
                if (line.contains(e.getKey())) return true;
            }
        }
        return false;
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
    private void addReference(Map<String, List<CodeReference>> map, String table, Path file, int line, String snippet) {
        map.computeIfAbsent(table, k -> new ArrayList<>()).add(new CodeReference(file, line, snippet));
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
    private void addColumnReference(String table, String column, Path file, int line, String snippet) {
        columnReferences.computeIfAbsent(table, t -> new HashMap<>())
                        .computeIfAbsent(column, c -> new ArrayList<>())
                        .add(new CodeReference(file, line, snippet));
    }

    /**
     * Identifies tables that are defined but never referenced.
     *
     * @return A list of unused TableDefinition objects.
     */
    private List<TableDefinition> findUnusedTables() {
        List<TableDefinition> unused = new ArrayList<>();
        for (String table : createTableStatements.keySet()) {
            if (!tableReferences.containsKey(table) || tableReferences.get(table).isEmpty()) {
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
     * Resolves the string value of an expression, handling string literals, constants, and concatenations.
     *
     * @param expr The expression to resolve.
     * @return The resolved string value, or null if it cannot be resolved.
     */
    private String resolveStringValue(Expression expr) {
        if (expr == null) return null;
        if (expr.isStringLiteralExpr()) {
            return expr.asStringLiteralExpr().getValue();
        } else if (expr.isNameExpr()) {
            NameExpr ne = expr.asNameExpr();
            try {
                ResolvedValueDeclaration ref = ne.resolve();
                if (ref instanceof ResolvedFieldDeclaration) {
                    ResolvedFieldDeclaration fieldDecl = (ResolvedFieldDeclaration) ref;
                    Optional<FieldDeclaration> fieldNode = fieldDecl.toAst()
                            .filter(FieldDeclaration.class::isInstance)
                            .map(FieldDeclaration.class::cast);
                    if (fieldNode.isPresent()) {
                        for (VariableDeclarator var : fieldNode.get().getVariables()) {
                            if (var.getNameAsString().equals(fieldDecl.getName())) {
                                return resolveStringFromInitializer(var.getInitializer().orElse(null));
                            }
                        }
                    }
                    // Fallback to constantsMap if no initializer found
                    return constantsMap.get(fieldDecl.getName());
                } else {
                    // Possibly a local variable or parameter
                    return constantsMap.get(ref.getName());
                }

            } catch (Exception e) {
                // Symbol resolution failed, fallback
                // You might want to log this
                System.err.println("Failed to resolve symbol for: " + ne.getNameAsString());
                e.printStackTrace();
            }
            return constantsMap.getOrDefault(ne.getNameAsString(), null);
        } else if (expr.isBinaryExpr()) {
            BinaryExpr be = expr.asBinaryExpr();
            if (be.getOperator() == BinaryExpr.Operator.PLUS) {
                String left = resolveStringValue(be.getLeft());
                String right = resolveStringValue(be.getRight());
                return (left != null ? left : "") + (right != null ? right : "");
            }
        }
        // If we cannot resolve directly
        return null;
    }

    /**
     * Recursively resolves the string value from an initializer expression.
     *
     * @param init The initializer expression.
     * @return The resolved string value, or null if it cannot be resolved.
     */
    private String resolveStringFromInitializer(Expression init) {
        if (init == null) return null;
        if (init.isStringLiteralExpr()) {
            return init.asStringLiteralExpr().getValue();
        } else if (init.isBinaryExpr()) {
            BinaryExpr be = init.asBinaryExpr();
            if (be.getOperator() == BinaryExpr.Operator.PLUS) {
                String left = resolveStringFromInitializer(be.getLeft());
                String right = resolveStringFromInitializer(be.getRight());
                return (left != null ? left : "") + (right != null ? right : "");
            }
        } else if (init.isNameExpr()) {
            return resolveStringValue(init);
        }
        // Could not resolve more complex cases
        return null;
    }

    /**
     * Parses the columns from the CREATE TABLE SQL statement.
     *
     * @param colsStr The string containing column definitions.
     * @return A list of column names.
     */
    private List<String> parseColumns(String colsStr) {
        colsStr = colsStr.trim();
        if (colsStr.endsWith(")")) {
            colsStr = colsStr.substring(0, colsStr.length() - 1);
        }
        String[] colDefs = colsStr.split(",");
        List<String> cols = new ArrayList<>();
        Set<String> constraintKeywords = new HashSet<>(Arrays.asList(
                "PRIMARY","FOREIGN","UNIQUE","CHECK","CONSTRAINT","KEY"
        ));
        for (String cdef : colDefs) {
            cdef = cdef.trim();
            if (cdef.isEmpty()) continue;
            String first = cdef.split("\\s+")[0].replaceAll("[\"`\\[]", "").replaceAll("[\\]\"]", "");
            if (!constraintKeywords.contains(first.toUpperCase())) {
                cols.add(first);
            }
        }
        return cols;
    }

    /**
     * Extracts potential SQL from a MethodCallExpr.
     *
     * @param mce The method call expression.
     * @return The extracted SQL string, or an empty string if not found.
     */
    private String extractPotentialSQL(MethodCallExpr mce) {
        for (Expression arg : mce.getArguments()) {
            String val = resolveStringValue(arg);
            if (val != null) {
                String upper = val.toUpperCase();
                if (upper.contains("SELECT") || upper.contains("INSERT")
                        || upper.contains("UPDATE") || upper.contains("DELETE")
                        || upper.contains("CREATE TABLE")) {
                    return val;
                }
            }
        }
        return "";
    }

    /**
     * Classifies the type of SQL query based on its content and the method used.
     *
     * @param sql    The SQL string.
     * @param method The database method used.
     * @return The classified query type.
     */
    private String classifyQueryType(String sql, String method) {
        String upper = sql.toUpperCase();
        if (upper.contains("SELECT")) return "SELECT";
        if (upper.contains("INSERT INTO")) return "INSERT";
        if (upper.contains("UPDATE ")) return "UPDATE";
        if (upper.contains("DELETE FROM")) return "DELETE";
        if (upper.contains("CREATE TABLE")) return "CREATE";
        // Fallback by method
        if (method.equals("query") || method.equals("rawQuery") || method.equals("executeQuery")) return "SELECT";
        if (method.equals("insert") || method.equals("replace")) return "INSERT";
        if (method.equals("update")) return "UPDATE";
        if (method.equals("delete")) return "DELETE";
        return "UNKNOWN";
    }

    /**
     * Computes a naive complexity score for an SQL query based on keyword occurrences and length.
     *
     * @param sql The SQL string.
     * @return The complexity score.
     */
    private int computeQueryComplexity(String sql) {
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
     * Generates an HTML report summarizing the analysis.
     *
     * @param outputPath  The path to the output HTML file.
     * @param repoUrl     The repository URL (for linking in the report).
     * @param repoDir     The directory of the cloned repository.
     * @param unusedTables A list of unused tables.
     * @param unusedCols  A map of unused columns per table.
     * @throws IOException If an I/O error occurs.
     */
    private void generateHtmlReport(Path outputPath, String repoUrl, Path repoDir,
                                    List<TableDefinition> unusedTables,
                                    Map<String, List<String>> unusedCols) throws IOException {
        try (BufferedWriter w = Files.newBufferedWriter(outputPath, StandardCharsets.UTF_8)) {
            w.write("<html><head><title>Database Table Usage Report</title></head><body>");
            w.write("<h1>Database Table Usage Report</h1>");

            // Summary
            w.write("<h2>Summary</h2>");
            w.write("<p>Total tables: " + createTableStatements.size() + "</p>");
            w.write("<p>Unused tables: " + unusedTables.size() + "</p>");
            if (!unusedTables.isEmpty()) {
                w.write("<ul>");
                for (TableDefinition td : unusedTables) {
                    w.write("<li>" + td.tableName + " (Defined in: " + repoDir.relativize(td.file) + ")</li>");
                }
                w.write("</ul>");
            }

            int totalUnusedColumns = unusedCols.values().stream().mapToInt(List::size).sum();
            w.write("<p>Unused columns: " + totalUnusedColumns + "</p>");
            if (totalUnusedColumns > 0) {
                w.write("<ul>");
                for (Map.Entry<String, List<String>> e : unusedCols.entrySet()) {
                    w.write("<li><strong>" + e.getKey() + "</strong>: " + String.join(", ", e.getValue()) + "</li>");
                }
                w.write("</ul>");
            }

            // Detailed Table Usage
            w.write("<h2>Detailed Table Usage</h2>");
            for (String table : createTableStatements.keySet()) {
                w.write("<h3 id='" + table + "'>" + table + "</h3>");
                TableDefinition def = createTableStatements.get(table);
                w.write("<p>Defined in: " + repoDir.relativize(def.file) + ", line " + def.lineNumber + "</p>");

                // Columns
                w.write("<h4>Columns</h4><ul>");
                List<String> cols = tableColumns.getOrDefault(table, Collections.emptyList());
                for (String col : cols) {
                    boolean used = columnReferences.containsKey(table) &&
                            columnReferences.get(table).containsKey(col) &&
                            !columnReferences.get(table).get(col).isEmpty();
                    if (used) {
                        w.write("<li>" + col + "</li>");
                    } else {
                        w.write("<li>" + col + " - <strong>UNUSED</strong></li>");
                    }
                }
                w.write("</ul>");

                // References
                List<CodeReference> refs = tableReferences.get(table);
                if (refs != null && !refs.isEmpty()) {
                    w.write("<h4>References</h4><ul>");
                    for (CodeReference cr : refs) {
                        w.write("<li>" + repoDir.relativize(cr.file) + ": line " + cr.lineNumber + " - " + escapeHtml(cr.snippet) + "</li>");
                    }
                    w.write("</ul>");
                } else {
                    w.write("<p>No references found.</p>");
                }

                // Column references
                w.write("<h4>Column References</h4>");
                Map<String, List<CodeReference>> colRefsMap = columnReferences.get(table);
                if (colRefsMap != null) {
                    for (String col : colRefsMap.keySet()) {
                        w.write("<h5>" + col + "</h5>");
                        List<CodeReference> colRefs = colRefsMap.get(col);
                        if (!colRefs.isEmpty()) {
                            w.write("<ul>");
                            for (CodeReference ccr : colRefs) {
                                w.write("<li>" + repoDir.relativize(ccr.file) + ": line " + ccr.lineNumber + " - " + escapeHtml(ccr.snippet) + "</li>");
                            }
                            w.write("</ul>");
                        } else {
                            w.write("<p>No references found for this column.</p>");
                        }
                    }
                }
            }

            // Query Statistics
            generateQueryStatisticsSection(w, repoDir);

            w.write("</body></html>");
        }
    }

    /**
     * Generates the Query Statistics section of the HTML report.
     *
     * @param w       The BufferedWriter to write to.
     * @param repoDir The directory of the cloned repository.
     * @throws IOException If an I/O error occurs.
     */
    private void generateQueryStatisticsSection(BufferedWriter w, Path repoDir) throws IOException {
        w.write("<h2>Query Statistics</h2>");

        // Queries by type
        Map<String, List<QueryInfo>> queriesByType = new HashMap<>();
        for (QueryInfo qi : queries) {
            queriesByType.computeIfAbsent(qi.type, t -> new ArrayList<>()).add(qi);
        }

        w.write("<h3>Queries by Type</h3><ul>");
        for (Map.Entry<String, List<QueryInfo>> e : queriesByType.entrySet()) {
            w.write("<li>" + e.getKey() + ": " + e.getValue().size() + " queries</li>");
        }
        w.write("</ul>");

        // Complexity stats
        w.write("<h3>Complexity Statistics</h3>");
        w.write("<table border='1'><tr><th>Query Type</th><th>Count</th><th>Average Complexity</th></tr>");
        for (Map.Entry<String, List<QueryInfo>> e : queriesByType.entrySet()) {
            double avg = e.getValue().stream().mapToInt(q -> q.complexity).average().orElse(0.0);
            w.write("<tr><td>" + e.getKey() + "</td><td>" + e.getValue().size() + "</td><td>" + String.format("%.2f", avg) + "</td></tr>");
        }
        w.write("</table>");

        // Distribution by file
        Map<Path, Integer> queriesByFile = new HashMap<>();
        for (QueryInfo qi : queries) {
            queriesByFile.put(qi.file, queriesByFile.getOrDefault(qi.file, 0) + 1);
        }
        List<Map.Entry<Path, Integer>> sortedByCount = new ArrayList<>(queriesByFile.entrySet());
        sortedByCount.sort((a, b) -> Integer.compare(b.getValue(), a.getValue()));

        w.write("<h3>Distribution Over Code Base</h3>");
        if (!sortedByCount.isEmpty()) {
            w.write("<ol>");
            for (Map.Entry<Path, Integer> e : sortedByCount) {
                w.write("<li>" + repoDir.relativize(e.getKey()) + ": " + e.getValue() + " queries</li>");
            }
            w.write("</ol>");
        } else {
            w.write("<p>No queries found.</p>");
        }

        // Examples
        w.write("<h3>Example Queries</h3>");
        for (Map.Entry<String, List<QueryInfo>> e : queriesByType.entrySet()) {
            w.write("<h4>" + e.getKey() + "</h4>");
            List<QueryInfo> examples = e.getValue().stream().limit(5).collect(Collectors.toList());
            if (!examples.isEmpty()) {
                w.write("<ul>");
                for (QueryInfo ex : examples) {
                    w.write("<li>" + repoDir.relativize(ex.file) + ": line " + ex.lineNumber +
                            " - " + escapeHtml(ex.snippet) +
                            " (complexity: " + ex.complexity + ")</li>");
                }
                w.write("</ul>");
            } else {
                w.write("<p>No examples.</p>");
            }
        }
    }

    /**
     * Escapes HTML characters in a string to prevent rendering issues.
     *
     * @param snippet The string to escape.
     * @return The escaped string.
     */
    private String escapeHtml(String snippet) {
        return snippet.replace("<", "&lt;").replace(">", "&gt;");
    }

    // ----- Helper Classes -----
    /**
     * Represents the definition of a database table.
     */
    static class TableDefinition {
        String tableName;
        Path file;
        int lineNumber;

        TableDefinition(String tableName, Path file, int lineNumber) {
            this.tableName = tableName;
            this.file = file;
            this.lineNumber = lineNumber;
        }
    }

    /**
     * Represents a reference to a table or column in the codebase.
     */
    static class CodeReference {
        Path file;
        int lineNumber;
        String snippet;

        CodeReference(Path file, int lineNumber, String snippet) {
            this.file = file;
            this.lineNumber = lineNumber;
            this.snippet = snippet;
        }
    }

    /**
     * Represents information about a database query.
     */
    static class QueryInfo {
        String type;
        Path file;
        int lineNumber;
        String snippet;
        int complexity;

        QueryInfo(String type, Path file, int lineNumber, String snippet, int complexity) {
            this.type = type;
            this.file = file;
            this.lineNumber = lineNumber;
            this.snippet = snippet;
            this.complexity = complexity;
        }
    }
}
