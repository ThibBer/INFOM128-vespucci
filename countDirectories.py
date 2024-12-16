import os


def count_directories(base_path):
    if not os.path.exists(base_path):
        print(f"Path does not exists : {base_path}")
        return 0

    directory_count = 0
    for root, dirs, files in os.walk(base_path):
        directory_count += len(dirs)

    return directory_count


if __name__ == "__main__":
    num_directories = count_directories("osmeditor4android-20.1.4.0/src/main/java/de/blau/android")
    print(f"Directories count : {num_directories}")
