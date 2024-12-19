import subprocess
import re
from pathlib import Path
from typing import Optional


def get_line_creation_date(
    repo_path: Path, file_path: Path, line_number: int
) -> Optional[str]:
    try:
        relative_path = file_path.relative_to(repo_path).as_posix()
        result = subprocess.run(
            [
                "git",
                "blame",
                "--date=iso",
                "-L",
                f"{line_number},{line_number}",
                relative_path,
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
        match = re.search(r"(\d{4}-\d{2}-\d{2})", output)
        if match:
            return match.group(1)
    except subprocess.CalledProcessError:
        pass
    return None


def clone_repository(repo_url: str, clone_path: Path) -> None:
    if not clone_path.exists():
        subprocess.run(["git", "clone", repo_url, str(clone_path)], check=True)
