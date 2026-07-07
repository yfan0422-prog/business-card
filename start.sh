#!/bin/bash
# 名片管理系统一键启动脚本（支持 HTTPS 和手机访问）

cd "$(dirname "$0")"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}📇 名片管理系统启动脚本${NC}"
echo ""

# 检查是否安装 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 请先安装 Python 3${NC}"
    exit 1
fi

# 获取本机 IP 地址
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n1 2>/dev/null || true)
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi

# 检查是否有证书，没有就生成
CERT_DIR="./certs"
CERT_KEY="$CERT_DIR/key.pem"
CERT_CRT="$CERT_DIR/cert.pem"

if [ ! -f "$CERT_KEY" ] || [ ! -f "$CERT_CRT" ]; then
    echo -e "${YELLOW}🔐 正在生成自签名 HTTPS 证书...${NC}"
    mkdir -p "$CERT_DIR"

    # 用 OpenSSL 生成证书（如果没安装 OpenSSL，提示用户）
    if command -v openssl &> /dev/null; then
        openssl req -x509 -newkey rsa:2048 -days 365 -nodes \
            -keyout "$CERT_KEY" -out "$CERT_CRT" \
            -subj "/CN=Business Card System" \
            -addext "subjectAltName = DNS:localhost, DNS:127.0.0.1, IP:$LOCAL_IP" 2>/dev/null || \
        openssl req -x509 -newkey rsa:2048 -days 365 -nodes \
            -keyout "$CERT_KEY" -out "$CERT_CRT" \
            -subj "/CN=Business Card System"
    else
        echo -e "${YELLOW}⚠️  未找到 OpenSSL，尝试用 Python 生成...${NC}"
        python3 <<END
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
try:
    import ipaddress
    has_ipaddress = True
except ImportError:
    has_ipaddress = False

# 生成私钥
key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# 生成证书
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, "Business Card System"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Local"),
])

# 构建 SAN 列表
san_list = [
    x509.DNSName("localhost"),
    x509.DNSName("127.0.0.1"),
]
if has_ipaddress:
    try:
        san_list.append(x509.IPAddress(ipaddress.ip_address("$LOCAL_IP")))
    except:
        pass

cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.utcnow()
).not_valid_after(
    datetime.utcnow() + timedelta(days=365)
).add_extension(
    x509.SubjectAlternativeName(san_list), critical=False,
).sign(key, hashes.SHA256(), default_backend())

# 保存
with open("$CERT_KEY", "wb") as f:
    f.write(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))

with open("$CERT_CRT", "wb") as f:
    f.write(cert.public_bytes(encoding=serialization.Encoding.PEM))
END
    fi

    echo -e "${GREEN}✅ 证书生成完成${NC}"
    echo ""
fi

# 安装依赖（如果需要）
echo -e "${YELLOW}📦 检查依赖...${NC}"
pip3 install -q -r requirements.txt

echo -e ""
echo -e "${GREEN}🌐 访问地址：${NC}"
echo -e "   本机（推荐）：${YELLOW}https://localhost:8443/${NC}"
if [ "$LOCAL_IP" != "127.0.0.1" ]; then
    echo -e "   手机局域网访问：${YELLOW}https://$LOCAL_IP:8443/${NC}"
fi
echo ""
echo -e "${GREEN}📱 手机使用说明：${NC}"
echo -e "   1. 确保手机和 Mac 在同一 WiFi"
echo -e "   2. 在手机浏览器打开上面的局域网地址"
echo -e "   3. 第一次会提示「不安全」，点「继续访问」或「高级」→「继续前往」"
echo -e "   4. 点击浏览器菜单 →「添加到主屏幕」，像 App 一样使用"
echo ""
echo -e "${YELLOW}⏳ 正在启动服务...${NC}"
echo ""

# 启动服务
python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8443 \
    --ssl-keyfile "$CERT_KEY" \
    --ssl-certfile "$CERT_CRT"
