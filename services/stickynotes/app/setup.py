"""
This module sets up the database connection and initialization for the StickyNotes service.

- Defines the path and URL for the SQLite database.
- Ensures the database directory exists.
- Configures SQLAlchemy engine and session maker.
- Provides `init_db()` to create all tables defined in the ORM models.

"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from shared.models.stickynotes import Base

DB_PATH = "/app/shared/db/stickynotes/stickynotes.db"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

