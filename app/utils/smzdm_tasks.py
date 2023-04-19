import json
import re

import prettytable as pt
from loguru import logger
from utils.smzdm_bot import SmzdmBot


class SmzdmTasks:
    def __init__(self, bot: SmzdmBot) -> None:
        self.bot = bot

    def checkin(self):
        url = "https://user-api.smzdm.com/checkin"
        resp = self.bot.session.post(url, self.bot.data())
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
            🏅金币: {gold}
            🏅积分: {point}
            🏅经验: {exp}
            🏅等级: {rank}
            🏅补签卡: {cards}"""
            return msg
        else:
            logger.error("Faile to sign in")
            msg = "Fail to login in"
            return msg

    def vip_info(self):
        msg = ""
        url = "https://user-api.smzdm.com/vip"
        resp = self.bot.session.post(url, self.bot.data())
        if resp.status_code == 200 and int(resp.json()["error_code"]) == 0:
            resp_data = resp.json()["data"]
            rank = resp_data["vip"]["exp_level"]
            exp_current_level = resp_data["vip"]["exp_current_level"]
            exp_level_expire = resp_data["vip"]["exp_level_expire"]
            tb = pt.PrettyTable()
            tb.field_names = ["值会员等级", "值会员经验", "值会员有效期"]
            tb.add_row([rank, exp_current_level, exp_level_expire])
            logger.info(f"\n{tb}")
            msg = f"""
            ⭐值会员等级: {rank}
            🏅值会员经验: {exp_current_level}
            🏅值会员有效期: {exp_level_expire}"""
        return msg

    def all_reward(self):
        msg = ""
        url = "https://user-api.smzdm.com/checkin/all_reward"
        resp = self.bot.session.post(url, self.bot.data())
        if resp.status_code == 200 and int(resp.json()["error_code"]) == 0:
            resp_data = resp.json()["data"]
            if resp_data["normal_reward"]["gift"]["title"]:
                msg = f"\n{resp_data['normal_reward']['gift']['title']}: {resp_data['normal_reward']['gift']['content_str']}"
            elif resp_data["normal_reward"]["gift"]["content_str"]:
                msg = f"\n{resp_data['normal_reward']['gift']['content_str']}: {resp_data['normal_reward']['gift']['sub_content']}"
            logger.info(msg)
        else:
            logger.info("No reward today")
        return msg

    def lottery(self):
        url = "https://m.smzdm.com/zhuanti/life/choujiang/"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-cn",
            "Connection": "keep-alive",
            "Host": "m.smzdm.com",
            "User-Agent": self.bot._user_agent(),
            "Cookie": self.bot.cookies,
        }
        resp = self.bot.session.get(url, headers=headers)
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
        timestamp = self.bot._timestamp()
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-cn",
            "Connection": "keep-alive",
            "Host": "zhiyou.smzdm.com",
            "Referer": "https://m.smzdm.com/zhuanti/life/choujiang/",
            "User-Agent": self.bot._user_agent(),
            "Cookie": self.bot.cookies,
        }

        url = f"https://zhiyou.smzdm.com/user/lottery/jsonp_draw?callback=jQuery34109305207178886287_{timestamp}&active_id={lottery_activity_id}&_={timestamp}"

        resp = self.session.get(url, headers=headers)
        try:
            result = json.loads(re.findall(".*?\((.*?)\)", resp.text)[0])
            logger.info(result["error_msg"])
        except Exception as e:
            logger.error(e)

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
        resp = self.bot.session.post(url, self.bot.data())
        logger.info(resp.json()["data"])

    def _show_view_v2(self):
        url = "https://user-api.smzdm.com/checkin/show_view_v2"
        resp = self.bot.session.post(url, self.bot.data())
        if resp.status_code == 200 and int(resp.json()["error_code"]) == 0:
            return resp.json()
