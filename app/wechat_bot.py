import hashlib
import base64
import json
import time
import requests
from typing import Optional, Dict, Any
from pathlib import Path
from app.config import Config


class WeChatBot:
    def __init__(self):
        self.access_token = None
        self.token_expires_at = 0

    def _get_access_token(self) -> str:
        now = time.time()
        if self.access_token and now < self.token_expires_at - 60:
            return self.access_token

        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {
            "corpid": Config.WECHAT_CORP_ID,
            "corpsecret": Config.WECHAT_SECRET
        }
        response = requests.get(url, params=params)
        data = response.json()

        if data.get("errcode") != 0:
            raise Exception(f"Failed to get access token: {data}")

        self.access_token = data["access_token"]
        self.token_expires_at = now + data["expires_in"]
        return self.access_token

    def verify_signature(self, msg_signature: str, timestamp: str, nonce: str, data: str) -> bool:
        if not Config.WECHAT_TOKEN:
            return True

        sort_list = [Config.WECHAT_TOKEN, timestamp, nonce, data]
        sort_list.sort()
        sha1 = hashlib.sha1()
        sha1.update("".join(sort_list).encode("utf-8"))
        return sha1.hexdigest() == msg_signature

    def decrypt_message(self, encrypted_msg: str) -> Dict[str, Any]:
        return {"MsgType": "text", "Content": "test", "FromUserName": "test_user"}

    def send_text_message(self, to_user: str, content: str) -> bool:
        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"

        data = {
            "touser": to_user,
            "msgtype": "text",
            "agentid": Config.WECHAT_AGENT_ID,
            "text": {"content": content}
        }

        response = requests.post(url, json=data)
        result = response.json()
        return result.get("errcode") == 0

    def send_image_message(self, to_user: str, image_path: Path) -> bool:
        if not image_path.exists():
            return False

        media_id = self._upload_image(image_path)
        if not media_id:
            return False

        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"

        data = {
            "touser": to_user,
            "msgtype": "image",
            "agentid": Config.WECHAT_AGENT_ID,
            "image": {"media_id": media_id}
        }

        response = requests.post(url, json=data)
        result = response.json()
        return result.get("errcode") == 0

    def _upload_image(self, image_path: Path) -> Optional[str]:
        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={token}&type=image"

        with open(image_path, "rb") as f:
            files = {"media": (image_path.name, f, "image/jpeg")}
            response = requests.post(url, files=files)

        result = response.json()
        if result.get("errcode") == 0:
            return result.get("media_id")
        return None

    def download_media(self, media_id: str, save_path: Path) -> bool:
        token = self._get_access_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/media/get?access_token={token}&media_id={media_id}"

        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            return True
        return False
