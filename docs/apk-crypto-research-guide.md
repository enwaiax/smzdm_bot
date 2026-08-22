# SMZDM Android 签名与 SK 静态分析指南

本文记录如何从合法取得的 SMZDM Android APK 中验证请求签名常量、SK 生成常量及其调用链，并说明应用升级后的重复检查流程。

本文只讨论本地静态分析。脚本不会读取 Cookie、不会登录账号、不会请求 SMZDM API，也不会自动修改项目源码。

## 免责声明

本文档及配套脚本仅用于合法的软件互操作性研究、安全研究、个人学习和已获授权的维护工作，不构成法律意见，也不授予任何超出法律、软件许可协议或平台服务条款的权利。

使用者必须确保：

- 仅分析自己合法取得且有权研究的 APK、账号、设备和数据。
- 遵守适用法律法规、著作权要求、软件许可协议及平台服务条款。
- 不将本文内容用于未授权访问、凭证窃取、验证码或风控绕过、批量滥用、虚假互动、数据抓取、商业利用或其他损害平台及用户权益的行为。
- 不传播真实 Cookie、session、token、用户 ID、设备标识、个人资料或未经授权的内部数据。
- 在执行任何线上请求前取得明确授权，坚持最小请求、最低频率和可审计原则；默认只进行本地离线分析。
- 如果研究中发现可能影响平台或用户安全的漏洞，应停止扩大验证范围，保留必要证据，并通过适当渠道进行负责任披露。

APK 中存在可提取的常量，不代表平台允许第三方调用相关接口。免责声明不能使未经授权的行为合法化，也不能消除账号封禁、数据损失、法律责任或其他风险。使用者应自行评估并承担使用后果；如无法确认授权边界，应停止操作并寻求专业法律或安全合规意见。

## 研究推理链

本节记录可复现的工程推理和证据链，而不是不可验证的主观猜测或逐字思维过程。目标是让后续维护者知道每个结论为何成立、哪些假设已被排除，以及升级后应从哪里重新开始。

### 研究问题

需要回答四个独立问题：

1. 当前项目中的 `SIGN_KEY` 是否仍被最新版 APP 使用？
2. 当前项目中的 `SK_KEY` 是否仍被最新版 APP 使用？
3. SK 的 plaintext、cipher、padding 和 encoding 是否发生变化？
4. 请求参数排序、空值过滤、空格处理和 MD5 输出格式是否发生变化？

只有同时回答这些问题，才能判断现有 Python 实现是否仍与 APP 一致。仅在 APK 中搜索到相同字符串并不足以证明它仍位于有效调用链中。

### 初始假设

分析开始时保留以下互斥或并存假设：

- H1：两个 Key 仍以 DEX 明文常量存在。
- H2：Key 未变化，但其中一个已迁移到 native library。
- H3：Key 被拆分、编码或运行时计算，静态字符串搜索无法直接找到。
- H4：Key 已变化，但算法结构未变化。
- H5：Key 和算法均已变化，社区旧实现已经失效。

分析原则是逐步收集证据排除假设，而不是先认定社区代码正确。

### 阶段一：确认 APK 完整性

最初读取 APK 时发现：

- 文件头为标准 ZIP local header：`PK\x03\x04`
- 标准 ZIP 工具提示找不到 central directory
- 文件大小约为 19 MB
- 可以定位部分 `classes*.dex` local header

这存在两种可能：

- 文件损坏或下载不完整
- 文件仍在复制或下载

没有立即把它判定为错误 APK，而是检查文件尾、central directory 和文件大小变化。稍后文件增长到约 92 MB，并能通过 Python `zipfile` 正常读取，最终确认它当时仍在写入。

经验：

- APK 文件名存在不代表下载完成。
- 分析前必须同时检查 ZIP 可读性、文件大小稳定性和 SHA-256。
- 不应基于正在变化的文件发布最终哈希或结论。

完整后确认：

```text
package      = com.smzdm.client.android
versionName  = 11.1.90
versionCode  = 1190
dexCount     = 12
```

### 阶段二：建立社区实现基线

在多个开源实现中发现两个共同常量及两套主要认证路径：

- 请求签名常量用于 `sorted parameters + "&key=" + SIGN_KEY`
- SK 常量用于 DES 加密
- 一类实现直接使用 Cookie 中的 `sess`
- 另一类实现先请求 `/robot/token`

Git 历史显示：

- `SIGN_KEY` 至少在 2023 年的公开实现中已存在。
- 自动计算 SK 的代码在 `hex-ci/smzdm_script` 2023-08-08 的 `Automatic sk acquisition` 提交中加入。

但开源代码只能作为搜索线索，不能作为最新版 APK 的证据。复制传播可能导致多个仓库同时保留同一个过期实现。

### 阶段三：离线验证历史 SK 公式

在接触最新版 APK 调用链前，先用公开历史脚本中的固定 SK 验证候选算法：

```text
candidate plaintext = smzdm_id + device_id
candidate cipher    = DES/ECB/PKCS7Padding
candidate output    = Base64
```

使用候选 `SK_KEY` 的前 8 字节解密历史固定 SK 后得到：

- Base64 可正常解码
- DES 解密成功
- PKCS padding 完全有效
- 明文长度为 42
- 明文结构符合 `10 位数字 + 32 位字母数字`

这与 `smzdm_id + device_id` 的结构吻合。

历史固定 SK 与同一提交中出现的 Cookie 并不匹配，说明两者来自不同账号或设备。该不匹配不能否定算法；有效 padding 和严格的明文结构为候选算法提供了独立支持。

这一阶段证明“社区算法能够解释历史抓包值”，但仍未证明最新版 APP 继续使用该算法。

### 阶段四：APK 全局字符串初筛

对所有完整 DEX 和 native library 进行初筛：

- `SK_KEY` 明文出现在 `classes12.dex`
- `/checkin`、`robot/token`、`smzdm_id`、`device_id` 分布在多个 DEX
- 旧 `SIGN_KEY` 没有出现在任何 DEX
- `classes12.dex` 中存在 `&key=` 和 `ZDMKeyUtil`

由此：

- H1 仅对 `SK_KEY` 成立。
- `SIGN_KEY` 不在 DEX，H2 或 H3 的可能性上升。
- 仅凭 `SK_KEY` 字符串存在仍不能排除它是遗留死代码，必须继续追踪 xref。

### 阶段五：还原 SK 调用链

在 `classes12.dex` 中定位 `SK_KEY` 的字符串引用，得到：

```text
class  = Lcom/smzdm/client/base/utils/s;
method = p()Ljava/lang/String;
```

该方法执行：

```text
b.u0()
  -> current user ID

s.r(false)
  -> raw device ID

user ID + device ID
  -> A.h(SK_KEY, ..., plaintext)
```

继续分析 `A.h()`、`A.i()` 和 `A.f()`：

```text
DESKeySpec
SecretKeyFactory.getInstance("DES")
Cipher.getInstance("DES")
Cipher.ENCRYPT_MODE
Cipher.doFinal(...)
Base64Encoder.encode(...)
```

这直接证明：

- `SK_KEY` 位于有效加密调用链中，不是无关遗留字符串。
- cipher 为 Java `DES`。
- Android provider 默认 transformation 为 `DES/ECB/PKCS5Padding`。
- `DESKeySpec` 使用 Key 的前 8 字节。
- 输出经过 Base64。

随后定位 `s.p()` 的调用者：

```text
com.smzdm.client.android.utils.A1.g(...)
  -> s.p()
  -> base/data/a.f1("", sk)
  -> form field "sk"
  -> POST https://user-api.smzdm.com/checkin
```

至此，H4 和 H5 在 SK 路径上被排除：11.1.90 仍使用现有 Key 和现有算法。

### 阶段六：还原 SIGN_KEY 调用链

从 `&key=` 字符串反向定位到两个请求签名方法：

```text
LFh/a.c(Map, String)
LFh/d.b(Map, String)
```

两个方法的行为一致：

```text
collect map keys
  -> Collections.sort(keys)
  -> skip null and empty values
  -> append key=value pairs
  -> append "&key="
  -> ZDMKeyUtil.a().b()
  -> remove ASCII spaces
  -> MD5
  -> uppercase
```

`ZDMKeyUtil.b()` 不再返回 DEX 常量，而是调用：

```text
private native getDefaultNativeKey()
```

类初始化器加载：

```text
System.loadLibrary("lib_zdm_key")
```

APK 中对应文件实际为：

```text
lib/arm64-v8a/liblib_zdm_key.so
```

因此 H2 得到支持：`SIGN_KEY` 没有变化，但被迁移到 native library。

### 阶段七：ARM64 native 证据

ELF dynamic symbol table 中存在：

```text
Java_com_smzdm_client_base_utils_ZDMKeyUtil_getDefaultNativeKey
```

符号信息：

```text
function address = 0x6ee0
function size    = 324 bytes
```

反汇编函数后发现 ARM64 指令组合：

```text
ADRP x1, <rodata page>
ADD  x1, x1, <offset>
```

计算出的字符串虚拟地址为：

```text
0x215a0
```

该地址位于 ELF `.rodata`，内容与项目当前 `SIGN_KEY` 完全一致。函数随后通过 JNI string 创建路径将其返回给 Java。

这不是“在 native 文件中碰巧搜到相同字符串”，而是证明 native getter 的有效函数直接引用该地址。H3、H4 和 H5 在签名 Key 路径上被排除。

### 阶段八：对照 Python 实现

将 APK 证据逐项与 `src/smzdm_bot/client.py` 对比后发现：

一致项：

- 参数按 key 排序
- 跳过空值
- 追加 `&key=<SIGN_KEY>`
- MD5 转大写
- SK plaintext 为 `smzdm_id + device_id`
- DES ECB
- PKCS padding
- Base64 输出
- DES 使用 Key 的前 8 字节

差异项：

1. Python 原实现删除空格、Tab 和换行；APK 只执行 `replaceAll(" ", "")`。
2. Python 默认 APP 版本仍为 `10.4.26/866`；APK 为 `11.1.90/1190`。
3. Cookie 缺少 `device_id` 时，Python 会每次随机生成新值，导致同一账号 SK 不稳定。

据此完成修正：

- 签名只删除 ASCII 空格。
- 默认版本更新为 `11.1.90/1190`。
- 自动生成 SK 时强制要求 `smzdm_id` 和 `device_id`。
- 手动配置 SK 时仍允许缺少设备字段。
- 使用纯合成数据建立固定测试向量。

### 证据强度分级

直接证据：

- DEX instruction 中的字符串引用和方法调用。
- `Cipher.getInstance("DES")`、`DESKeySpec` 和 encrypt mode。
- `/checkin` form builder 接收 `s.p()` 返回的 SK。
- ELF dynamic symbol。
- native getter 的 ARM64 字符串引用地址。
- `.rodata` 中被 getter 直接引用的 Key。

交叉验证证据：

- 历史固定 SK 可用候选 Key 正常解密。
- 解密 plaintext 结构严格符合 user ID + device ID。
- Python 和社区 Node.js 实现产生相同结构的结果。

仍属于推断或运行时依赖：

- Java `Cipher.getInstance("DES")` 在目标 Android provider 上按标准映射为 `DES/ECB/PKCS5Padding`。
- Cookie 中的 `device_id` 与 APP 内部 `H.g(false)` 返回值应保持一致。
- 服务端当前是否实际强制校验每个接口中的 SK，静态分析无法证明。

### 可证伪条件

未来出现以下任一证据时，当前结论必须重新评估：

- `ZDMKeyUtil` 不再加载当前 native library。
- native getter 不再引用静态字符串。
- 签名方法改用 HMAC、SHA-256、nonce 或服务端 challenge。
- SK 加密不再调用 `DES`。
- SK plaintext 不再由 user ID 与 device ID组成。
- 出现 IV、AES、RSA、native-only cipher 或服务端返回的 SK。
- `/checkin` 不再使用当前 form builder。
- 动态抓包结果无法由静态还原算法复现。

### 失败路线与优化经验

本次分析中出现过几条低效或不可靠路线：

1. 对未下载完成的 APK 直接使用标准 ZIP 工具  
   结果：误报文件损坏。  
   改进：先确认文件大小稳定、central directory 可读并计算最终 SHA-256。

2. 只搜索已知 Key 字符串  
   结果：能找到 `SK_KEY`，却无法解释 `SIGN_KEY` 的来源，也无法证明字符串仍在有效路径。  
   改进：必须继续追踪 xref、调用者和最终请求入口。

3. 对整个 DEX 建立完整 Androguard analysis graph  
   结果：日志接近 1 MB，运行约 3 分钟，且并非定位字符串调用所必需。  
   改进：直接使用 `DEX` instruction iterator，再根据 helper marker 缩小到候选 DEX，自动脚本约十几秒即可完成。

4. 直接信任开源仓库中的固定 SK  
   结果：无法确认所属账号、设备和 APP 版本。  
   改进：仅将其用于离线密码学交叉验证，生产测试全部使用合成 fixture。

5. 自动把低置信度候选写入源码  
   风险：native symbol 或类名变化时可能误选无关字符串。  
   改进：提取器只输出候选、证据和置信度，不自动修改 `client.py`。

这条研究链的核心不是记住两个 Key，而是形成以下可重复方法：

```text
verify artifact
  -> establish hypotheses
  -> search constants and protocol markers
  -> trace DEX references
  -> reconstruct data flow
  -> cross JNI boundary
  -> trace native symbol and rodata reference
  -> compare implementation behavior
  -> create synthetic regression vectors
  -> perform minimal authorized runtime validation
```

## 1. 当前已验证结论

验证样本：

- Package：`com.smzdm.client.android`
- Version：`11.1.90`
- Version code：`1190`
- SHA-256：`59ed9d2774d888096200a6399217aa3a2653d543a81d7976ff194c10dce19a5b`

### 1.1 SIGN_KEY 调用链

APK 11.1.90 已不在 DEX 中直接保存 `SIGN_KEY`，而是通过 JNI 从 native library 获取：

```text
request parameters
  -> LFh/a.c(Map, String) or LFh/d.b(Map, String)
  -> append "&key="
  -> ZDMKeyUtil.a().b()
  -> ZDMKeyUtil.getDefaultNativeKey()
  -> lib/arm64-v8a/liblib_zdm_key.so
  -> Java_com_smzdm_client_base_utils_ZDMKeyUtil_getDefaultNativeKey
```

native getter 在 ARM64 函数中引用 `.rodata` 字符串，再通过 JNI 返回 Java `String`。

签名算法：

```text
1. 按参数名进行字典序排序
2. 跳过 null 和空字符串
3. 拼接为 key1=value1&key2=value2
4. 追加 &key=<SIGN_KEY>
5. 删除值中的 ASCII 空格
6. 计算 MD5
7. 转成大写十六进制
```

等价表达：

```text
sign = UPPERCASE(MD5(sorted_form_data + "&key=" + SIGN_KEY))
```

### 1.2 SK_KEY 调用链

签到入口调用动态 SK 生成函数：

```text
com.smzdm.client.android.utils.A1.g(...)
  -> com.smzdm.client.base.utils.s.p()
  -> SharedPreferencePool user ID: b.u0()
  -> device ID: s.r(false)
  -> A.h(SK_KEY, ..., user_id + device_id)
  -> A.i(...)
  -> A.f(...)
  -> DES encryption
  -> Base64
  -> request form field "sk"
  -> POST https://user-api.smzdm.com/checkin
```

DEX 中的加密实现使用：

```text
DESKeySpec
SecretKeyFactory.getInstance("DES")
Cipher.getInstance("DES")
Cipher.ENCRYPT_MODE
```

Android 中 `Cipher.getInstance("DES")` 对应：

```text
DES/ECB/PKCS5Padding
```

对于 DES 的 8 字节 block，PKCS5Padding 与 PKCS7Padding 的结果相同。

最终公式：

```text
plaintext = smzdm_id + device_id
sk = Base64(DES-ECB-PKCS5Padding(plaintext, SK_KEY[:8]))
```

虽然源码中的 `SK_KEY` 字符串超过 8 字节，但 `DESKeySpec` 实际使用前 8 字节。项目中的 Python 实现与该行为一致。

## 2. 自动提取脚本

脚本位置：

```text
tools/extract_smzdm_apk_keys.py
```

脚本使用 PEP 723 内联依赖，由 `uv` 创建隔离环境，不会把 Androguard、Capstone 和 pyelftools 加入生产依赖。

### 2.1 基本运行

```bash
uv run tools/extract_smzdm_apk_keys.py /path/to/smzdm.apk
```

输出内容：

- Package、version name、version code
- APK SHA-256
- DEX 和 native library 数量
- `SIGN_KEY` 候选值、来源、置信度和 native symbol 证据
- `SK_KEY` 候选值、来源、置信度和 DEX 方法证据
- DES、用户 ID、设备 ID 调用特征是否存在

### 2.2 JSON 输出

```bash
uv run tools/extract_smzdm_apk_keys.py /path/to/smzdm.apk --json
```

JSON 适合保存到 CI artifact 或与上一版本结果进行结构化比较。保存前应评估是否允许在当前环境持久化应用内置常量。

### 2.3 退出码

- `0`：两个 Key 均以 `high` 或 `medium` 置信度找到
- `1`：APK 可分析，但至少一个 Key 缺失或只有低置信度候选
- `2`：文件不存在、ZIP/APK 损坏或缺少 DEX

## 3. 脚本如何定位 Key

### 3.1 SIGN_KEY

高置信度路径：

1. 在 APK 中寻找 `liblib_zdm_key.so`。
2. 读取 ELF dynamic symbol table。
3. 找到以 `ZDMKeyUtil_getDefaultNativeKey` 结尾的 JNI symbol。
4. 使用 Capstone 反汇编该函数。
5. 解析 ARM64 `ADRP + ADD` 组合得到字符串虚拟地址。
6. 将虚拟地址映射回 ELF load segment。
7. 读取 getter 实际引用的字符串。

如果 JNI symbol 被删除或函数结构变化，脚本会退化为 native printable string 候选扫描，并将置信度标记为 `low`。低置信度结果不能直接写入项目。

### 3.2 SK_KEY

高置信度路径：

1. 遍历所有 `classes*.dex`。
2. 寻找调用 `com/smzdm/client/base/utils/A.h(...)` 的方法。
3. 提取该调用点所在方法的常量字符串。
4. 优先选择 `com/smzdm/client/base/utils/s.p()` 中的候选。
5. 独立检查 DEX 是否仍包含 DES cipher、用户 ID 和设备 ID 数据源。

如果升级后类名、方法名或加密 helper 被重命名，脚本可能返回缺失。这种情况下应该更新结构匹配规则，而不是从全部字符串中盲选一个值。

## 4. 每次 APP 升级后的检查流程

### Step 1：保存可信 APK

只使用有权分析且来源可信的 APK。记录：

- 下载来源
- 文件名
- Package
- Version name/code
- SHA-256

不要使用仍在下载或复制中的文件。完整 APK 应能被标准 ZIP 工具读取中央目录。

### Step 2：运行提取器

```bash
uv run tools/extract_smzdm_apk_keys.py new-smzdm.apk --json
```

重点检查：

- Package 是否仍为 `com.smzdm.client.android`
- 两个 Key 的置信度是否为 `high`
- Key 是否发生变化
- `des_cipher_present` 是否为 `true`
- `user_id_source_present` 是否为 `true`
- `device_id_source_present` 是否为 `true`

### Step 3：人工核对调用链

即使脚本返回 `high`，也至少核对以下事实：

- `SIGN_KEY` 确实由请求签名函数调用，而不是无关遗留字符串
- `SK_KEY` 确实进入签到 SK 加密函数
- SK plaintext 仍由用户 ID 和设备 ID组成
- 签名参数排序、空值过滤、空格处理和 MD5 大小写没有变化

### Step 4：更新项目

只有在证据充分时才更新：

```text
src/smzdm_bot/client.py
```

可能需要更新：

- `SIGN_KEY`
- `SK_KEY`
- `DEFAULT_VERSION`
- `DEFAULT_VERSION_CODE`
- `compute_request_signature()`
- `generate_security_key()`

不要让提取脚本自动覆写生产源码，避免低置信度或误识别结果直接进入签到逻辑。

### Step 5：运行离线测试

```bash
uv run pytest
uv run ruff check src tests tools
```

测试必须使用合成的 `smzdm_id`、`device_id`、Cookie 和 session。禁止把真实 Cookie、token、用户 ID 或抓包响应提交到仓库。

### Step 6：验证认证

先调用只读接口验证 Cookie 和通用签名，例如项目使用的 `/vip`。日志只能输出成功状态和错误类型，不能输出 Cookie、session 或完整响应。

### Step 7：验证签到

只有只读验证通过并得到明确授权后，才调用一次 `/checkin`。需要分别记录：

- 首次签到成功响应
- 今日已签到响应
- SK 无效响应
- Cookie 失效响应

保存测试 fixture 前必须彻底脱敏。

## 5. 常见失败情况

### APK 不完整

表现：

- `BadZipFile`
- 找不到 ZIP central directory
- 文件大小仍在变化

处理：等待下载或复制完成，重新计算 SHA-256 后再分析。

### Split APK

如果下载的是 `.apks`、`.xapk` 或多个 split：

- DEX 通常位于 base APK
- ARM64 native library 可能位于 config split

提取器当前要求单个 APK 同时包含 DEX 和目标 native library。应先取得完整、合法的 universal/arm64 APK，或分别分析 base 与 native split。

### Native symbol 被移除

如果 `getDefaultNativeKey` 被隐藏、重命名或完全内联：

- 脚本可能只返回低置信度字符串
- 需要重新定位 `ZDMKeyUtil.b()` 的 native bridge
- 根据 JNI registration table 或 native call reference 追踪实际 getter

不能仅凭字符串形态判定 Key。

### SK 算法变化

如果以下任意检查失败，不能继续沿用现有公式：

- 不再使用 `DES`
- plaintext 不再包含 user ID/device ID
- 出现 IV、nonce、HMAC、AES 或 native-only 加密
- SK 由服务端接口返回

此时应重新建立完整数据流，而不是只替换常量。

## 6. 安全与维护原则

- 只分析有权使用的 APK。
- APK 内置常量不是用户 Cookie，但仍属于协议敏感信息，不应无目的扩散。
- 不提交真实 Cookie、session、token、设备标识或用户资料。
- 不使用开源仓库中意外泄露的 Cookie 作为测试 fixture。
- 所有离线测试使用合成数据。
- Key 提取、代码更新和线上请求必须分为三个独立步骤。
- 自动化功能默认只启用签到和状态查询；互动类任务应单独评估平台规则与账号风险。

