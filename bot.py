import nonebot
from nonebot.log import logger, default_format
from nonebot.adapters.onebot.v11 import Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(Adapter)

if driver.config.is_log_file:
    logger.add("logs/bot_{time}.log", level="INFO", format=default_format, rotation="1 week")
else:
    print("不输出日志文件")

nonebot.load_from_toml("pyproject.toml")
nonebot.load_plugins("plugins")

if __name__ == "__main__":
    nonebot.run()
