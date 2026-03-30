import sys
import os
from pathlib import Path

# Add backend to sys.path to resolve imports properly
base_dir = Path(__file__).parent.resolve()
backend_dir = base_dir / "backend"
sys.path.append(str(backend_dir))

from services.tools import get_bus_trips, DB_PATH

print("DB Path:", DB_PATH)
print("Testing tool for Antalya -> Adana...")
result = get_bus_trips("Antalya", "Adana")
print("Result:")
print(result)
