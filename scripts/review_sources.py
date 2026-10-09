"""Read-only research cache. Download source text, never execute upstream code."""
import json
import urllib.request
from pathlib import Path

SOURCES = {
    "Nixtla/statsforecast": ("3e6789a89f824d8a1ab0efde4f725318eb714e67", ["README.md", "LICENSE", "python/statsforecast/models.py", "python/statsforecast/core.py"]),
    "grocy/grocy": ("41206cb90154e0d17d3e108cc1f182b94fdb465d", ["README.md", "LICENSE", "services/StockService.php"]),
    "scikit-learn-contrib/MAPIE": ("f46a14b8046fa060636a96acc3692026accf25fe", ["README.md", "LICENSE", "examples/regression/1-quickstart/plot_ts-tutorial.py"]),
    "seanrsinclair/robust_censored_newsvendor": ("aa60415b1f427ec43d11ab743568256364ff0e7a", ["README.md", "LICENSE", "algorithms.py", "helper.py"]),
    "rvcrajkumar/hostel-food-waste-ai": ("3052c212d2536ff37d068c9d0f143faff8219ada", ["README.md", "LICENSE", "src/train_predictive_pipeline.py", "src/predict.py"]),
    "abhranshu/Data-Analytics-Project-Food-Waste-": ("efe7ba8eeef03e5d33b1559d2dcb008ba0b996e5", ["README.md", "model/train.py", "model/features.py"]),
}

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "artifacts" / "research"
    root.mkdir(parents=True, exist_ok=True)
    manifest = []
    for repo, (sha, paths) in SOURCES.items():
        for path in paths:
            url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
            try:
                content = urllib.request.urlopen(url, timeout=25).read()
                destination = root / repo.replace("/", "__") / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                manifest.append({"repo": repo, "commit": sha, "path": path, "url": url, "bytes": len(content)})
                print(repo, path, len(content))
            except Exception as exc:
                print("Unavailable:", repo, path, exc)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
