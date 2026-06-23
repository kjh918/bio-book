import paramiko

# SSH 클라이언트 객체 생성
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) # 호스트 키 자동 수락

# 원격 서버 연결
ssh.connect('192.168.0.39', username='gmctso', password='tso@gmc!!')

# 명령어 실행
stdin, stdout, stderr = ssh.exec_command('pwd')

# 결과 확인
lines = stdout.readlines()
print("".join(lines))

# 연결 종료
ssh.close()
