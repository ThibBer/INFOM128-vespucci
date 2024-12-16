import os
import re

db_call_pattern = re.compile(r'(\w+)\.(\w+)(\(.+\))')
java_calls = {
    "select": [],
    "insert": [],
    "delete": [],
    "update": [],
    "execSQL": [],
    "rawQuery": [],
    "createTable": [],
    "alterTable": [],
}

java_files_with_queries = []

database_object_names = ["db", "database", "mdatabase"]


def get_java_files(directory):
    java_files = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))

    return java_files


if __name__ == '__main__':
    path = "osmeditor4android-20.1.4.0/src/main/java/de/blau/android/"
    out_dir = "./Home made analyzer"
    print("Start analyze code")
    java_files = get_java_files(path)

    if os.path.exists(out_dir):
        os.rmdir(out_dir)

    print("Create out directory " + out_dir)
    os.mkdir(out_dir)
    os.mkdir(out_dir + "/detailed")
    os.mkdir(out_dir + "/simple")

    for file in java_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                for line_number, line in enumerate(f, start=1):
                    matches = db_call_pattern.finditer(line)
                    for match in matches:
                        all_data = match.group(0)
                        object_name = match.group(1)
                        function_name = match.group(2)
                        data = match.group(3)

                        if object_name.lower() not in database_object_names:
                            continue

                        if function_name not in java_calls:
                            continue

                        java_files_with_queries.append(file)

                        if "create table" in data.lower():
                            java_calls["createTable"].append({
                                'line': line_number,
                                'file': file,
                                'complete_call': all_data
                            })
                        elif "alter table" in data.lower() or "alter_table" in data.lower():
                            java_calls["alterTable"].append({
                                'line': line_number,
                                'file': file,
                                'complete_call': all_data
                            })
                        elif function_name == "query":
                            java_calls["select"].append({
                                'line': line_number,
                                'file': file,
                                'complete_call': all_data
                            })
                        elif "select" in data.lower():
                            java_calls["select"].append({
                                'line': line_number,
                                'file': file,
                                'complete_call': all_data
                            })
                        elif "insert" in data.lower():
                            java_calls["insert"].append({
                                'line': line_number,
                                'file': file,
                                'complete_call': all_data
                            })
                        elif "update" in data.lower():
                            java_calls["update"].append({
                                'line': line_number,
                                'file': file,
                                'complete_call': all_data
                            })
                        elif "delete" in data.lower():
                            java_calls["delete"].append({
                                'line': line_number,
                                'file': file,
                                'complete_call': all_data
                            })
                        else:
                            java_calls[function_name].append({
                                'line': line_number,
                                'file': file,
                                'complete_call': all_data
                            })

                        # print(file.replace(path, "").replace("\\", "/"), "#" + str(line_number), all_data, function_name)

        except Exception as e:
            print(f"Erreur lors de la lecture du fichier {file_path}: {e}")

    for function_name in java_calls.keys():
        calls = java_calls[function_name]
        f = open(os.path.join(out_dir + "/detailed", function_name + ".txt"), "a")
        f_simple = open(os.path.join(out_dir + "/simple", function_name + ".txt"), "a")
        f_all = open(os.path.join(out_dir, "all.txt"), "a")

        for call in calls:
            f.write(call["file"] + "|" + str(call["line"]) + "|" + call["complete_call"] + "\n")
            f_simple.write(call["complete_call"] + "\n")
            f_all.write(call["complete_call"] + "\n")

        f_simple.close()
        f_all.close()

    java_files = open(os.path.join(out_dir, "javaFilesWithSqlQuery.txt"), "a")
    for java_file_with_queries in list(dict.fromkeys(java_files_with_queries)):
        java_files.write(java_file_with_queries + "\n")

    java_files.close()
