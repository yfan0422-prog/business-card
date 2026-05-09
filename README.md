# 名片管理系统

基于企业微信的名片管理系统，支持拍照录入、智能搜索、名片卡片生成。

## 功能特性

- 通过企业微信机器人录入名片
- 手动输入名片信息
- 多种方式搜索（姓名、公司、全文）
- 生成美观的名片卡片图片
- 公司联系人聚合展示
- 数据全部存储在本地

## 部署指南

### 1. 企业微信配置

1. 登录企业微信管理后台
2. 创建应用，获取：
   - CORP_ID（我的企业 - 企业ID）
   - SECRET（应用管理 - 应用 - 自建 - Secret）
   - AGENT_ID（应用管理 - 应用 - 自建 - AgentId）
3. 配置接收消息服务器：
   - URL: https://your-domain.com/wechat
   - Token: 自定义
   - EncodingAESKey: 随机生成

### 2. 本地运行

```bash
cd /Users/yfan/business-card-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入配置
uvicorn app.main:app --reload
```

### 3. Docker 部署（群晖）

```bash
cd /Users/yfan/business-card-system
cp .env.example .env
# 编辑 .env 填入配置
docker-compose up -d
```

### 4. 中文字体

将中文字体文件（如 SimSun.ttf）放入 `fonts/` 目录。

群晖系统可从以下位置复制字体：
```
/usr/share/fonts/truetype/wqy/wqy-microhei.ttc
```

## 使用说明

发送"帮助"到企业微信机器人查看详细命令。
