package com.example.models;

import java.nio.file.Path;
import java.time.LocalDateTime;

/**
 * Represents the definition of a database table.
 */
public class TableDefinition {
  public String tableName;
  public Path file;
  public int lineNumber;
  public LocalDateTime creationDate;

  public TableDefinition(String tableName, Path file, int lineNumber) {
    this.tableName = tableName;
    this.file = file;
    this.lineNumber = lineNumber;
  }
}
