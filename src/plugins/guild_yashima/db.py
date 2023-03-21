"""
封装一些数据库的操作
"""
import datetime

from peewee import *

db = DatabaseProxy()


def init_database(db_path: str):
    global db
    _db = SqliteDatabase(db_path, pragmas={
        'journal_mode': 'wal',
        'cache_size': -1 * 8000,  # 8MB
        'ignore_check_constraints': 0,
        'synchronous': 0})
    db.initialize(_db)
    _db.connect()
    _db.create_tables(models=[StreamSchedule])


class BaseModel(Model):
    id = AutoField()

    class Meta:
        database = db


class StreamSchedule(BaseModel):
    """
    直播日程
    """
    work_name = CharField(unique=True)  # 作品名称
    date_schedule = CharField()  # 计划直播日期
    time_schedule = CharField()  # 计划直播时间

    update_user_id = CharField()
    update_user_nickname = CharField()
    update_time = DateTimeField(default=datetime.datetime.now)
