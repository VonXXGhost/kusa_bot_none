"""
封装一些数据库的操作
"""
from peewee import *

db = DatabaseProxy()


def init_database(db_path: str):
    global db
    _db = SqliteDatabase(db_path)
    db.initialize(db)


class BaseModel(Model):
    class Meta:
        database = db
