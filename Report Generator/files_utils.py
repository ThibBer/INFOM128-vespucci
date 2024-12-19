import os


def find_java_files(root_dir):
    java_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))
    return java_files
