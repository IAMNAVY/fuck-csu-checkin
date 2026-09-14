# CSU Checkin

一个面向 GitHub Actions 的中南大学智慧学工自动打卡脚本。配置 GitHub Secrets 后，工作流会在每天北京时间 **20:00—22:30** 之间随机选择一个时刻执行一次打卡，并在 Actions 日志中保留执行记录。

项目保持轻量：Python 3.12+ 命令行程序，无 Web 服务、数据库或前端构建步骤。

> 本项目仅供获得授权的账号进行自动化操作。使用前请确认符合学校考勤制度、网站服务条款及当地法律法规。作者不对因使用本项目造成的漏打卡、误打卡或账号风险负责。

## 功能

- GitHub Actions 定时执行，也支持手动触发
- 每天在指定时间窗内随机选择执行时刻
- 支持 CAS 账号密码登录，并自动提取学校业务登录所需凭据
- 支持复用 `token` 与 `casual`，token 过期后可自动重新登录
- 支持 `GCJ-02`、`WGS-84`、`BD-09` 坐标输入
- 在给定坐标周围生成 50 米以内的随机定位点
- 可选百度地图逆地理编码，自动获取附近地点名称
- 支持 `--dry-run`，仅查询打卡班次和校验坐标，不提交打卡
- 适配 GitHub Actions 非交互环境，缺少配置时快速失败并给出提示

## 快速开始：GitHub Actions

### 1. 创建仓库

将本项目文件上传到 GitHub 仓库根目录。`.github/workflows/checkin.yml` 必须位于仓库根目录下：

```text
.github/workflows/checkin.yml
checkin.py
cli.py
api.py
auth.py
crypto_utils.py
coordinates.py
geocoding.py
config.py
requirements.txt
```

### 2. 配置 Secrets

进入仓库的 **Settings → Secrets and variables → Actions**，添加以下必需的 Repository secrets：

| 变量 | 必需 | 说明 |
| --- | --- | --- |
| `CHECKIN_USERNAME` | 是 | CAS 学号或账号 |
| `CHECKIN_PASSWORD` | 是 | CAS 密码 |
| `CHECKIN_LNG` | 是 | 打卡位置经度 |
| `CHECKIN_LAT` | 是 | 打卡位置纬度 |

可选变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CHECKIN_COORD` | `gcj02` | 输入坐标系：`gcj02`、`wgs84` 或 `bd09` |
| `CHECKIN_DKLB` | `PA` | 学校接口使用的打卡类别 |
| `CHECKIN_DKDZ` | 空 | 手动指定地点名称；设置后跳过逆地理编码 |
| `CHECKIN_BAIDU_AK` | 空 | 百度地图 AK；仅从仓库 Secret 读取，用于自动识别地点 |
| `CHECKIN_TOKEN` | 空 | 已有的 JWT token |
| `CHECKIN_CASUAL` | 空 | 与 token 配套的 `casual` 密钥 |

推荐配置 `CHECKIN_USERNAME` 和 `CHECKIN_PASSWORD`，这样 token 过期后可以在下一次任务中自动重新登录。若只配置 `CHECKIN_TOKEN` 和 `CHECKIN_CASUAL`，凭据过期后任务会失败，需手动更新 Secrets。

### 获取精确坐标

可以使用高德地图的[坐标拾取器](https://lbs.amap.com/tools/picker)获取打卡位置：

1. 打开坐标拾取器，搜索学校、校区或具体建筑。
2. 在地图上点击实际打卡位置。
3. 复制页面显示的经度和纬度，分别填写到 `CHECKIN_LNG` 和 `CHECKIN_LAT`。
4. 高德地图在中国大陆通常返回 GCJ-02 坐标，因此 `CHECKIN_COORD` 保持为默认值 `gcj02`；如页面明确标注了其他坐标系，请按实际情况修改。

百度地图逆地理编码只会使用 `CHECKIN_BAIDU_AK` 仓库 Secret 中的值，不会在代码中内置 AK。该配置可以不填；未填写时自动地点识别会跳过并以空地点继续提交。也可以使用 `CHECKIN_DKDZ` 直接指定地点名称，跳过逆地理编码。

### 3. 手动验证

打开仓库的 **Actions**，选择 **智慧学工自动打卡**，点击 **Run workflow**。手动执行默认立即运行，不等待每日随机时间窗；正式的定时任务仍按工作流中的计划执行。

### 4. 定时规则

默认工作流在每天北京时间 20:00 启动一个任务，然后随机等待 0—150 分钟，在 20:00—22:30 之间执行打卡：

```text
北京时间 20:00  ─────── 随机等待 ─────── 22:30
```

GitHub Actions 的 cron 使用 UTC，因此配置文件中使用 `0 12 * * *`。GitHub 的调度可能受到队列影响而延迟；工作流会以任务实际启动时间为基准，尽量将执行限制在当天时间窗内。

如需更换时间窗，请同时调整 `.github/workflows/checkin.yml` 中的启动 cron、随机等待上限和截止时间计算逻辑。

## 本地运行

```bash
python -m pip install -r requirements.txt
python checkin.py --dry-run --lng 112.9388 --lat 28.1716
```

不提供参数时，脚本会交互式询问账号、密码和坐标：

```bash
python checkin.py
```

CI 或其他非交互环境必须通过环境变量提供配置。例如：

```bash
CHECKIN_USERNAME=学号 \
CHECKIN_PASSWORD=密码 \
CHECKIN_LNG=112.9388 \
CHECKIN_LAT=28.1716 \
python checkin.py --dry-run
```

Windows PowerShell：

```powershell
$env:CHECKIN_USERNAME = "学号"
$env:CHECKIN_PASSWORD = "密码"
$env:CHECKIN_LNG = "112.9388"
$env:CHECKIN_LAT = "28.1716"
python checkin.py --dry-run
```

## 命令行参数

```text
--lng FLOAT             经度
--lat FLOAT             纬度
--coord {gcj02,wgs84,bd09}
                        输入坐标系
--dklb TEXT             打卡类别，默认 PA
--dkdz TEXT             手动指定地点名称
--token TEXT            JWT token
--casual TEXT           DES 密钥 casual
--username TEXT         CAS 账号
--dry-run               只查询和校验，不提交打卡
```

命令行参数优先级高于环境变量。认证信息未通过参数或环境变量提供时，本地交互模式会读取同目录下的 `checkin_config.json`，并在成功登录后保存 token 与 casual。该文件已经加入 `.gitignore`，不要手动提交它。

## 工作流程

1. 读取 GitHub Secrets、环境变量或本地配置。
2. 使用已有 token，或通过 CAS 登录获取新的业务凭据。
3. 将输入坐标转换为 GCJ-02。
4. 在坐标圆心 50 米范围内生成本次定位点。
5. 查询当前可用的打卡班次。
6. 校验定位点是否在学校允许的范围内。
7. 获取地点名称并提交打卡请求。
8. 将成功或失败状态输出到 GitHub Actions 日志。

## 安全与隐私

- 密码、token、坐标等敏感信息应只放在 GitHub Actions Secrets 中，不要写入源码、Issue、日志或提交记录。
- 工作流不会主动打印密码和 token，但第三方接口返回内容可能包含学校系统信息，请谨慎分享 Actions 日志。
- 本地 `checkin_config.json` 保存的是 token 和 casual，属于敏感文件；请限制文件访问权限并避免同步到云盘。
- `CHECKIN_BAIDU_AK` 为可选配置，只从 GitHub Actions Repository Secret 读取；不提供时自动地点识别会跳过并以空地点提交，也可以通过 `CHECKIN_DKDZ` 手动指定地点。
- 建议为自动化使用专用 GitHub 仓库，并限制仓库协作者和 Actions 权限。

## 开发与测试

安装依赖：

```bash
python -m pip install -r requirements.txt
```

语法检查：

```bash
python -m compileall -q .
```

项目没有内置的端到端测试。任何真实接口测试都可能产生实际打卡，请先确认账号授权和测试时间窗口。

## 项目结构

```text
.
├── .github/workflows/checkin.yml  # GitHub Actions 定时任务
├── checkin.py                      # 兼容入口
├── cli.py                          # 命令行流程与 CI 适配
├── auth.py                         # CAS 登录与 token 解析
├── api.py                          # 智慧学工接口客户端
├── crypto_utils.py                 # 请求体与密码加密
├── coordinates.py                  # 坐标转换和随机定位点
├── geocoding.py                    # 百度逆地理编码
├── config.py                       # 本地配置读写
├── requirements.txt                # Python 依赖
└── README.backup.md                # 原始 README 备份
```
