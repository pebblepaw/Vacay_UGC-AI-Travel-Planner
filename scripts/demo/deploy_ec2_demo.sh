#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
AWS_REGION="${AWS_REGION:-ap-southeast-1}"
INSTANCE_NAME="${INSTANCE_NAME:-VacayClawDemo}"
INSTANCE_TYPE="${INSTANCE_TYPE:-m7i-flex.large}"
ROOT_VOLUME_SIZE="${ROOT_VOLUME_SIZE:-40}"
ROOT_VOLUME_TYPE="${ROOT_VOLUME_TYPE:-gp3}"
SUBNET_ID="${SUBNET_ID:-subnet-0369c6fb7c0ec0059}"
VPC_ID="${VPC_ID:-vpc-029784a350488ad15}"
SECURITY_GROUP_NAME="${SECURITY_GROUP_NAME:-vacayclaw-demo-ssh}"
WORK_DIR="${WORK_DIR:-/tmp/vacayclaw-ec2-deploy}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-${AWS_ACCESS:-}}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-${AWS_SECRET:-}}"
export AWS_DEFAULT_REGION="$AWS_REGION"

if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  echo "AWS credentials are missing. Set AWS_ACCESS/AWS_SECRET or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY in $ENV_FILE" >&2
  exit 1
fi

for required_var in TELEGRAM_BOT_TOKEN TELEGRAM_WEBHOOK_SECRET MAPBOX_PUBLIC; do
  if [ -z "${!required_var:-}" ]; then
    echo "Missing required env var: $required_var" >&2
    exit 1
  fi
done

AMI_ID="${AMI_ID:-$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query 'Parameter.Value' --output text)}"
MY_IP="$(curl -4 -s https://checkip.amazonaws.com | tr -d '\n')"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
KEY_NAME="${KEY_NAME:-vacayclaw-demo-${TIMESTAMP}}"
KEY_PATH="${KEY_PATH:-$HOME/.ssh/${KEY_NAME}.pem}"

mkdir -p "$WORK_DIR"

SG_ID="$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' \
  --output text 2>/dev/null || true)"

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  SG_ID="$(aws ec2 create-security-group \
    --group-name "$SECURITY_GROUP_NAME" \
    --description 'VacayClaw demo SSH access' \
    --vpc-id "$VPC_ID" \
    --query 'GroupId' \
    --output text)"
fi

aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --ip-permissions "[{\"IpProtocol\":\"tcp\",\"FromPort\":22,\"ToPort\":22,\"IpRanges\":[{\"CidrIp\":\"${MY_IP}/32\",\"Description\":\"Codex current IP\"}]}]" \
  >/dev/null 2>&1 || true

aws ec2 create-key-pair --key-name "$KEY_NAME" --query 'KeyMaterial' --output text > "$KEY_PATH"
chmod 600 "$KEY_PATH"

INSTANCE_ID="$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_ID" \
  --associate-public-ip-address \
  --key-name "$KEY_NAME" \
  --block-device-mappings "[{\"DeviceName\":\"/dev/xvda\",\"Ebs\":{\"VolumeSize\":${ROOT_VOLUME_SIZE},\"VolumeType\":\"${ROOT_VOLUME_TYPE}\",\"DeleteOnTermination\":true}}]" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${INSTANCE_NAME}}]" \
  --query 'Instances[0].InstanceId' \
  --output text)"

aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-status-ok --instance-ids "$INSTANCE_ID"

PUBLIC_IP="$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
ARCHIVE_PATH="$WORK_DIR/vacayclaw.tar.gz"

tar \
  --exclude-vcs \
  --exclude='.env' \
  --exclude='node_modules' \
  --exclude='venv' \
  --exclude='frontend/node_modules' \
  --exclude='frontend/dist' \
  --exclude='downloads' \
  --exclude='.pytest_cache' \
  -czf "$ARCHIVE_PATH" \
  -C "$ROOT_DIR" .

until ssh -o StrictHostKeyChecking=accept-new -i "$KEY_PATH" "ec2-user@$PUBLIC_IP" 'echo ready' >/dev/null 2>&1; do
  sleep 5
done

scp -o StrictHostKeyChecking=accept-new -i "$KEY_PATH" "$ARCHIVE_PATH" "ec2-user@$PUBLIC_IP:/tmp/vacayclaw.tar.gz"
scp -o StrictHostKeyChecking=accept-new -i "$KEY_PATH" "$ENV_FILE" "ec2-user@$PUBLIC_IP:/tmp/vacayclaw.env"

ssh -o StrictHostKeyChecking=accept-new -i "$KEY_PATH" "ec2-user@$PUBLIC_IP" "
  sudo mkdir -p /opt/vacayclaw &&
  sudo chown -R ec2-user:ec2-user /opt/vacayclaw &&
  tar -xzf /tmp/vacayclaw.tar.gz -C /opt/vacayclaw &&
  cp /tmp/vacayclaw.env /opt/vacayclaw/.env &&
  cd /opt/vacayclaw &&
  bash deploy/ec2/bootstrap_host.sh
"

TUNNEL_URL="$(ssh -o StrictHostKeyChecking=accept-new -i "$KEY_PATH" "ec2-user@$PUBLIC_IP" "cd /opt/vacayclaw && bash deploy/ec2/start_stack.sh /opt/vacayclaw /opt/vacayclaw/.env" | tail -n 1)"

REMOTE_BROWSER_URL="${TUNNEL_URL}/remote-browser/vnc.html?autoconnect=true&resize=scale"

ssh -o StrictHostKeyChecking=accept-new -i "$KEY_PATH" "ec2-user@$PUBLIC_IP" "
python3 - <<'PY'
from pathlib import Path
env_path = Path('/opt/vacayclaw/.env')
updates = {
    'PUBLIC_WEB_BASE_URL': '${TUNNEL_URL}',
    'PUBLIC_API_BASE_URL': '${TUNNEL_URL}',
    'PUBLIC_REMOTE_BROWSER_URL': '${REMOTE_BROWSER_URL}',
}
lines = env_path.read_text().splitlines()
seen = set()
output = []
for line in lines:
    if '=' not in line or line.lstrip().startswith('#'):
        output.append(line)
        continue
    key, value = line.split('=', 1)
    if key in updates:
        output.append(f'{key}={updates[key]}')
        seen.add(key)
    else:
        output.append(line)
for key, value in updates.items():
    if key not in seen:
        output.append(f'{key}={value}')
env_path.write_text('\\n'.join(output) + '\\n')
PY
cd /opt/vacayclaw &&
if sudo docker compose version >/dev/null 2>&1; then
  sudo docker compose --env-file /opt/vacayclaw/.env -f /opt/vacayclaw/docker-compose.yml up -d backend nginx cloudflared
else
  sudo docker-compose --env-file /opt/vacayclaw/.env -f /opt/vacayclaw/docker-compose.yml up -d backend nginx cloudflared
fi
"

curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=${TUNNEL_URL}/api/telegram/webhook" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}" >/dev/null

cat <<EOF
INSTANCE_ID=$INSTANCE_ID
PUBLIC_IP=$PUBLIC_IP
SSH_KEY=$KEY_PATH
TUNNEL_URL=$TUNNEL_URL
REMOTE_BROWSER_URL=$REMOTE_BROWSER_URL
EOF
