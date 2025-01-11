package com.example.utils;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Stream;

public class FileUtils {
  /**
   * Recursively finds all Java files in the given directory.
   *
   * @param rootDir The root directory to search.
   * @return A list of paths to Java files.
   * @throws IOException If an I/O error occurs.
   */
  public static List<Path> findJavaFiles(Path rootDir) throws IOException {
    try (Stream<Path> paths = Files.walk(rootDir)) {
      return paths.filter(p -> p.toString().endsWith(".java")).toList();
    }
  }
}
