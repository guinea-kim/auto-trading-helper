import smtplib, pickle  # smtplib: 메일 전송을 위한 패키지
from email import encoders  # 파일전송을 할 때 이미지나 문서 동영상 등의 파일을 문자열로 변환할 때 사용할 패키지
from email.mime.text import MIMEText  # 본문내용을 전송할 때 사용되는 모듈
from email.mime.multipart import MIMEMultipart  # 메시지를 보낼 때 메시지에 대한 모듈
from library import secret

def loginGmail():
    smtp = smtplib.SMTP('smtp.gmail.com', 587)
    smtp.ehlo()
    smtp.starttls()  # tls방식으로 접속, 그 포트번호가 587
    smtp.login(secret.alert_email, secret.alert_password)
    return smtp


def sendEmail(subject, message):
    smtp = loginGmail()
    msg = MIMEMultipart()  # msg obj.
    msg['Subject'] = subject

    part = MIMEText(message)
    msg.attach(part)

    # for addr in toAddr:
    msg["To"] = secret.alerted_email
    smtp.sendmail(secret.alert_email, secret.alerted_email, msg.as_string())

    smtp.quit()
def SendMessage(msg):
    try:
        sendEmail('auto trader', msg)
    except Exception as ex:
        print('에러 발생:', ex)