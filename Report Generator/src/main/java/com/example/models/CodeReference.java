package com.example.models;

import java.nio.file.Path;

public class CodeReference {
  /**
   * Represents a reference to a table or column in the codebase.
   */
  public Path file;
  public int lineNumber;
  public String snippet;
  public String refType; // e.g. SELECT, INSERT, DELETE, CREATE, etc.

  public CodeReference(Path file, int lineNumber, String snippet,
                       String refType) {
    this.file = file;
    this.lineNumber = lineNumber;
    this.snippet = snippet;
    this.refType = refType;
  }
}
