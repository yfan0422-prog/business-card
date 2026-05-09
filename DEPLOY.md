# 群晖部署步骤

## 前置准备

1. 群晖已安装 Docker
2. 已注册企业微信（个人可免费注册）
3. 有公网域名或内网穿透工具

## 步骤

### 1. 复制项目到群晖

将整个 business-card-system 目录复制到群晖（如 /docker/business-card-system）

### 2. 配置企业微信

1. 访问 https://work.weixin.qq.com/
2. 注册企业微信（个人也可以注册）
3. 创建应用
4. 获取以下信息填入 .env：
   - CORP_ID：我的企业 → 企业ID
   - SECRET：应用管理 → 应用 → 自建 → Secret
   - AGENT_ID：应用管理 → 应用 → 自建 → AgentId
5. 在应用设置中配置接收消息：
   - URL: https://你的域名/wechat
   - Token: 任意填写（需与配置一致）
   - EncodingAESKey: 点击随机生成

### 3. 在群晖启动 Docker

SSH 登录群晖或使用终端：

```bash
cd /docker/business-card-system
cp .env.example .env
# 编辑 .env 填入配置
docker-compose up -d
```

### 4. 配置反向代理

在群晖控制面板 → 应用程序门户 → 反向代理：

- 源协议: HTTPS
- 源主机名: 你的域名
- 源端口: 443
- 源路径: /wechat
- 目标协议: HTTP
- 目标主机名: localhost
- 目标端口: 8000
- 目标路径: /wechat

### 5. 开始使用

在企业微信中添加应用，发送"帮助"开始使用！
