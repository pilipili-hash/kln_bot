# NcatBot 优化版

一个功能丰富的 QQ 机器人项目，基于 NcatBot 框架开发，支持多种插件功能。

## ✨ 特性

- 🤖 基于 NcatBot 框架，支持 OneBotV11 协议
- 🔌 丰富的插件系统，包含 40+ 实用插件
- 🎨 图片处理、搜索、娱乐等多种功能
- 📊 性能监控和错误处理机制
- 🛠️ 完善的配置管理系统
- 🔧 跨平台支持 (Windows/Linux/macOS)

## 🚀 快速开始

### 方法一：一键启动（推荐）

**Windows 用户：**
```bash
# 完整安装（首次使用）
install.bat

# 快速启动（已配置环境）
run.bat
```

**Linux/macOS 用户：**
```bash
# 给脚本执行权限
chmod +x start_bot.sh run.sh

# 完整安装（首次使用）
./start_bot.sh

# 快速启动（已配置环境）
./run.sh
```

### 方法二：手动安装

1. **安装 Python 3.10+**
   ```bash
   python --version  # 确认版本 >= 3.10
   ```

2. **安装依赖**
   ```bash
   # 使用 pip
   pip install -r requirements.txt
   ```
   
3. **配置机器人**
   ```bash
   # 复制配置模板
   cp config.example.yaml config.yaml
   
   # 编辑配置文件
   nano config.yaml  # 或使用其他编辑器
   ```

4. **启动机器人**
   ```bash
   python main.py
   ```

## ⚙️ 配置说明

### 基本配置

编辑 `config.yaml` 文件：

```yaml
# 机器人基本信息
bot:
  uin: "123456789"  # 机器人QQ号
  ws_uri: "ws://localhost:3001"  # OneBot WebSocket地址
  root_user: "987654321"  # 管理员QQ号

# 管理员列表
master:
  - 987654321

# API 密钥（可选）
gemini_apikey: "your_api_key"
saucenao_api_key: "your_api_key"
pixiv_refresh_token: "your_token"
```

### OneBot 客户端配置

需要配置支持 OneBotV11 协议的客户端，如：
- [go-cqhttp](https://github.com/Mrs4s/go-cqhttp)
- [Lagrange](https://github.com/LagrangeDev/Lagrange.Core)
- [NapCat](https://github.com/NapNeko/NapCatQQ)

## 🔌 插件功能

### 🎨 图片相关
- **Pixiv 搜索** - 搜索和获取 Pixiv 作品
- **图片搜索** - 以图搜图功能
- **壁纸获取** - 随机壁纸推送
- **表情包制作** - 自定义表情包生成
- **AI 绘画** - AI 图片生成

### 🎮 娱乐功能
- **每日老婆** - 随机角色卡片
- **今日运势** - 运势查询
- **手办抽取** - 虚拟手办收集
- **CSGO 开箱** - 模拟开箱游戏
- **疯狂星期四** - KFC 文案生成

### � 信息查询
- **番剧搜索** - 动漫信息查询
- **今日番剧** - 番剧更新提醒
- **生日提醒** - 角色生日查询
- **热搜查询** - 各平台热搜榜
- **游戏搜索** - Steam 游戏信息

### 🛠️ 实用工具
- **群管功能** - 群组管理工具
- **签到系统** - 用户签到积分
- **数据库管理** - 数据统计查询
- **帮助系统** - 功能说明文档

## 📁 项目结构

```
NcatBot/
├── main.py              # 主程序入口
├── handlers.py          # 事件处理器
├── config.example.yaml  # 配置文件模板
├── requirements.txt     # Python 依赖
├── pyproject.toml      # Poetry 配置
├── start_bot.bat       # Windows 启动脚本
├── start_bot.sh        # Linux/Mac 启动脚本
├── run.bat             # Windows 快速启动
├── run.sh              # Linux/Mac 快速启动
├── plugins/            # 插件目录
├── utils/              # 工具模块
├── static/             # 静态资源
└── data/               # 数据存储（自动创建）
```

## 🔧 开发指南

### 添加新插件

1. 在 `plugins/` 目录创建插件文件夹
2. 继承基础插件类
3. 实现必要的方法和事件处理
4. 在配置中启用插件

### 代码规范

- 使用 Python 3.10+ 特性
- 遵循 PEP 8 代码规范
- 添加类型注解
- 编写文档字符串

## 🐛 故障排除

### 常见问题

1. **依赖安装失败**
   ```bash
   # 升级 pip
   python -m pip install --upgrade pip
   
   # 使用国内镜像
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
   ```

2. **WebSocket 连接失败**
   - 检查 OneBot 客户端是否正常运行
   - 确认 WebSocket 地址和端口正确
   - 检查防火墙设置

3. **插件功能异常**
   - 查看 `logs/` 目录下的日志文件
   - 检查相关 API 密钥配置
   - 确认网络连接正常

### 日志查看

```bash
# 查看最新日志
tail -f logs/bot.log

# 查看错误日志
grep "ERROR" logs/bot.log
```

## 📄 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建功能分支
3. 提交更改
4. 发起 Pull Request

## � 支持

如果遇到问题或有建议，请：
- 提交 [Issue](../../issues)
- 查看 [Wiki](../../wiki) 文档
- 加入交流群组

---

⭐ 如果这个项目对你有帮助，请给个 Star！
