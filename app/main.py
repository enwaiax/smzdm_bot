import os
import sys
from pathlib import Path

from loguru import logger
from notify.notify import NotifyBot
from utils.file_helper import TomlHelper
from utils.smzdm_bot import SmzdmBot
from utils.smzdm_tasks import SmzdmTasks

CURRENT_PATH = Path(__file__).parent.resolve()
CONFIG_FILE = Path(CURRENT_PATH, "config/config.toml")

logger.add("smzdm.log", retention="10 days")


def load_conf():
    conf_kwargs = {}

    if Path.exists(CONFIG_FILE):
        logger.info("Get configration from config.toml")
        conf_kwargs = TomlHelper(CONFIG_FILE).read()
        conf_kwargs.update({"toml_conf": True})
    elif os.environ.get("ANDROID_COOKIE", None):
        logger.info("Get configration from env")
        conf_kwargs = {
            "SK": os.environ.get("SK"),
            "ANDROID_COOKIE": os.environ.get("ANDROID_COOKIE"),
            "PUSH_PLUS_TOKEN": os.environ.get("PUSH_PLUS_TOKEN", None),
            "SC_KEY": os.environ.get("SC_KEY", None),
            "TG_BOT_TOKEN": os.environ.get("TG_BOT_TOKEN", None),
            "TG_USER_ID": os.environ.get("TG_USER_ID", None),
            "TG_BOT_API": os.environ.get("TG_BOT_API", None),
        }
        conf_kwargs.update({"env_conf": True})
    else:
        logger.info("Please set cookies first")
        sys.exit(1)
    return conf_kwargs


def main():
    conf_kwargs = load_conf()
    msg = ""
    if conf_kwargs.get("toml_conf"):
        for user, config in conf_kwargs["user"].items():
            if config.get("Disable"):
                logger.info(f"===== Skip task for user: {user} =====")
                continue
            logger.info((f"===== Start task for user: {user} ====="))
            try:
                bot = SmzdmBot(**config)
                tasks = SmzdmTasks(bot)
                msg += tasks.checkin()
                msg += tasks.vip_info()
                msg += tasks.all_reward()
                tasks.extra_reward()
                msg += tasks.lottery()
            except Exception as e:
                logger.error(e)
                continue
        if not msg:
            logger.error("No msg generated")
            return
        NotifyBot(content=msg, **conf_kwargs["notify"])
    else:
        bot = SmzdmBot(**conf_kwargs)
        tasks = SmzdmTasks(bot)
        msg += tasks.checkin()
        msg += tasks.vip_info()
        msg += tasks.all_reward()
        tasks.extra_reward()
        msg += tasks.lottery()
        NotifyBot(content=msg, **conf_kwargs)
    if msg is None or "Fail to login in" in msg:
        logger.error("Fail the Github action job")
        sys.exit(1)


if __name__ == "__main__":
    main()
