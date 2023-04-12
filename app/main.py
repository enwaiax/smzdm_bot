import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from random import randint
from urllib.parse import unquote

import prettytable as pt
import requests
from loguru import logger
from notify.notify import NotifyBot
from utils.file_helper import TomlHelper

CURRENT_PATH = Path(__file__).parent.resolve()
CONFIG_PATH = Path(CURRENT_PATH, "config")

logger.add("smzdm.log", retention="10 days")


class SmzdmBot(object):
    SIGN_KEY = "apr1$AwP!wRRT$gJ/q.X24poeBInlUJC"

    def __init__(self, conf_kwargs: dict):
        self.conf_kwargs = conf_kwargs
        self.session = requests.Session()
        self.cookies_dict = self._parser_cookies()
        self._set_header()

    def _timestamp(self):
        sleep = randint(1, 7)
        time.sleep(sleep)
        timestamp = int(time.time())
        return timestamp

    def _parser_cookies(self):
        cookies = self.conf_kwargs["ANDROID_COOKIE"]
        cookies = unquote(cookies)
        cookies_dict = {}
        result = re.findall("(.*?)=(.*?);", cookies)
        for i in result:
            key, value = i
            cookies_dict.update({key: value})
        return cookies_dict

    def _user_agent(self):
        device_smzdm = self.cookies_dict["device_smzdm"]
        device_smzdm_version = self.cookies_dict["device_smzdm_version"]
        device_smzdm_version_code = self.cookies_dict["device_smzdm_version_code"]
        device_system_version = self.cookies_dict["device_system_version"]
        device_type = self.cookies_dict["device_type"]
        try:
            USER_AGENT = f"smzdm_{device_smzdm}_V{device_smzdm_version} rv:{device_smzdm_version_code} ({device_type};{device_smzdm.capitalize()}{device_system_version};zh)smzdmapp"
        except Exception:
            USER_AGENT = "smzdm_android_V10.4.26 rv:866 (MI 8;Android10;zh)smzdmapp"
        return USER_AGENT

    def _set_header(self):
        request_key = (
            f"{randint(10000000, 100000000) * 10000000000 + self._timestamp()}"
        )
        headers = {
            # "user-agent": self.conf_kwargs["USER_AGENT"],
            "User-Agent": self._user_agent(),
            "Accept-Encoding": "gzip",
            "Request_Key": request_key,
            "Cookie": self.conf_kwargs["ANDROID_COOKIE"],
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "keep-alive",
        }
        self.session.headers = headers

    def _default_data(self):
        data = {
            "weixin": "1",
            "captcha": "",
            "f": self.cookies_dict["device_smzdm"],
            "v": self.cookies_dict["device_smzdm_version"],
            "touchstone_event": "",
            "time": self._timestamp() * 1000,
            "token": self.cookies_dict["sess"],
        }
        if self.conf_kwargs.get("SK"):
            data.update({"sk": self.conf_kwargs.get("SK")})
        return data

    def _gen_sign(self, data: dict):
        """
        sign is generated from data
        """
        sign_str = ""
        for key, value in sorted(data.items()):
            if value:
                sign_str += f"{key}={value}&"
        sign_str += f"key={self.SIGN_KEY}"
        sign = self._str_to_md5(sign_str).upper()
        return sign

    def _str_to_md5(self, m: str):
        return hashlib.md5(m.encode()).hexdigest()

    def _data(self):
        data = self._default_data()
        sign = self._gen_sign(data)
        data.update({"sign": sign})
        return data

    def checkin(self):
        url = "https://user-api.smzdm.com/checkin"
        data = self._data()
        resp = self.session.post(url, data)
        if resp.status_code == 200 and int(resp.json()["error_code"]) == 0:
            resp_data = resp.json()["data"]
            checkin_num = resp_data["daily_num"]
            gold = resp_data["cgold"]
            point = resp_data["cpoints"]
            exp = resp_data["cexperience"]
            rank = resp_data["rank"]
            cards = resp_data["cards"]
            tb = pt.PrettyTable()
            tb.field_names = ["签到天数", "金币", "积分", "经验", "等级", "补签卡"]
            tb.add_row([checkin_num, gold, point, exp, rank, cards])
            logger.info(f"\n{tb}")
            msg = f"""\n⭐签到成功{checkin_num}天
            🏅金币{gold}
            🏅积分{point}
            🏅经验{exp}
            🏅等级{rank}
            🏅补签卡{cards}"""
            return msg
        else:
            logger.error("Faile to sign in")
            msg = "Fail to login in"
            return msg

    def all_reward(self):
        url = "https://user-api.smzdm.com/checkin/all_reward"
        data = self._data()
        resp = self.session.post(url, data)
        if resp.status_code == 200 and int(resp.json()["error_code"]) == 0:
            logger.info(resp.json()["data"])

    def extra_reward(self):
        continue_checkin_reward_show = False
        userdata_v2 = self._show_view_v2()
        try:
            for item in userdata_v2["data"]["rows"]:
                if item["cell_type"] == "18001":
                    continue_checkin_reward_show = item["cell_data"][
                        "checkin_continue"
                    ]["continue_checkin_reward_show"]
                    break
        except Exception as e:
            logger.error(f"Fail to check extra reward: {e}")
        if not continue_checkin_reward_show:
            return
        url = "https://user-api.smzdm.com/checkin/extra_reward"
        data = self._data()
        resp = self.session.post(url, data)
        logger.info(resp.json()["data"])

    def _show_view_v2(self):
        url = "https://user-api.smzdm.com/checkin/show_view_v2"
        data = self._data()
        resp = self.session.post(url, data)
        if resp.status_code == 200 and int(resp.json()["error_code"]) == 0:
            return resp.json()

    def _vip(self):
        url = "https://user-api.smzdm.com/vip"
        data = self._data()
        resp = self.session.post(url, data)
        logger.info(resp.json()["data"])

    def lottery(self):
        url = "https://m.smzdm.com/zhuanti/life/choujiang/"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-cn",
            "Connection": "keep-alive",
            "Host": "m.smzdm.com",
            "User-Agent": self._user_agent(),
            "Cookie": self.conf_kwargs["ANDROID_COOKIE"],
        }
        resp = self.session.get(url, headers=headers)
        try:
            re.findall('class="chance-surplus".*?(\d)', resp.text)[0]
        except IndexError:
            logger.warning("No lottery chance left")
            return
        try:
            lottery_activity_id = re.findall(
                'name="lottery_activity_id" value="(.*?)"', resp.text
            )[0]
        except Exception:
            lottery_activity_id = "A6X1veWE2O"
        timestamp = self._timestamp()
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-cn",
            "Connection": "keep-alive",
            "Host": "zhiyou.smzdm.com",
            "Referer": "https://m.smzdm.com/zhuanti/life/choujiang/",
            "User-Agent": self._user_agent(),
            "Cookie": self.conf_kwargs["ANDROID_COOKIE"],
        }

        url = f"https://zhiyou.smzdm.com/user/lottery/jsonp_draw?callback=jQuery34109305207178886287_{timestamp}&active_id={lottery_activity_id}&_={timestamp}"

        resp = self.session.get(url, headers=headers)
        try:
            result = json.loads(re.findall(".*?\((.*?)\)", resp.text)[0])
            logger.info(result["error_msg"])
        except Exception as e:
            logger.error(e)


def load_conf():
    conf_kwargs = {}

    if Path.exists(Path(CONFIG_PATH, "config.toml")):
        logger.info("Get configration from config.toml")
        conf_kwargs = TomlHelper(Path(CONFIG_PATH, "config.toml")).read()
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
        logger.info(os.environ.get("ANDROID_COOKIE"))
        print conf_kwargs
        conf_kwargs.update({"env_conf": True})
    else:
        logger.info("Please set cookies first")
        sys.exit(1)
    return conf_kwargs


def main():
    conf_kwargs = load_conf()
    logger.info("conf_kwargs", conf_kwargs)
    logger.info("conf_kwargs*ANDROID_COOKIE", conf_kwargs["ANDROID_COOKIE"])
    msg = ""
    if conf_kwargs.get("toml_conf"):
        for i in conf_kwargs["user"]:
            if conf_kwargs["user"][i].get("Disable"):
                logger.info(f"===== Skip task for user: {i} =====")
                continue
            logger.info((f"===== Start task for user: {i} ====="))
            try:
                bot = SmzdmBot(conf_kwargs["user"][i])
                msg += bot.checkin()
                bot.all_reward()
                bot.extra_reward()
                bot.lottery()
            except Exception as e:
                logger.error(e)
                continue
        if not msg:
            logger.error("No msg generated")
            return
        NotifyBot(content=msg, **conf_kwargs["notify"])
    else:
        bot = SmzdmBot(conf_kwargs)
        msg = bot.checkin()
        bot.all_reward()
        bot.extra_reward()
        bot.lottery()
        NotifyBot(content=msg, **conf_kwargs)
    if msg is None or "Fail to login in" in msg:
        logger.error("Fail the Github action job")
        sys.exit(1)


if __name__ == "__main__":
    main()
