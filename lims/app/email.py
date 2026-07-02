import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# ⚙️ 테스트 설정 (연구원님 환경에 맞게 수정)
# ==========================================
SMTP_SERVER = "127.0.0.1"  # 로컬 서버 자체를 가리킴 (또는 localhost)
SMTP_PORT = 25             # 기본 SMTP 포트

# 보내는 사람 (존재하지 않는 가짜 주소여도 발송 시도는 가능함)
SENDER_EMAIL = "lims-system@your-server-ip.com" 

# 받는 사람 (연구원님의 실제 사내 이메일 주소를 입력하세요!)
RECEIVER_EMAIL = "jhkim@gencurix.com" 

def run_mail_test():
    print(f"🚀 로컬 SMTP 서버({SMTP_SERVER}:{SMTP_PORT}) 연결 및 발송 시도 중...")
    
    # 메일 본문 구성
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = "🚨 [LIMS] 웹 서버 로컬 메일 발송 테스트"
    
    body = """
    안녕하세요!
    
    이 메일은 LIMS 웹 서버(localhost)의 내장 메일 데몬을 통해 직접 발송된 테스트 메일입니다.
    이 메일을 정상적으로 수신하셨다면, 서버 자체 메일 발송 기능이 정상 작동하는 것입니다! 🎉
    """
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    try:
        # 인증(ID/PW) 없이 로컬 25번 포트로 냅다 던지기
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        
        # 💡 만약 발송이 안 될 경우, 아래 줄의 주석을 풀면 어떤 단계에서 막히는지 상세 로그(디버그)를 볼 수 있습니다.
        # server.set_debuglevel(1) 
        
        server.send_message(msg)
        server.quit()
        print("\n✅ 발송 명령 성공! 수신함을 확인해 보세요.")
        print("⚠️ (주의) 사내망이 아닌 외부 메일(Gmail 등)로 보냈다면 스팸 필터에 걸려 안 올 확률이 매우 높습니다.")
        
    except ConnectionRefusedError:
        print("\n❌ 연결 거부 (Connection Refused):")
        print("서버에 메일 발송 데몬(Postfix, Sendmail 등)이 설치되어 있지 않거나 실행 중이 아닙니다.")
    except Exception as e:
        print(f"\n❌ 알 수 없는 에러 발생: {e}")

if __name__ == "__main__":
    run_mail_test()