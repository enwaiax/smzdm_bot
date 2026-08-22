# SMZDM Bot

[![Package](https://img.shields.io/github/actions/workflow/status/enwaiax/smzdm-bot/package.yml?label=Package)](https://github.com/enwaiax/smzdm-bot/actions/workflows/package.yml)
[![Build](https://img.shields.io/github/actions/workflow/status/enwaiax/smzdm-bot/build.yml?label=Build)](https://github.com/enwaiax/smzdm-bot/actions/workflows/build.yml)
[![License](https://img.shields.io/github/license/enwaiax/smzdm-bot)](LICENSE)
[![Docker Pulls](https://img.shields.io/docker/pulls/enwaiax/smzdm_bot)](https://hub.docker.com/r/enwaiax/smzdm_bot)

基于 Python 3.12、Typer、Rich、httpx 和 Pydantic 构建的什么值得买自动化客户端。

项目采用标准 `src` layout，可作为 Python package 安装，也可以通过 CLI、scheduler 或青龙面板运行。

## 功能

- Android APP 请求签名
- 根据 `smzdm_id + device_id` 动态生成 SK
- 每日签到及签到奖励
- 连续签到额外奖励
- VIP 信息
- 当前 APP 任务抽奖和免费幸运屋
- 每日文章浏览、关注和阶段奖励任务
- 可识别并明确跳过不安全或未经验证的写入任务
- 可选全民众测任务
- 多账号
- Bark、PushPlus、ServerChan、企业微信和 Telegram 通知
- Typer CLI 和 Rich 输出
- APScheduler 定时执行
- 顶层任务和可执行子任务均使用随机前置延时

签名和 SK 算法已通过 SMZDM Android 11.1.90 APK 静态验证。验证过程见
[`docs/apk-crypto-research-guide.md`](docs/apk-crypto-research-guide.md)。
当前版本的接口、签名范围、响应结构和废弃记录见
[`docs/smzdm-api-reference.md`](docs/smzdm-api-reference.md)。

## Package 结构

```text
src/smzdm_bot/
├── config/
│   ├── models.py       # 运行时配置模型
│   └── settings.py     # 环境变量和 .env 加载
├── tasks/
│   ├── checkin.py      # 签到、VIP 和奖励
│   ├── lottery.py      # 任务抽奖和幸运屋
│   ├── daily.py        # 每日活动任务
│   ├── testing.py      # 全民众测活动
│   ├── execution.py    # 通用执行策略
│   └── runner.py       # 单账号任务编排
├── client.py           # HTTP 请求
├── protocol.py         # APP profile、签名和 SK
├── main.py             # 多账号及通知编排
└── cli.py              # Typer/Rich CLI
```

依赖方向保持从配置和协议层指向客户端、任务编排和 CLI，避免业务模块反向依赖入口层。

## 安装

推荐使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync --locked
```

查看 CLI：

```bash
uv run smzdm-bot --help
```

也可以构建 wheel 后作为独立 CLI 工具安装：

```bash
uv build --no-sources
uv tool install dist/smzdm_bot-*.whl
```

## 配置

项目从当前工作目录的 `.env` 或系统环境变量读取配置。所有变量使用 `SMZDM_` 前缀。

### 单账号

```env
SMZDM_COOKIE="your_cookie"
SMZDM_SK=""
```

`SMZDM_SK` 可选。未配置时，Cookie 必须包含：

- `sess`
- `smzdm_id`
- `device_id`

### 多账号

```env
SMZDM_USERS='[
  {"account_label": "account-1", "cookie": "cookie-1"},
  {
    "account_label": "account-2",
    "cookie": "cookie-2",
    "security_key": "optional-sk"
  }
]'
```

设置 `SMZDM_USERS` 后优先使用多账号配置。
运行汇总和通知优先显示各 Cookie 中的 `smzdm_id`；仅在该字段缺失时使用
`account_label` 作为回退标识。

### 通知

```env
SMZDM_BARK_PUSH=""
SMZDM_PUSH_PLUS_TOKEN=""
SMZDM_SC_KEY=""
SMZDM_WECOM_WEBHOOK=""
SMZDM_TG_BOT_TOKEN=""
SMZDM_TG_USER_ID=""
SMZDM_TG_API_BASE=""
```

`SMZDM_BARK_PUSH` 使用完整 Bark 推送地址，例如
`https://api.day.app/your-device-key`。配置非空时自动启用 Bark。

### 可选任务策略

```env
SMZDM_ENABLE_FOLLOW_TASKS=true
SMZDM_ENABLE_TESTING_TASKS=false
SMZDM_ENABLE_ACTIVITY_REWARD_CLAIMS=true
```

- 评论和内容发布任务不自动执行，也没有启用开关。
- 当前 API 不提供可靠的点赞、收藏账号状态，APP 使用本地数据库保存，因此两类任务固定跳过。
- 用户、栏目和品牌关注会读取当前状态，并在任务后恢复。
- 分享流程未经当前版本验证且无法撤销，因此固定跳过。
- 付费幸运屋目标映射未经验证，因此不自动参与；免费选项仍会正常处理。
- 站外浏览、打开第三方 APP 和下载 APP 需要真实设备行为，因此固定跳过。
- 创建签到小组件和开启推送需要真实 Android 系统状态，因此固定跳过。
- 全民众测默认关闭；开启后会动态读取当前活动 ID，并使用独立领奖接口。
- 众测申请涉及报名和资格选择，不自动执行。
- 旧版接口和任务数据结构不匹配时，任务会报告跳过或失败，不会尝试内容发布。

### Scheduler

```env
SMZDM_SCH_HOUR=9
SMZDM_SCH_MINUTE=30
SMZDM_TIMEZONE="Asia/Shanghai"
```

未设置时间时，每次启动会在 06:00 至 10:59 之间选择一个执行时间。

## CLI

执行一次：

```bash
uv run smzdm-bot run
```

启动 scheduler：

```bash
uv run smzdm-bot schedule
```

检查配置；显示 `smzdm_id` 以区分账号，但不显示 Cookie 或 SK：

```bash
uv run smzdm-bot config
```

查看版本：

```bash
uv run smzdm-bot version
uv run python -m smzdm_bot --version
```

启用 debug 日志：

```bash
uv run smzdm-bot run --debug
```

写入日志文件：

```bash
uv run smzdm-bot run --log-file ./smzdm.log
```

默认不创建日志文件。

## Python API

执行所有已配置账号：

```python
from smzdm_bot.main import run_all_accounts

account_results = run_all_accounts()
```

调用只读 API：

```python
from smzdm_bot import SmzdmClient, UserConfig

user_config = UserConfig(cookie="...")
with SmzdmClient(user_config) as smzdm_client:
    vip_response = smzdm_client.post("/vip")
```

## 青龙面板

拉取仓库：

```text
ql repo https://github.com/enwaiax/smzdm-bot.git "smzdm_ql.py"
```

青龙入口会安装当前 checkout，并执行：

```bash
python -m smzdm_bot run
```

它不会在每次运行时升级 pip。

## 开发

安装开发依赖：

```bash
uv sync --locked --dev
```

运行检查：

```bash
uv run ruff check src tests tools
uv run ruff format --check src tests tools
uv run pytest
uv build --no-sources
uv run --isolated --no-project --with dist/*.whl smzdm-bot --version
uv run --isolated --no-project --with dist/*.tar.gz smzdm-bot --version
```

APK Key 静态检查工具使用独立的 PEP 723 依赖，不进入生产 package：

```bash
uv run tools/extract_smzdm_apk_keys.py /path/to/smzdm.apk
```

## 安全说明

- 不要提交 `.env`、Cookie、session、token、用户 ID 或设备标识。
- 默认只应使用自己的账号和合法取得的数据。
- 遇到验证码、`403`、`429` 或风控提示时停止请求，不进行绕过。
- 互动类自动任务可能违反平台规则并带来账号风险。
- 项目不会自动点赞、收藏、分享、发布内容或参与付费幸运屋。
- APK 分析、Key 提取和线上 API 请求应保持为相互独立、可审计的步骤。

## License

Apache-2.0
