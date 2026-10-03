import os
from sqlalchemy import create_engine
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/complaints')
engine = create_engine(DATABASE_URL)
