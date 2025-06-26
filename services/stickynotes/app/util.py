"""
Utility functions for database session management.

This module provides a generator function to yield a database session
using SQLAlchemy's SessionLocal. The session is properly closed after use.

Functions:
    get_db(): Yields a database session and ensures it is closed after use.
"""

from app.setup import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
