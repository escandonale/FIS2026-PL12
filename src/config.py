from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / "centro_deportivo.db"
SCHEMA = Path(__file__).parent / "resources" / "schema.sql"
