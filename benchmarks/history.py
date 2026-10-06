"""
Keep the benchmark history that index.html charts.

    python benchmarks/history.py record REPORT DATA_JS   # add a pytest-benchmark JSON report
    python benchmarks/history.py check DATA_JS           # fail if the last run regressed

Each run keeps each benchmark's fastest round, which varies less between runs than the mean, and
the peak memory of the benchmarks that record it.
"""

import json
from pathlib import Path
import subprocess
import sys
import time

REPO_URL = "https://github.com/ImageMarkup/isic"
PREFIX = "window.BENCHMARK_DATA = "
# Shared runners are noisy, and each run is on a different runner than the run before it, so only
# large changes fail.
THRESHOLD = 1.5


def load(path: Path) -> dict:
    if not path.exists():
        return {"repoUrl": REPO_URL, "entries": {"Benchmark": []}}
    return json.loads(path.read_text().removeprefix(PREFIX))


def record(report_path: Path, data_path: Path) -> None:
    report = json.loads(report_path.read_text())
    commit = report["commit_info"]
    message = subprocess.run(
        ["git", "show", "--no-patch", "--format=%B", commit["id"]],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    data = load(data_path)
    data["lastUpdate"] = time.time() * 1000
    data["entries"]["Benchmark"].append(
        {
            "commit": {
                "id": commit["id"],
                "message": message,
                "timestamp": commit["time"],
                "url": f"{data['repoUrl']}/commit/{commit['id']}",
            },
            "benches": [
                {
                    "name": benchmark["fullname"],
                    "value": benchmark["stats"]["min"] * 1000,
                    "unit": "ms",
                }
                for benchmark in report["benchmarks"]
            ]
            + [
                {
                    "name": f"{benchmark['fullname']} peak memory",
                    "value": benchmark["extra_info"]["peak_memory_mib"],
                    "unit": "MiB",
                }
                for benchmark in report["benchmarks"]
                if "peak_memory_mib" in benchmark["extra_info"]
            ],
        }
    )
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(PREFIX + json.dumps(data))


def check(data_path: Path) -> None:
    runs = load(data_path)["entries"]["Benchmark"]
    if len(runs) < 2:
        return

    previous = {bench["name"]: bench["value"] for bench in runs[-2]["benches"]}
    regressions = [
        f"{bench['name']}: {previous[bench['name']]:.3g} -> {bench['value']:.3g} {bench['unit']}"
        for bench in runs[-1]["benches"]
        if bench["name"] in previous and bench["value"] > previous[bench["name"]] * THRESHOLD
    ]
    if regressions:
        sys.exit(
            f"More than {THRESHOLD:.0%} of the run before ({runs[-2]['commit']['id']}):\n"
            + "\n".join(regressions)
        )


if len(sys.argv) == 4 and sys.argv[1] == "record":
    record(Path(sys.argv[2]), Path(sys.argv[3]))
elif len(sys.argv) == 3 and sys.argv[1] == "check":
    check(Path(sys.argv[2]))
else:
    sys.exit(__doc__)
