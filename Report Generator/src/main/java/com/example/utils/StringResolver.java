package com.example.utils;
import com.example.analyzer.DatabaseUsageAnalyzer;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.VariableDeclarator;
import com.github.javaparser.ast.expr.BinaryExpr;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.NameExpr;
import com.github.javaparser.resolution.declarations.ResolvedFieldDeclaration;
import com.github.javaparser.resolution.declarations.ResolvedValueDeclaration;
import java.util.Optional;

public class StringResolver {
  private static final org.slf4j.Logger logger =
      org.slf4j.LoggerFactory.getLogger(StringResolver.class);
  /**
   * Resolves the string value of an expression, handling string literals,
   * constants, and concatenations.
   *
   * @param expr The expression to resolve.
   * @return The resolved string value, or null if it cannot be resolved.
   */
  public static String resolveStringValue(Expression expr) {
    if (expr == null)
      return null;
    if (expr.isStringLiteralExpr()) {
      return expr.asStringLiteralExpr().getValue();
    } else if (expr.isNameExpr()) {
      NameExpr ne = expr.asNameExpr();
      try {
        ResolvedValueDeclaration ref = ne.resolve();
        if (ref instanceof ResolvedFieldDeclaration fieldDecl) {
          Optional<FieldDeclaration> fieldNode =
              fieldDecl.toAst()
                  .filter(FieldDeclaration.class ::isInstance)
                  .map(FieldDeclaration.class ::cast);
          if (fieldNode.isPresent()) {
            for (VariableDeclarator variable : fieldNode.get().getVariables()) {
              if (variable.getNameAsString().equals(fieldDecl.getName())) {
                return resolveStringFromInitializer(
                    variable.getInitializer().orElse(null));
              }
            }
          }
          // Fallback to constantsMap if no initializer found
          return DatabaseUsageAnalyzer.constantsMap.get(fieldDecl.getName());
        } else {
          // Possibly a local variable or parameter
          return DatabaseUsageAnalyzer.constantsMap.get(ref.getName());
        }

      } catch (Exception e) {
        logger.error("Failed to resolve symbol for: {}", ne.getNameAsString());
      }
      return DatabaseUsageAnalyzer.constantsMap.getOrDefault(
          ne.getNameAsString(), null);
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
  public static String resolveStringFromInitializer(Expression init) {
    if (init == null)
      return null;
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
}
