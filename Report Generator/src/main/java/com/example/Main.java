package com.example;

import com.example.utils.GitUtils;
import java.io.IOException;

/**
 * DatabaseUsageAnalyzer analyzes Java codebases and generates an HTML report
 * with detailed information and hyperlinks to the source code.
 */
public class Main {
  public static void main(String[] args) throws IOException {
    String repoUrl = "https://github.com/MarcusWolschon/osmeditor4android.git";
    String commitHash = "6286b3c1b060c882adddce29e32b28fd6f9704fa";
    GitUtils.cloneRepository(repoUrl, commitHash);
  }
}