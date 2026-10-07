"""Retain the completed pre-fix topology probe separately from final evidence."""
from pathlib import Path

root = (Path(__file__).resolve().parents[1] / '.cache/performance-remediation').resolve()
source = (root / 'step-after').resolve()
target = (root / 'step-after-exploratory-topology').resolve()
assert source.is_relative_to(root) and target.is_relative_to(root)
assert source.is_dir() and not target.exists()
source.rename(target)
print(target)
