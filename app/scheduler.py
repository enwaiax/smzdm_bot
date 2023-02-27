import os
from random import randint

from apscheduler.schedulers.background import BlockingScheduler
from loguru import logger
from main import main

if __name__ == "__main__":
    logger.info("First time run")
    main()
    SCH_HOUR = randint(0, 23) if not os.environ.get("SCH_HOUR") else os.environ.get("SCH_HOUR")
    SCH_MINUTE = randint(0, 59) if not os.environ.get("SCH_HOUR") else os.environ.get("SCH_HOUR")
    logger.info(f"The scheduelr time is: {SCH_HOUR}:{SCH_MINUTE}")
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(main, "cron", hour=SCH_HOUR, minute=SCH_MINUTE)
    print("Press Ctrl+{0} to exit".format("Break" if os.name == "nt" else "C"))
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
