from apscheduler.schedulers.background import BlockingScheduler

from main import main
from main import main, conf_kwargs

if __name__ == "__main__":
    main()
    main(conf_kwargs())
    SCH_HOUR = os.environ.get("SCH_HOUR", randint(0, 23))
    SCH_MINUTE = os.environ.get("SCH_MINUTE", randint(0, 59))
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(main, "cron", hour=SCH_HOUR, minute=SCH_MINUTE)
    scheduler.add_job(main, "cron", hour=SCH_HOUR, minute=SCH_MINUTE, args=['conf_kwargs()'])
    print("Press Ctrl+{0} to exit".format("Break" if os.name == "nt" else "C"))
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
