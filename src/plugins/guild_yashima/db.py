"""
封装一些数据库的操作
"""
import datetime
import logging
from typing import Optional, List

from peewee import *
from enum import Enum

db = DatabaseProxy()


def init_database(db_path: str):
    logger = logging.getLogger('peewee')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)

    global db
    _db = SqliteDatabase(db_path, pragmas={
        'journal_mode': 'wal',
        'cache_size': -1 * 4000,  # 4MB
        'ignore_check_constraints': 0,
        'synchronous': 0})
    db.initialize(_db)
    _db.connect()
    _db.create_tables(models=[ClockEventLog])


class BaseModel(Model):
    id = AutoField()

    class Meta:
        database = db


class ClockEventLog(BaseModel):
    """
    打卡记录
    """
    user_name = CharField()
    user_id = CharField(index=True)
    status = CharField()  # 打卡状态：参考 ClockStatus
    start_time = DateTimeField(default=datetime.datetime.now)
    end_time = DateTimeField(null=True)
    duration = IntegerField(default=0)  # 持续时长，单位分钟

    def

    @staticmethod
    def query_by_user_id_and_status(user_id: str, status: "ClockStatus") -> Optional["ClockEventLog"]:
        return (ClockEventLog.select()
                .where((ClockEventLog.status == status.value) & (ClockEventLog.user_id == user_id))
                .order_by(ClockEventLog.id.desc())
                .limit(1)
                .get_or_none())

    @staticmethod
    def query_overtime(user_id: str) -> Optional["ClockEventLog"]:
        return ClockEventLog.query_by_user_id_and_status(user_id, ClockStatus.OVERTIME)

    @staticmethod
    def query_working(user_id: str) -> Optional["ClockEventLog"]:
        return ClockEventLog.query_by_user_id_and_status(user_id, ClockStatus.WORKING)


class ClockStatus(Enum):
    WORKING = "working"  # 进行中
    FINISH = "finish"  # 已结束
    OVERTIME = "overtime"  # 超时自动签退
