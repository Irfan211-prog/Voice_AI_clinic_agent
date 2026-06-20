from app.database import Base, engine, SessionLocal
from app.scraper import seed_real_aiims_patna_data


def main():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        result = seed_real_aiims_patna_data(db)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()