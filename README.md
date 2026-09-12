# SMZDM Bot

[![Package](https://img.shields.io/github/actions/workflow/status/enwaiax/smzdm-bot/package.yml?label=Package)](https://github.com/enwaiax/smzdm-bot/actions/workflows/package.yml)
[![Build](https://img.shields.io/github/actions/workflow/status/enwaiax/smzdm-bot/build.yml?label=Build)](https://github.com/enwaiax/smzdm-bot/actions/workflows/build.yml)
[![License](https://img.shields.io/github/license/enwaiax/smzdm-bot)](LICENSE)
[![Docker Pulls](https://img.shields.io/docker/pulls/enwaiax/smzdm_bot)](https://hub.docker.com/r/enwaiax/smzdm_bot)

基于 Python 3.12、Typer、Rich、httpx 和 Pydantic 构建的什么值得买自动化客户端。

项目采用标准 `src` layout，可作为 Python package 安装，也可以通过 CLI、scheduler 或青龙面板运行。

## 功能

- Android 11.1.90 和 iPhone 11.1.92 APP 请求签名
- 根据 `smzdm_id + device_id` 动态生成 SK
- 每日签到及签到奖励
- 连续签到额外奖励
- VIP 信息
- 当前 APP 任务抽奖和免费幸运屋
- 每日文章浏览、关注和阶段奖励任务
- 可识别并明确跳过不安全或未经验证的写入任务
- 可选全民众测任务
- 多账号
- Bark（多设备）、飞书、钉钉、PushPlus、ServerChan、企业微信和 Telegram 串行通知
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

也可以从 APP 抓包导出的 HAR 文件中导入登录 Cookie。脚本只读取什么值得买域名的
请求，并且不会在终端输出 Cookie 内容：

```bash
python tools/import_smzdm_har.py /path/to/smzdm.har
```

脚本默认更新当前目录的 `.env`、将权限设为 `0600`，并在文件已存在时生成带时间戳的
备份。使用 `--dry-run` 可以只验证、不写入文件；如果 HAR 包含多个账号，可以使用
`--user-id` 选择账号。导入时 `SMZDM_SK` 默认清空，由程序根据 Cookie 中的
`smzdm_id + device_id` 动态生成；iPhone 请求不需要 SK。

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

`SMZDM_BARK_PUSH` 支持单 Key、完整推送地址及逗号分隔的多目标。
完整开关、发送顺序和飞书/钉钉配置见下方 [Notification](#notification)。

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

## Notification

### Notification Channels

支持 Bark、Feishu（飞书）、DingTalk（钉钉）、Telegram、WeCom（企业微信）、
PushPlus、ServerChan。配置继续从当前工作目录的 `.env` 加载，系统环境变量优先。
下面是完整通知配置示例，也可参考 `.env.example`：

```env
# ==================================================
# Notification
# ==================================================
SMZDM_NOTIFY_ENABLED=true
SMZDM_NOTIFY_CHANNELS=bark,feishu,dingtalk,telegram,wecom,pushplus,serverchan
SMZDM_NOTIFY_TIMEOUT=10
SMZDM_NOTIFY_ON_SUCCESS=true
SMZDM_NOTIFY_ON_FAILURE=true

# Omitted channel switches auto-enable when credentials are present.
# Uncomment true/false to override. Do not use an empty boolean value.

# Bark: comma-separated keys or full URLs (including self-hosted endpoints).
# Example: key1,key2,key3
# SMZDM_NOTIFY_BARK_ENABLED=true
SMZDM_BARK_PUSH=""

# Feishu
# SMZDM_NOTIFY_FEISHU_ENABLED=false
SMZDM_FEISHU_WEBHOOK=""
SMZDM_FEISHU_SECRET=""

# DingTalk
# SMZDM_NOTIFY_DINGTALK_ENABLED=false
SMZDM_DINGTALK_WEBHOOK=""
SMZDM_DINGTALK_SECRET=""

# Telegram (custom API base remains supported)
# SMZDM_NOTIFY_TELEGRAM_ENABLED=false
SMZDM_TG_BOT_TOKEN=""
SMZDM_TG_USER_ID=""
SMZDM_TG_API_BASE=""

# WeCom
# SMZDM_NOTIFY_WECOM_ENABLED=false
SMZDM_WECOM_WEBHOOK=""

# PushPlus
# SMZDM_NOTIFY_PUSHPLUS_ENABLED=false
SMZDM_PUSH_PLUS_TOKEN=""

# ServerChan
# SMZDM_NOTIFY_SERVERCHAN_ENABLED=false
SMZDM_SC_KEY=""
```

### Multiple Notification Channels

可以同时启用多个 Channel：

```env
SMZDM_NOTIFY_ENABLED=true
SMZDM_NOTIFY_CHANNELS=bark,feishu,dingtalk
SMZDM_NOTIFY_BARK_ENABLED=true
SMZDM_NOTIFY_FEISHU_ENABLED=true
SMZDM_NOTIFY_DINGTALK_ENABLED=true
```

填入对应凭据后，按照 Bark → 飞书 → 钉钉顺序串行发送。
任一 Channel 失败不会阻止后续通知，也不会改变签到结果或进程退出码。
多账号仍汇总为一条统一的 title/content，然后交给每个 Channel。

### Bark Multiple Devices

```env
SMZDM_BARK_PUSH=key1,key2,key3
```

使用英文逗号分隔，逐项去掉首尾空格并过滤空值：
`aaa, bbb,,ccc,` 得到三个目标。按出现顺序逐个发送，不并发。
裸 Key 自动使用 `https://api.day.app/<key>`；单 Key、旧版完整 URL、
自建 Bark 地址和 Key/URL 混用都支持，例如：

```env
SMZDM_BARK_PUSH=key1,https://bark.example.com/key2
```

一个目标失败会继续剩余目标及后续 Channel。日志只显示目标序号：
`Bark notification 2/3 failed: request timeout`。
Channel 汇总支持 `partial success (2/3)`，全部设备成功才计为一个成功 Channel。

### Feishu

```env
SMZDM_NOTIFY_FEISHU_ENABLED=true
SMZDM_FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
SMZDM_FEISHU_SECRET=
```

使用自定义机器人 text 消息，内容为“标题 + 换行 + 正文”。
启用签名校验时填入 Secret；使用秒级时间戳，
以 `timestamp + "\n" + secret` 为 HMAC-SHA256 Key，对空消息签名后 Base64 编码，
将 `timestamp/sign` 放入 JSON。
检查业务 `code` 或旧版 `StatusCode`，必须为 0；缺少状态字段也按失败处理。
参见[飞书自定义机器人文档](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)。

### DingTalk

```env
SMZDM_NOTIFY_DINGTALK_ENABLED=true
SMZDM_DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
SMZDM_DINGTALK_SECRET=
```

使用自定义机器人 text 消息。Secret 留空直接发送；配置后使用毫秒级时间戳，
以 Secret 为 HMAC-SHA256 Key，对 `timestamp + "\n" + secret` 签名，
Base64 编码后通过 URL 查询参数编码加入 `timestamp/sign`，保留原 access_token。
只有响应 `errcode=0` 才认为成功。
参见[钉钉自定义机器人文档](https://open.dingtalk.com/document/robots/custom-robot-access)。

### Notification Order

`SMZDM_NOTIFY_CHANNELS` 指定参与调度的 Channel 及顺序。
未配置或为空时，默认顺序为：

```text
bark,feishu,dingtalk,telegram,wecom,pushplus,serverchan
```

名称不区分大小写，忽略空项、去重并保留首次出现的位置。
未列入的 Channel 不发送；未知名称输出 warning 后跳过，继续后续 Channel。
显式启用但缺少凭据的 Channel 会报告 `missing credentials`。

### Notification Switches

总开关 `SMZDM_NOTIFY_ENABLED=false` 时不执行任何通知。
每个 `SMZDM_NOTIFY_<CHANNEL>_ENABLED` 是独立开关：

- 显式配置 true/false：以开关为准。
- 未配置（示例中注释掉）：按对应凭据是否完整自动启用，兼容旧配置。
- 不要将布尔开关写为空值；请删除该行、注释掉或填写 true/false。

旧变量名称及别名保持有效，包括 `SMZDM_BARK_URL`、
`SMZDM_TG_BOT_TOKEN`、`SMZDM_TG_USER_ID`、`SMZDM_TG_API_BASE`、
`SMZDM_WECOM_WEBHOOK`、`SMZDM_PUSH_PLUS_TOKEN`、`SMZDM_SC_KEY`。
旧 `.env` 无需修改即可继续通知。

`SMZDM_NOTIFY_ON_SUCCESS` 和 `SMZDM_NOTIFY_ON_FAILURE` 默认都为 true：

| SUCCESS | FAILURE | 通知策略 |
| --- | --- | --- |
| true | true | 所有运行结果 |
| false | true | 仅失败 |
| true | false | 仅成功 |
| false | false | 不发送 |

整次运行所有账号成功才算成功；任一账号失败算失败，通知依然包含所有账号。
沿用现有 `AccountTaskResult.success` 判定，不改变可选任务的成功/失败语义。

`SMZDM_NOTIFY_TIMEOUT` 默认 10 秒，必须是有限正数，应用于每次请求的
connect/read/write/pool 超时。它不是整批通知的总时限。无自动重试。
HTTP 非 2xx、JSON 解析失败、业务错误和网络异常分别处理；
日志不输出请求 URL、消息正文、原始异常或服务端错误消息。
`python -m smzdm_bot config` 显示经过总开关、顺序列表和独立开关筛选后的启用状态。

实现位于 `notifications/`：公共 HTTP/结果模型、Channel 实现、独立签名函数和
`NotificationManager`。新增 Channel 只需实现接口并注册到注册表，业务入口无需调整。
旧 `notify.py` 的函数签名和 bool/int 返回类型继续保留。

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
