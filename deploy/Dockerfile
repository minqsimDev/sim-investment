# SIMvest 앱 이미지 — 단일 EC2(Docker Compose)용.
# 빌드 컨텍스트는 리포 루트(docker-compose.yml의 build.context: ..)
FROM python:3.12-slim

# 런타임은 pyzbar(시스템 zbar)를 쓰지 않음 — QR '생성'은 qrcode[pil](pip)뿐.
# (pyzbar는 테스트 전용이라 시스템 libzbar0 불필요)
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 계정/알림/자격증명 JSON은 Path.home() 기준 → HOME을 마운트 볼륨으로 돌려 영속화
ENV HOME=/data
RUN mkdir -p /data /app/data

EXPOSE 8520

# 0.0.0.0 바인딩(컨테이너), 프록시(Caddy)가 앞단 HTTPS 담당
CMD ["streamlit", "run", "app.py", \
     "--server.port=8520", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
