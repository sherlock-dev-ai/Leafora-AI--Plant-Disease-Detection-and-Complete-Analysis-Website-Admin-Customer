
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

with app.app_context():
    inspector = inspect(db.engine)
    for table_name in inspector.get_table_names():
        print(f"Table: {table_name}")
        for column in inspector.get_columns(table_name):
            print(f"  Column: {column['name']} ({column['type']})")
        print("-" * 20)
