import json
from typing import Dict
from urllib.parse import urljoin

import requests
from loguru import logger


class NotifyBot(object):
    def __init__(self, content, title="什么值得买签到", **kwargs: Dict) -> None:
        self.content = content
        self.title = title
        self.kwargs = kwargs

        self.push_plus()
        self.server_chain()
        #self.wecom()
        self.qiyePush()
        
        self.tg_bot()
        
    def qiyePush(self):
        """
        https://www.cnblogs.com/ddzj01/p/12185254.html
        https://work.weixin.qq.com/api/doc/90001/90143/90372
        """
        if not self.kwargs.get("WECOM_BOT_AGENTID", None):
            logger.warning("⚠️ WECOM_BOT_AGENTID not set, skip WeCom notification")
            return
        WECOM_BOT_AGENTID = self.kwargs.get("WECOM_BOT_AGENTID")
        if not self.kwargs.get("WECOM_BOT_CORPID", None):
            logger.warning("⚠️ WECOM_BOT_CORPID not set, skip WeCom notification")
            return
        WECOM_BOT_CORPID = self.kwargs.get("WECOM_BOT_CORPID")
        if not self.kwargs.get("WECOM_BOT_SECRET", None):
            logger.warning("⚠️ WECOM_BOT_SECRET not set, skip WeCom notification")
            return
        WECOM_BOT_SECRET = self.kwargs.get("WECOM_BOT_SECRET")

        try:
            header = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.0.0"}
            # 获取access_token
            tokenUrl = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            Data = {
                "corpid": WECOM_BOT_CORPID,
                "corpsecret": WECOM_BOT_SECRET
            }
            res_token = requests.get(url=tokenUrl, params=Data,headers=header,verify=False)
            token = res_token.json()['access_token']
        
            # 发送消息
            msgUrl = "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=%s" % token
            Data = {
                "toparty": "1",  # 部门ID
                "msgtype": "text",  #
                "agentid": WECOM_BOT_AGENTID,
                "text": {"content": self.title + '\n' + self.content},
                "safe": "0"
            }
            r = requests.post(url=msgUrl, data=json.dumps(Data), verify=False)
            n = 1
            while r.json()['errcode'] != 0 and n < 4:
                n = n + 1
                #  重新获取token
                res_token = requests.get(url=tokenUrl, params=Data, verify=False)
                token = res_token.json()['access_token']
                if token:
                    msgUrl = "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=%s" % token
                    r = requests.post(url=msgUrl, data=json.dumps(Data), verify=False)
            if resp.ok:
                logger.info("✅ WeCom notified")
            else:
                logger.warning("Fail to notify WeCom")
        except Exception as e:
            logger.error(e)
    
    def push_plus(self, template="html"):
        if not self.kwargs.get("PUSH_PLUS_TOKEN", None):
            logger.warning("⚠️ PUSH_PLUS_TOKEN not set, skip PushPlus nofitication")
            return
        PUSH_PLUS_TOKEN = self.kwargs.get("PUSH_PLUS_TOKEN")

        url = "https://www.pushplus.plus/send"
        body = {
            "token": PUSH_PLUS_TOKEN,
            "title": self.title,
            "content": self.content,
            "template": template,
        }
        data = json.dumps(body).encode(encoding="utf-8")
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(url, data=data, headers=headers)
            if resp.ok:
                logger.info("✅ Push Plus notified")
            else:
                logger.warning("Fail to notify Push Plus")
        except Exception as e:
            logger.error(e)

    def server_chain(self):
        if not self.kwargs.get("SC_KEY", None):
            logger.warning("⚠️ SC_KEY not set, skip ServerChain notification")
            return
        SC_KEY = self.kwargs.get("SC_KEY")
        url = f"http://sc.ftqq.com/{SC_KEY}.send"
        data = {"text": self.title, "desp": self.content}
        try:
            resp = requests.post(url, data=data)
            if resp.ok:
                logger.info("✅ Server Chain notified")
            else:
                logger.warning("Fail to notify Server Chain")
        except Exception as e:
            logger.error(e)

    def wecom(self):
        if not self.kwargs.get("WECOM_BOT_WEBHOOK", None):
            logger.warning("⚠️ WECOM_BOT_WEBHOOK not set, skip WeCom notification")
            return
        WECOM_BOT_WEBHOOK = self.kwargs.get("WECOM_BOT_WEBHOOK")
        message = {
            "msgtype": "text",
            "text": {"content": f"{self.title}\n{self.content}"},
        }
        try:
            resp = requests.post(WECOM_BOT_WEBHOOK, data=json.dumps(message))
            if resp.ok:
                logger.info("✅ WeCom notified")
            else:
                logger.warning("Fail to notify WeCom")
        except Exception as e:
            logger.error(e)

    def tg_bot(self):
        if not self.kwargs.get("TG_BOT_TOKEN", None) or not self.kwargs.get(
            "TG_USER_ID", None
        ):
            logger.warning("⚠️ Skip TelegramBot notification")
            return
        TG_BOT_TOKEN = self.kwargs.get("TG_BOT_TOKEN")
        TG_USER_ID = self.kwargs.get("TG_USER_ID")
        if self.kwargs.get("TG_BOT_API"):
            url = urljoin(
                self.kwargs.get("TG_BOT_API"), f"/bot{TG_BOT_TOKEN}/sendMessage"
            )
        else:
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        params = {
            "chat_id": str(TG_USER_ID),
            "text": f"{self.title}\n{self.content}",
            "disable_web_page_preview": "true",
        }
        try:
            resp = requests.post(url=url, headers=headers, params=params)
            if resp.ok:
                logger.info("✅ Telegram Bot notified")
            else:
                logger.warning("Fail to notify TelegramBot")
        except Exception as e:
            logger.error(e)
