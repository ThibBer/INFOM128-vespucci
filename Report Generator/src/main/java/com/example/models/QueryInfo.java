package com.example.models;

import java.nio.file.Path;

public class QueryInfo {
  /**
   * Represents information about a database query.
   */
  public String type; // e.g. SELECT, INSERT, etc.
  public Path file;
  public int lineNumber;
  public String snippet;
  public int complexity;

  public QueryInfo(String type, Path file, int lineNumber, String snippet,
                   int complexity) {
    this.type = type;
    this.file = file;
    this.lineNumber = lineNumber;
    this.snippet = snippet;
    this.complexity = complexity;
  }
}
