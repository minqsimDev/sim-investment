# SIM INVESTMENT — AWS 단일 EC2 저비용 배포 가이드

새 AWS 계정의 **Free Tier(12개월)** 기반으로 SIM INVESTMENT를 **단일 EC2 + Docker Compose + Caddy 자동 HTTPS**로 운영한다.
**ALB · NAT Gateway · RDS · ECS · CloudFront 미사용**(비용 최소화).

> ⚠️ **이 앱은 단일 인스턴스 전용이다.** 상태가 로컬 파일(`~/.siminvest_accounts.json`, `alerts.json`, `data/market_data.db`)이고 동시성 보호가 **fcntl 파일락(한 호스트 한정)**이다. **오토스케일·다중 인스턴스 금지** — 그럴 경우 락이 무력화되고 상태가 쪼개진다. 수평 확장이 필요해지면 상태를 외부 DB로 옮기는 별도 작업이 선행되어야 한다.

---

## 💸 비용 요약 (먼저 읽기)

Free Tier로 **EC2 컴퓨팅·EBS·데이터전송은 12개월 무료**지만, 아래는 **Free Tier로 덮이지 않는 소액 과금**이라 README에 명시한다:

| 항목 | 대략 비용 | 비고 |
|---|---|---|
| **Public IPv4 / Elastic IP** | **~$3.6/월** ($0.005/시간) | 2024-02부터 모든 공인 IPv4 과금. 실행 중 인스턴스에 붙은 EIP도 해당 |
| **Route53 Hosted Zone** | **$0.50/월** | Route53로 DNS 운영 시. *등록기관 자체 DNS를 쓰면 0원* |
| **도메인 등록비** | 연 ~$10–15 | 등록기관/도메인별 상이 (Route53 또는 외부) |
| EC2 t2/t3.micro 750h | $0 (12개월) | 이후 ~$8–9/월 |
| EBS 30GB gp3 | $0 (12개월) | 30GB 이하 Free Tier 한도 내 |
| 데이터 전송(아웃) 100GB/월 | $0 | Free Tier |

→ **실질 월 고정비 ≈ $4 내외**(IPv4 + Route53), 12개월 후 EC2 요금이 추가된다. 12장(AWS Budgets)으로 알람을 건다.

---

## 0. 사전 준비
- AWS 새 계정(루트 MFA 설정 권장), 리전 1개 선택(예: `ap-northeast-2` 서울).
- 도메인 — **별도 구매 불필요**(기본은 무료 `sslip.io`, 8장). 보유/구매 도메인도 가능.
- 로컬에 SSH 키페어.

## 1. EC2 인스턴스 시작
1. EC2 → **Launch instance**
2. AMI: **Ubuntu Server 24.04 LTS** (Free tier eligible)
3. 인스턴스 타입: **t2.micro 또는 t3.micro** — 콘솔에 **"Free tier eligible"** 라벨 있는 것
4. 키페어: 기존/신규 선택
5. 스토리지: **30GB gp3**(= Free Tier EBS 한도). 더 줄여도 됨
6. 보안그룹: 4장 참고로 설정
7. Launch

> 1GB RAM(t*.micro)은 pandas/streamlit엔 빠듯하다 → **5장에서 스왑 2GB** 추가(필수).

## 2. Elastic IP 할당 → **토스 허용목록 등록**
1. EC2 → **Elastic IPs** → **Allocate** → 방금 인스턴스에 **Associate**
2. 이 **Elastic IP**를 **토스증권 개발자 콘솔 → 허용 IP**에 등록(안 하면 시세 403).
   - EIP는 고정이라 재시작에도 안 바뀐다(클라우드에서 IP 유동 문제 해결).

## 3. 접속 + 시스템 준비
```bash
ssh -i <key.pem> ubuntu@<ELASTIC_IP>
sudo apt update && sudo apt -y upgrade
```

## 4. 보안그룹 (인바운드)
| 포트 | 소스 | 용도 |
|---|---|---|
| 22 (SSH) | **내 IP만** | 관리 |
| 80 (HTTP) | 0.0.0.0/0 | Caddy ACM 챌린지·HTTP→HTTPS 리다이렉트 |
| 443 (HTTPS) | 0.0.0.0/0 | 서비스 |
| 8520 | **열지 않음** | 앱은 Caddy 경유만 |

## 5. 스왑 2GB (1GB RAM 대비, 필수)
```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 6. Docker + Compose 설치
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
# 그룹 반영 위해 재로그인(exit 후 다시 ssh)
exit
```

## 7. 코드 가져오기 + 시크릿(.env)
```bash
ssh -i <key.pem> ubuntu@<ELASTIC_IP>
git clone https://github.com/minqsimDev/sim-investment.git
cd sim-investment/deploy
cp .env.example .env && chmod 600 .env
nano .env     # DOMAIN + 모든 키 입력(토스 키 포함). .env는 깃·이미지에 안 들어감
```
> 시크릿을 더 단단히 하려면 AWS **SSM Parameter Store(표준 파라미터 무료)** 에 넣고 부팅 시 주입하는 방식으로 바꿀 수 있다(후속 옵션). 본 가이드는 최소구성으로 호스트 `.env`(600 권한) 사용.

## 8. 도메인 설정 — sslip.io (무료·기본) 또는 보유 도메인
**기본(무료·DNS 설정 0): `sslip.io`** — Elastic IP의 점을 대시로 바꾼 `<EIP>.sslip.io`가 자동으로 그 IP로 해석된다. **DNS 레코드를 만들 필요 없이** `.env`의 `DOMAIN`에 넣기만 하면 Caddy가 인증서를 발급한다.
- 예: EIP `3.34.56.78` → `.env` 에 `DOMAIN=3-34-56-78.sslip.io`
- Route53/등록기관 비용 0, A레코드 관리 불필요.

**대안(보유/구매 도메인):**
- 보유 도메인: 등록기관 DNS에서 **A레코드 → Elastic IP** (Route53 안 써도 0원)
- Route53: Hosted zone($0.50/월) → A레코드 → EIP

> `.env`의 `DOMAIN`과 실제 해석되는 호스트명이 **일치**해야 Caddy 인증서가 발급된다.
> sslip.io는 공용 도메인이라 드물게 Let's Encrypt 주간 발급 한도(공유)에 걸릴 수 있다 — 실패 시 잠시 후 재시도하거나 DuckDNS(무료·PSL 등록)·보유 도메인으로 전환.

## 9. 실행 — GHCR 이미지 받아 띄우기 (EC2 빌드 없음)
이미지는 **GitHub Actions가 main 푸시마다 GHCR(`ghcr.io/minqsimdev/sim-investment`)에 빌드·푸시**(linux/amd64)한다. EC2는 빌드하지 않고 **pull만** 한다.

> **GHCR 접근**: 패키지가 **Public 이면 로그인 불필요**(권장 — 이미지엔 시크릿 없음, `.dockerignore`로 `.env` 제외). 최초 푸시 후 GitHub → 패키지 페이지 → *Package settings → Change visibility → Public*.
> Private로 두려면 EC2에서 1회 로그인:
> ```bash
> echo <GHCR_READ_PAT> | docker login ghcr.io -u <github계정> --password-stdin   # PAT: read:packages 권한
> ```

```bash
cd ~/sim-investment/deploy
docker compose pull          # GHCR에서 최신 이미지 받기
docker compose up -d
docker compose logs -f caddy   # 인증서 발급 로그 확인(Ctrl+C로 빠져나옴)
```
→ `.env`의 `DOMAIN`(예: `https://3-34-56-78.sslip.io`)으로 접속. Caddy가 Let's Encrypt 인증서를 자동 발급·갱신한다(추가비용 0). 상태 파일은 `deploy/state/`·`deploy/appdata/`(호스트 EBS)에 영속.

> ⚠️ 최초 배포 전 **Actions 빌드가 1회 성공**해 GHCR에 `latest` 이미지가 있어야 pull 된다(이 변경을 main에 머지하면 자동 실행). Actions 탭에서 `build-image` 초록불 확인.

## 10. 일배치(main.py) — 지표 DB·텔레그램 평가 (자동, 추가 설정 불필요)
`docker compose up -d` 에 **`batch` 사이드카**(`deploy/batch_scheduler.py`)가 포함돼 있어 **자동**으로:
- 매일 **KST 06:00**(`.env`의 `BATCH_HOUR`로 조정) `main.py` 실행 → `market_data.db` 갱신·텔레그램 평가
- 장중에는 `SNAPSHOT_INTERVAL_SEC`(기본 600s)마다 시세 스냅샷으로 quotes 워밍

→ **별도 host cron 불필요.** (`docker compose ps` 에 `batch` 컨테이너가 떠 있으면 동작 중.)

> ⚠️ host cron 으로 `main.py` 를 또 걸지 말 것 — 사이드카와 **이중 실행**된다. 사이드카를 끄고 cron 만 쓰려면 compose 의 `batch` 서비스를 제거한 뒤 아래를 사용:
> ```bash
> crontab -e
> 10 6 * * * cd /home/ubuntu/sim-investment/deploy && docker compose run --rm app python main.py >> /home/ubuntu/batch.log 2>&1
> ```
> 서버 시간대 확인: `timedatectl`. 필요시 `sudo timedatectl set-timezone Asia/Seoul`.

## 11. 업데이트 / 롤백
코드를 main에 머지하면 Actions가 새 이미지를 GHCR에 푸시한다. EC2에서:
```bash
cd ~/sim-investment && git pull            # compose/Caddyfile 등 변경 반영(있을 때만)
cd deploy && docker compose pull && docker compose up -d   # 최신 이미지로 재기동
```
**롤백**: `.env`에 이전 태그를 지정하고 재기동(Actions가 커밋 SHA 태그도 푸시함).
```bash
echo 'IMAGE_TAG=sha-<이전커밋>' >> .env     # 예: sha-3d2e03d (GHCR 패키지 페이지에서 태그 확인)
docker compose up -d
```
상태(`deploy/state`, `deploy/appdata`)는 코드 배포와 분리되어 보존된다.

## 12. AWS Budgets 비용 알람 (필수)
예상치 못한 과금을 막는다(Budgets는 2개까지 무료).
1. AWS 콘솔 → **Billing and Cost Management → Budgets → Create budget**
2. 템플릿: **Monthly cost budget**(또는 **Zero spend budget**)
3. 금액: 예 **$5**(여유). 알림 임계: **실제 비용 80%·100%**, **예측 100%**
4. 알림 수신 이메일 입력 → 생성
5. (선택) **Billing → Billing preferences**에서 *Free Tier usage alerts*·*CloudWatch billing alerts* 켜기

## 13. 백업
상태 파일을 주기적으로 백업(계정·포트폴리오·알림 설정):
```bash
# 예: 일 1회 tar로 묶어 보관(원하면 S3로 업로드 — S3는 별도 소액)
tar czf ~/simvest-state-$(date +%F).tgz -C ~/sim-investment/deploy state appdata
```

---

## 부록 — 트러블슈팅
- **시세 403 / 빈 화면**: 토스 허용목록에 **현재 Elastic IP** 등록됐는지 확인.
- **HTTPS 발급 실패**: `.env` DOMAIN이 EIP를 가리키는지(sslip.io면 대시 표기 정확한지), 보안그룹 80/443 열렸는지 확인. `docker compose logs caddy`. sslip.io 한도 에러면 잠시 후 재시도하거나 DuckDNS/보유 도메인으로 전환.
- **앱 OOM/재시작 반복**: 스왑(5장) 적용 여부 확인. `free -h`, `docker stats`.
- **웹소켓 끊김**: Caddy `reverse_proxy`는 ws 자동 통과. 그래도 문제면 단일 도메인·동일 출처인지 확인.
- **포트 8520 외부 노출 금지**: 보안그룹에서 8520 인바운드 없음(앱은 Caddy 경유만).
