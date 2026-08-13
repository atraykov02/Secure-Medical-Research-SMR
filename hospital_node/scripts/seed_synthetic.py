from hospital_node.app.config import get_settings
from hospital_node.app.db import Base, create_database_engine, create_session_factory
from hospital_node.app.seed import seed_synthetic_data


def main():
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    SessionFactory = create_session_factory(engine)
    with SessionFactory() as db:
        inserted = seed_synthetic_data(
            db,
            count=settings.synthetic_patient_count,
            seed=settings.synthetic_seed,
            node_id=settings.participant_id,
        )
    print(f"Inserted {inserted} synthetic patients for {settings.organization_name}.")


if __name__ == "__main__":
    main()
