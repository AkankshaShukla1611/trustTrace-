import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401
from app.models.project import Project


def test_data_survives_a_simulated_application_restart():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "trusttrace_test.db"
        db_url = f"sqlite:///{db_path}"

        # "First run" of the application.
        engine_1 = create_engine(db_url)
        Base.metadata.create_all(engine_1)
        session_1 = sessionmaker(bind=engine_1)()
        project = Project(name="Persisted Project", description="should survive a restart")
        session_1.add(project)
        session_1.commit()
        project_id = project.id
        session_1.close()
        engine_1.dispose()

        # Simulated restart: brand-new engine/session against the same file.
        engine_2 = create_engine(db_url)
        session_2 = sessionmaker(bind=engine_2)()
        reloaded = session_2.get(Project, project_id)

        assert reloaded is not None
        assert reloaded.name == "Persisted Project"
        session_2.close()
        engine_2.dispose()
