import sys
from pathlib import Path

# Add project root directory (SIH) and iceberg_intelligence to sys.path for pytest module resolution
PROJECT_ROOT = Path(__file__).resolve().parent
ICEBERG_INTEL = PROJECT_ROOT / "iceberg_intelligence"

for path in [PROJECT_ROOT, ICEBERG_INTEL]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
