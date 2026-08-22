# SMZDM API 开发参考

> 本项目的非官方、特定版本开发说明。
>
> 本文档并非官方 SMZDM API 规范。内部接口可能随时变更，恕不另行通知。请仅使用您有权访问的
> 账号和数据；遇到 CAPTCHA、HTTP 403、HTTP 429 或明确的风控响应时，应立即停止。

## 1. 参考快照

- 研究日期：2026-08-22
- Android APP 版本：`11.1.90`
- Android 版本代码：`1190`
- APK SHA-256：
  `59ed9d2774d888096200a6399217aa3a2653d543a81d7976ff194c10dce19a5b`
- 包实现：`src/smzdm_bot`
- 历史对照：
  - `smzdm_script` (`10.4.26`)
  - `SMZDM_checkin.py` (`10.4.1`)
  - `dailycheckin/dailycheckin/smzdm` (`10.4.1`)

加密常量及其 APK 提取流程单独维护于：

- `src/smzdm_bot/protocol.py`
- `docs/apk-crypto-research-guide.md`
- `tools/extract_smzdm_apk_keys.py`

本文档有意不重复记录账号凭据、捕获的请求、Cookie 值、会话 token、安全密钥、用户标识符或
设备标识符。

## 2. 证据等级

每个接口均应按以下证据等级评估：

- **A — APK + 实时只读**：已在 Android `11.1.90` 中确认，并通过不会产生数据变更的实时响应验证。
- **B — APK 静态分析**：已在 Android `11.1.90` 中确认，但验证期间未调用写操作。
- **C — 实时只读**：已验证当前响应，但尚未重建完整的 Android 调用链。
- **D — 历史实现**：信息来自较早的开源实现，不应假定当前仍然有效。
- **E — 授权实时写入**：使用当前账号的真实任务目标执行，并确认任务状态或奖励状态发生预期变化。

不会为了证明接口存在而构造随机写入目标。只有在用户明确授权、当前账号存在真实任务且
不需要绕过风控时才进行 E 级验证；其余写接口的当前可信度通常为 B 级。

### 2.1 授权实时验证快照

2026-08-22 使用当前账号的真实任务完成了以下验证：

- 每日签到、VIP 信息和签到奖励读取成功。
- `/task/lottery` 成功执行一次当前任务抽奖。
- “关注 3 位达人”任务完成，奖励成功领取。
- 全民众测“浏览文章”任务从状态 `2` 变为 `4`，奖励成功领取。

验证期间没有可领取的额外签到奖励、活动阶段奖励或免费幸运屋选项，也没有
`guide.crowd` 任务，因此未调用相应写接口，未消耗碎银。点赞、收藏、内容发布和
众测申请仍按项目策略跳过。

## 3. 传输与签名规则

### 3.1 APP 签名请求

常用签名字段如下：

```text
weixin=1
basic_v=0
f=android
v=11.1.90
time=<milliseconds>
sign=<uppercase MD5 signature>
```

`sign` 根据排序后的非空请求字段和对应版本的 `SIGN_KEY` 计算。参见
`src/smzdm_bot/protocol.py` 中的 `compute_request_signature()`。

### 3.2 会话字段因服务而异

不要全局添加 `token` 和 `sk`。

| 服务 | `token` / `sk` 行为 | 当前证据 |
| --- | --- | --- |
| `user-api.smzdm.com` | 对已测试的只读接口，无论是否携带会话字段均可接受 | A |
| `article-api.smzdm.com` | 必须省略会话字段；添加后会产生 HTTP 500 | C |
| `dingyue-api.smzdm.com` | 必须省略会话字段；添加后会产生 HTTP 500 | A/C |
| `brand-api.smzdm.com` | 必须省略会话字段；添加后会产生 HTTP 500 | A |
| `zhiyou*.smzdm.com` Web API | 不签名的 Web Cookie 请求 | A/C |
| `test.m.smzdm.com` | 不签名的 Web Cookie 请求 | A |

省略 `token` 和 `sk` 表单字段时，Cookie 请求头仍会保留。某个接口不携带这些表单字段也能工作，
并不意味着它支持匿名访问。

### 3.3 响应惯例

- APP API 通常以字符串形式返回 `error_code`。
- 众测 Web API 通常以整数形式返回 `error_code`。
- 部分推荐 API 在顶层返回 `rows`。
- 当前的用户关注推荐 API 返回 `data.rows`。
- JSONP 抽奖接口不使用标准 APP 响应封装。
- HTTP 200 不代表业务操作成功；务必检查 API 状态。

## 4. 基础服务

```text
USER_API          = https://user-api.smzdm.com
ARTICLE_API       = https://article-api.smzdm.com
SUBSCRIPTION_API  = https://dingyue-api.smzdm.com
BRAND_API         = https://brand-api.smzdm.com
WEB               = https://zhiyou.smzdm.com
CROWD_MOBILE      = https://zhiyou.m.smzdm.com
TESTING_TASK      = https://zhiyou.m.smzdm.com/task/task
TESTING_CENTER    = https://test.m.smzdm.com
```

## 5. 每日任务 API

### 5.1 任务列表

```text
POST https://user-api.smzdm.com/task/list_v2
```

- 签名：APP 签名
- 会话字段：目前两种模式均可接受
- 数据变更：无
- 证据：A
- 当前响应路径：

```text
data.rows[]
  .cell_data
  .activity_task
  .default_list_v2[]
  .task_list[]
```

历史兼容路径：

```text
activity_task.accumulate_list[]
activity_task.accumulate_list.task_list_v2[]
```

当前观察结果：

- `default_list_v2` 已填充数据。
- `accumulate_list` 存在但为空。
- 保留历史解析器成本较低，且不会触发额外请求。

重要任务字段：

```text
task_id
task_name
task_status
task_event_type
task_redirect_url
task_even_num
task_finished_num
view_seconds
article_id
channel_id
```

已知状态值：

```text
2 = 未完成
3 = 可领取奖励
4 = 已完成或无需操作
```

### 5.2 机器人 token

```text
POST https://user-api.smzdm.com/robot/token
```

- 签名：APP 签名
- 会话字段：目前两种模式均可接受
- 数据变更：仅创建临时 token
- 证据：E，已在真实达人关注任务领奖前成功创建 token
- 响应：

```text
data.token
```

返回的 token 并非 Cookie 中的 `sess` 值。

### 5.3 领取单个任务奖励

```text
POST https://user-api.smzdm.com/task/activity_task_receive
```

- 签名：APP 签名
- 数据变更：领取已获得的奖励
- 证据：E
- 请求：

```text
robot_token
task_id
geetest_seccode
geetest_validate
geetest_challenge
captcha
```

在正常的无验证流程中，Geetest 和 CAPTCHA 字段以空值发送。遇到验证时，客户端必须停止，
不得绕过验证。

### 5.4 领取活动阶段奖励

```text
POST https://user-api.smzdm.com/task/activity_receive
```

- 签名：APP 签名
- 数据变更：领取已获得的阶段奖励
- 证据：B，当前验证时没有可领取的阶段奖励，未调用写接口
- 请求：

```text
activity_id
```

是否可领取通过以下字段判断：

```text
cell_data.activity_reward_status == 1
```

### 5.5 上报文章浏览

```text
POST https://user-api.smzdm.com/task/event_view_article_sync
```

- 签名：APP 签名
- 数据变更：记录任务浏览事件
- 证据：E，已通过全民众测的真实浏览任务验证
- 请求：

```text
article_id
channel_id
task_id
```

### 5.6 上报站外浏览

```text
POST https://user-api.smzdm.com/task/event_view_zhanwai
```

- 签名：APP 签名
- 数据变更：记录站外浏览任务事件
- 证据：B
- 请求：

```text
task_id
```

Android `11.1.90` 在打开 `task_redirect_url` 前直接调用该接口。原生流程会
异步上报任务 ID 并立即打开站外页面。仅调用上报接口而不执行真实跳转会伪造
完整行为，因此项目记录该接口但固定跳过自动执行。

## 6. 任务事件与项目策略

### 6.1 当前每日任务列表中观察到的事件

```text
interactive.follow.user
interactive.view.article
publish.baoliao_new
publish.biji_new
publish.yuanchuang_new
```

### 6.2 当前众测活动中观察到的事件

```text
interactive.rating
interactive.favorite
interactive.view.article
guide.apply_zhongce
```

众测 Web API 会返回 `interactive.rating` 和 `interactive.favorite`，但
Android `11.1.90` 原生任务分发器没有这两个专用事件分支，只会通过
`task_redirect_url` 打开目标页面。

### 6.3 APK 原生事件完整目录

```text
interactive.view.article
interactive.view.zhanwai
interactive.share
interactive.open_third_party_app
interactive.follow.user
interactive.download_zhangdama
guide.create_app_checkin_shortcut
guide.open_app_push
```

这是对 Android `11.1.90` 中所有读取 `task_event_type` 的原生分发方法进行静态
扫描后得到的完整常量集合，主要分发点为 `classes12.dex` 中的 `k.M0()` 和
`E3.L0()`，旧路径位于 `classes7.dex`。

项目支持 `interactive.view.article` 和 `interactive.follow.user`。其余事件
需要不可安全恢复的写入或真实 Android 设备行为，因此明确跳过。

`interactive.open_third_party_app` 不会在点击时立即上报完成。APP 会先记录
`task_id`，等待 Android 路由成功进入 `startActivity` 或 deep-link 分支并通过
EventBus 发布 `jumpType="APP"` 且 ID 匹配的事件，之后才调用：

```text
POST https://user-api.smzdm.com/task/event_view_third_party_app
task_id=<matched route task ID>
```

该事件只证明目标 APP 被成功拉起，不证明合作方业务已完成。服务端脚本没有真实
Android 路由事件，直接调用该接口会伪造设备行为，因此固定跳过。

`interactive.download_zhangdama` 将动态 `task_redirect_url.link` 交给浏览器或
应用市场。当前分发分支不直接下载、不验证安装，也没有硬编码任务完成请求。

`guide.create_app_checkin_shortcut` 先创建签到桌面小组件并保存 `task_id`；只有用户
从该小组件进入签到页后，APP 才调用 `/task/create_app_checkin_shortcut`。
`guide.open_app_push` 会保存任务 ID 并打开 Android 推送设置。两者都依赖真实
Android 系统状态，项目固定跳过。

### 6.4 执行策略

| 事件 | 项目策略 |
| --- | --- |
| `interactive.view.article` | 有明确目标时支持 |
| `interactive.follow.user` | 仅在具备当前推荐 API 和操作 API 时支持 |
| 无事件且 `link_type=lanmu` | 兼容栏目任务；仅在能够读取原始状态时支持 |
| 无事件且 `link_type=brand` | 兼容品牌任务；仅在能够读取原始状态时支持 |
| `interactive.rating` | 固定跳过；远程 API 无法读取账号原始状态 |
| `interactive.favorite` | 固定跳过；远程 API 无法读取账号原始状态 |
| `interactive.share` | 固定跳过；当前流程未经验证且无法撤销 |
| `interactive.view.zhanwai` | 固定跳过；原生流程还要求真实打开站外页面 |
| `interactive.open_third_party_app` | 固定跳过；需要真实 Android 设备行为 |
| `interactive.download_zhangdama` | 固定跳过；需要真实 Android 设备行为 |
| `guide.create_app_checkin_shortcut` | 固定跳过；需要创建并点击 Android 桌面小组件 |
| `guide.open_app_push` | 固定跳过；需要修改 Android 推送设置 |
| `interactive.comment` | 未实现 |
| `publish.*` | 未实现 |
| `guide.apply_zhongce` | 未实现 |
| `guide.crowd` | 固定跳过；任务目标与幸运屋选项的映射未经验证 |

内容发布、评论和众测申请被有意排除在自动化范围之外。

## 7. 文章 API

### 7.1 文章详情

```text
GET https://article-api.smzdm.com/article_detail/{article_id}
```

- 签名：APP 签名
- 会话字段：必须省略
- 数据变更：无
- 证据：C/D
- 已知查询字段：

```text
comment_flow
hashcode
lastest_update_time
uhome
imgmode
article_channel_id
h5hash
```

当前行为因样本而异：

- 探索期间，一个有效的任务关联文章成功返回了元数据。
- 另一个公开样本返回 API 状态码 `104`，且 `data=null`。
- 添加 `token` 和 `sk` 会导致 HTTP 500。
- 当前观察到的详情响应未提供可靠的用户级点赞/收藏状态字段。

在检查当前响应前，不要假定 `is_like`、`is_worth` 或 `is_favorite` 存在。

Android `11.1.90` 主要从按用户隔离的本地 DAO 读取互动状态：

```text
DetailPraiseBean.praised
DetailCollectBean.collect
```

这些本地状态不属于远程 API 响应，Python package 无法访问。详情响应中的
`favorite_count`、`collection_count`、`article_rating` 等字段是总数，不是
当前账号状态。

### 7.2 已弃用的随机文章回退方案

```text
GET https://article-api.smzdm.com/ranking_list/articles
```

- 签名：APP 签名
- 会话字段：必须省略
- 数据变更：无
- 当前结果：API 状态码 `0`，但 `data.rows` 为空
- 历史用途：为互动任务选择任意内容
- 项目状态：**已从任务执行中移除**

移除原因：

- 当前查询未返回候选项。
- 随机选择内容会扩大账号互动范围。
- 当前任务通常包含明确的 `article_id` 或跳转目标。
- 缺少目标时应跳过，而不是猜测。

该接口本身可能仍用于排行榜 UI 功能；仅弃用其作为任务回退方案的用途。

## 8. 评价、收藏与分享 API

这些都是写入接口，在只读验证期间未被调用。

### 8.1 评价

```text
POST https://user-api.smzdm.com/rating/like_create
POST https://user-api.smzdm.com/rating/like_cancel
POST https://user-api.smzdm.com/rating/worth_create
POST https://user-api.smzdm.com/rating/worth_cancel
```

请求：

```text
id
channel_id
wtype
```

`wtype` 用于值/不值流程：

```text
1 = create
3 = cancel
```

证据：B。

Android APP 使用本地 `DetailPraiseBean` 状态决定调用 create 还是 cancel，
没有独立的 `rating/status` API。动作响应中的 `like_num` 是更新后的总数，
不是当前账号状态查询结果。

### 8.2 收藏

```text
POST https://user-api.smzdm.com/favorites/create
POST https://user-api.smzdm.com/favorites/destroy
```

请求：

```text
id
channel_id
```

证据：B。

Android APP 使用本地 `DetailCollectBean.collect` 决定调用 create 还是
destroy，没有独立的 `favorites/status` API。

任务中心本身只跳转文章页面，不会自动执行 create → delay → cancel，也不会
自动恢复原状态。项目无法可靠读取 APP 本地 DAO，因此点赞和收藏固定跳过，
不提供绕过该限制的配置开关。

### 8.3 分享

```text
POST https://user-api.smzdm.com/share/complete_share_rule
POST https://user-api.smzdm.com/share/daily_reward
POST https://user-api.smzdm.com/share/callback
```

请求使用以下字段的组合：

```text
article_id
channel_id
tag_name=gerenzhongxin
```

证据：D。

分享完成后无法回滚，且这些历史接口尚未在当前版本的真实分享任务中验证。
项目固定跳过分享事件，不提供自动执行开关。

## 9. 关注 API

### 9.1 当前用户推荐

```text
POST https://dingyue-api.smzdm.com/dy/user/dingyue/tuijian_search
```

- 签名：APP 签名
- 会话字段：必须省略
- 数据变更：无
- 证据：A
- 业务请求：

```text
type=user
```

响应：

```text
data.rows[]
```

实用的条目字段：

```text
type
keyword
keyword_id
is_follow
follow_num
redirect_data
```

Android `11.1.90` 调用链：

```text
interactive.follow.user
  -> sub_type=search_user
  -> path_custom_follow_result_activity
  -> intent_param_type=user
  -> POST /dy/user/dingyue/tuijian_search
```

### 9.2 旧版推荐

```text
GET/POST https://dingyue-api.smzdm.com/tuijian/search_result
```

- 签名：APP 签名
- 会话字段：必须省略
- 数据变更：无
- 证据：A/B
- 可能的字段：

```text
nav_id
type
time_code
limit
page
is_from
```

项目状态：

- **已从用户关注任务流程中移除。**
- 在 Android `11.1.90` 的其他推荐分支中仍然存在。
- 不要将该接口全局标记为过时。

### 9.3 用户、标签与品牌关注操作

当前原生推荐列表统一使用：

```text
POST https://dingyue-api.smzdm.com/dingyue/create
POST https://dingyue-api.smzdm.com/dingyue/destroy
```

用户请求字段：

```text
keyword=<user_id>
refer=<screen name>
type=user
is_from_task=0
touchstone_event=<dynamic JSON or empty string>
```

用户请求不发送 `keyword_id`。动作由 endpoint 的 `create` 或 `destroy`
表示。

标签和品牌请求字段：

```text
keyword_id=<tag or brand id>
keyword=<tag or brand name>
type=tag|brand
refer=<screen name>
touchstone_event=<dynamic JSON or empty string>
```

部分页面可能附加 `keyword_hash`、`is_push`、`is_push_ai` 或
`interest_source`。

响应成功条件：

```text
error_code == 0
```

证据：E。已重建 Android `11.1.90` 的 `FollowButton` 调用链，并通过当前
“关注 3 位达人”任务验证 create、destroy 和原状态恢复流程。

### 9.4 关注状态

```text
POST https://dingyue-api.smzdm.com/dingyue/follow_status
```

- 签名：APP 签名
- 会话字段：必须省略
- 数据变更：无
- 证据：A/C
- 请求：

```text
rules=[{"type":"tag","keyword":"..."}]
```

响应包含：

```text
data.rules
data.users
data.wiki
data.article_attributes
```

### 9.5 品牌详情与 WebView 动作桥

```text
GET  https://brand-api.smzdm.com/brand/brand_basic
```

品牌详情：

- 会话字段：必须省略
- 请求：`brand_id`
- 当前响应包含 `follow_status`
- 证据：A

原生品牌推荐列表的关注动作使用 9.3 节中的通用
`/dingyue/create|destroy`。

APK 中还存在 WebView/品牌详情动作桥：

```text
POST https://dingyue-api.smzdm.com/dy/util/api/user_action
```

其外层字段由运行时 H5 提供：

```text
action
params
token
refer
touchstone_event
```

项目任务执行不再使用该 WebView 桥，因为 APK 没有静态证据证明 H5
当前仍使用历史的 `dingyue_lanmu_add|dingyue_lanmu_del` 参数。

## 10. 签到与账号 API

### 10.1 签到

```text
POST https://user-api.smzdm.com/checkin
```

- 签名：APP 签名
- 会话字段：当前项目流程要求提供
- 数据变更：记录每日签到
- 证据：E

包使用的响应字段：

```text
daily_num
cgold
cpoints
cexperience
rank
cards
```

### 10.2 VIP 信息

```text
POST https://user-api.smzdm.com/vip
```

- 数据变更：无
- 证据：C，当前账号实时读取成功

响应：

```text
data.vip.exp_level
data.vip.exp_current_level
data.vip.exp_level_expire
```

### 10.3 普通奖励与连续签到奖励

```text
POST https://user-api.smzdm.com/checkin/all_reward
POST https://user-api.smzdm.com/checkin/show_view_v2
POST https://user-api.smzdm.com/checkin/extra_reward
```

`extra_reward` 是写入接口，仅应在 `show_view_v2` 表明有可领取奖励后调用。
本次验证中 `all_reward` 和 `show_view_v2` 读取成功，但没有可领取的额外奖励，
因此未调用 `extra_reward`。

### 10.4 历史 HTML 账号资产

```text
GET https://zhiyou.smzdm.com/user/
GET https://zhiyou.m.smzdm.com/user/exp/ajax_log
```

历史脚本曾从这些页面解析昵称、金币、碎银、会员信息和每月经验。

项目状态：未实现。

原因：

- HTML 选择器稳定性较差。
- 经验值接口的独立证据有限。
- 执行任务不需要这些字段。

## 11. 任务抽奖 API

### 11.1 当前 APP 接口

```text
POST https://user-api.smzdm.com/task/lottery
```

- 签名：APP 签名
- 前置条件：存在登录会话
- 业务参数：无
- 数据变更：执行一次任务抽奖
- 证据：E

Android `11.1.90` 调用链：

```text
Holder18009.J0()
  -> A1.E()
  -> Z0.f0()
  -> POST /task/lottery
```

响应：

```text
error_code
error_msg
data.gift_id
data.gift_name
data.gift_pic
data.description
```

仅在 `error_code == 0` 时消费 `data`。

### 11.2 已从项目移除的 Web JSONP 流程

```text
GET https://zhiyou.smzdm.com/user/lottery/jsonp_get_current
GET https://zhiyou.smzdm.com/user/lottery/jsonp_draw
```

旧项目曾从活动页面提取 `hashId` 作为 `active_id`，并依赖
`remain_free_lottery_count` 判断是否抽奖。该流程已移除，原因如下：

- Android `11.1.90` APK 中没有 `jsonp_get_current`、`jsonp_draw` 或
  `has_web_lottery` 的字符串及调用链。
- `remain_free_lottery_count` 只存在于无调用方的遗留模型。
- 当前只读响应不再返回历史免费次数字段。
- 无法证明 `has_web_lottery=true` 表示存在免费抽奖机会。
- 动态 `hashId` 在 APK 中用于百科、商品或文章模块，没有连接到抽奖
  `active_id`。

远程 H5 仍可能自行调用 JSONP，但其运行时 JavaScript 不在 APK 中，
不能作为当前 Python 任务实现的可靠依据。

### 11.3 已移除的硬编码活动回退方案

项目不再使用固定 `active_id`。当前任务抽奖直接使用 11.1.90 APK
可达的 `/task/lottery`。

## 12. 幸运屋 API

### 12.1 发现选项

```text
GET https://zhiyou.smzdm.com/user/crowd/
```

HTML 当前公开以下内容：

```text
data-crowd_id
data-title
reduceNumber
```

当前只读观察结果：

- 未发现免费选项。
- 有六个选项消耗不超过 5 碎银。

### 12.2 参与

```text
POST https://zhiyou.m.smzdm.com/user/crowd/ajax_participate
```

请求：

```text
crowd_id
sourcePage
client_type=android
sourceRoot
sourceMode
price_id
```

这是可能消耗虚拟资产的写操作。
本次验证没有发现免费选项或真实 `guide.crowd` 任务，因此没有调用该接口。

项目只会参与页面中明确标记为消耗 `0` 碎银的免费选项。付费选项与
`guide.crowd` 任务目标之间缺少已验证映射，因此不会自动参与，也不提供付费开关。

## 13. 众测 API

### 13.1 发现当前活动

```text
GET https://zhiyou.m.smzdm.com/task/task/ajax_get_activity_id
```

请求：

```text
from=zhongce
```

响应：

```text
data.activity_id
```

证据：A。

### 13.2 获取活动信息

```text
GET https://zhiyou.m.smzdm.com/task/task/ajax_get_activity_info
```

请求：

```text
activity_id
```

当前任务路径：

```text
data.activity_task.default_list[]
```

当前的 `default_list` 是扁平任务列表，并未按 `task_list` 分组。仍支持历史分组布局。

证据：A。

### 13.3 领取众测任务奖励

```text
POST https://zhiyou.m.smzdm.com/task/task/ajax_activity_task_receive
```

请求：

```text
task_id
```

该接口不使用 APP `robot_token` 奖励流程。

证据：E。已确认真实众测浏览任务完成后可领取奖励，任务状态由 `2` 变为 `4`。

### 13.4 读取能量信息

```text
GET https://test.m.smzdm.com/win_coupon/user_data
```

响应：

```text
data.my_energy.my_energy_total
data.my_energy.energy_expired_time
```

证据：A。

## 14. 已弃用和有意不支持的行为

### 已从当前执行中移除

- 将 `/tuijian/search_result` 用于用户关注
- 通过 `/ranking_list/articles` 随机选择文章
- Web JSONP 转盘流程及动态 `hashId → active_id` 映射
- 硬编码的转盘 `active_id` 回退方案
- 将 `/dy/util/api/user_action` 用于原生品牌任务
- 硬编码的账号专用 `sk`

### 仅作为兼容性解析保留

- `activity_task.accumulate_list`
- 历史分组的众测任务列表

### 有意不支持

- 自动评论
- 自动发布内容
- 自动申请众测
- 自动点赞、收藏或分享
- 自动参与付费幸运屋
- 绕过 CAPTCHA 或风控

## 15. 升级验证清单

发布新的 Android APP 版本时：

1. 记录 APK SHA-256 和版本代码。
2. 运行 `tools/extract_smzdm_apk_keys.py`。
3. 对比 `SIGN_KEY`、`SK_KEY`、APP 版本和版本代码。
4. 在 APK 中搜索每个标记为 B 或待确认的接口。
5. 重建 Retrofit 方法注解和表单字段构建器。
6. 验证只读接口，且不得输出凭据。
7. 对比响应键和列表布局。
8. 不要仅为发现接口而验证写入接口。
9. 更新本文档中的证据等级和观察日期。
10. 运行：

```bash
uv run ruff check src tests tools smzdm_ql.py
uv run ruff format --check src tests tools smzdm_ql.py
uv run pytest
uv build --no-sources
```

## 16. 日志与脱敏规则

切勿记录或持久化以下内容：

```text
Cookie
sess
token
robot_token
sk
smzdm_id
device_id
完整签名查询字符串
原始账号响应载荷
```

安全的诊断信息应仅包含：

```text
接口标签
HTTP 状态
API 状态码
响应字段名称
列表长度
字段存在性布尔值
异常类型
```

## 17. 实现索引

| 领域 | 当前源码 |
| --- | --- |
| 签名与 SK | `src/smzdm_bot/protocol.py` |
| HTTP 传输 | `src/smzdm_bot/client.py` |
| 签到与奖励 | `src/smzdm_bot/tasks/checkin.py` |
| 每日任务与互动 | `src/smzdm_bot/tasks/daily.py` |
| 转盘与幸运屋 | `src/smzdm_bot/tasks/lottery.py` |
| 众测 | `src/smzdm_bot/tasks/testing.py` |
| 任务策略 | `src/smzdm_bot/config/models.py` |
| 环境设置 | `src/smzdm_bot/config/settings.py` |
| 账号编排 | `src/smzdm_bot/tasks/runner.py` |

## 18. 已确认限制

- 点赞与收藏状态保存在 Android APP 本地 DAO，没有可用的独立状态 API。
- Python package 无法可靠恢复未知的原始点赞或收藏状态，因此固定跳过两类任务。
- Web JSONP 抽奖流程属于远程 H5 或历史实现，不是 Android `11.1.90`
  可验证的原生调用链。
- 阶段奖励、额外签到奖励和幸运屋参与接口在当前账号上没有满足调用条件，
  仍未完成 E 级验证。
- 分享接口仍只有历史实现证据；不会为了验证而构造虚假的分享目标。

