import time
import smtplib
from email.message import EmailMessage
import urllib.request
import urllib.parse
import json
import os
from dotenv import load_dotenv

ALERT_COOLDOWN = {"last_alert": 0}


load_dotenv()

# Institutional Push Channels
SERVERCHAN_SENDKEY = os.getenv("SERVERCHAN_SENDKEY", "")
QQ_MAIL_USER = os.getenv("QQ_MAIL_USER", "")
QQ_MAIL_PASS = os.getenv("QQ_MAIL_PASS", "")
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465

def trigger_emergency_alert(subject: str, insight: str):
    now = time.time()
    if now - ALERT_COOLDOWN["last_alert"] < 3600:
        return
    # Removed subscriber query. We just push to admin directly.
        
    print(f"\n" + "="*50)
    print(f"[ALERT] [INSTITUTIONAL DISPATCHER] AUTOMATED EXECUTION TRIGGERED")
    print(f"Subject: 【AlphaCore 量化预警】{subject}")
    
    # 1. 微信推送 (Server酱)
    try:
        url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
        data = urllib.parse.urlencode({'title': subject, 'desp': insight}).encode('utf-8')
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as response:
            res = json.loads(response.read().decode('utf-8'))
            if res.get('code') == 0:
                print("[SUCCESS] WeChat (Server Chan) Push Sent!")
            else:
                print(f"[ERROR] WeChat (Server Chan) Push Failed: {res}")
    except Exception as e:
        print(f"[ERROR] WeChat Push Exception: {e}")

    # 2. 邮件推送 (QQ SMTP to Admin)
    try:
        msg = EmailMessage()
        msg.set_content(f"尊敬的 AlphaCore 管理员：\n\n系统监测到致命波动，触发自动预警：\n\n{insight}\n\n【本邮件由 AlphaCore 量化终端自动触发，请勿回复】")
        msg['Subject'] = f"【AlphaCore 量化预警】{subject}"
        msg['From'] = QQ_MAIL_USER
        msg['To'] = QQ_MAIL_USER # Send to self for alerting

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(QQ_MAIL_USER, QQ_MAIL_PASS)
            server.send_message(msg)
        print(f"[SUCCESS] Email sent to admin: {QQ_MAIL_USER}")
    except Exception as e:
        print(f"[ERROR] SMTP Email Exception: {e}")
        
    print(f"="*50 + "\n")
    
    ALERT_COOLDOWN["last_alert"] = now
