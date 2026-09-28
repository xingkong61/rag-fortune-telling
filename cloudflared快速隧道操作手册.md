# cloudflared 快速隧道操作手册

> 适用项目：RAG 问命（八字 / 梅花易数 / 六爻）
> 目的：让别人在公网用一条 HTTPS 链接访问你本机跑的服务
> 更新日期：2026-09-26

---

## 0. 最常用三步（急着用就看这里）

1. 双击 `scripts\start_public.cmd`
2. 在窗口里找到 `https://xxxx.trycloudflare.com` 这一行
3. 把这条网址发给对方，他直接用浏览器打开即可

---

## 1. 这套方案在做什么（原理）

```
   访客浏览器
        │  HTTPS（自动证书）
        ▼
   Cloudflare 边缘节点  ← 公网，无需你备案 / 无需公网 IP
        │  加密隧道（由本机主动向外建立的长连接）
        ▼
   本机 cloudflared  ──►  http://127.0.0.1:8300   （你的 FastAPI 服务）
```

四个关键点，理解了就不会踩坑：

| 特性 | 说明 |
|---|---|
| 不需要公网 IP | 出口由 Cloudflare 提供 |
| 不需要路由器端口映射 | 连接是**本机主动向外**建立的，家里的 NAT / 公司网络一般不阻拦 |
| 不需要域名备案 | 省掉花生壳那类 HTTP 映射的麻烦 |
| 本机不必对局域网开放 | 服务只监听 `127.0.0.1`，隧道在同一台机器上，够用且更安全 |

---

## 2. 前置条件

- **cloudflared 已安装**：本次通过 winget 安装，版本 `2026.9.3`
  - 安装位置：`C:\Program Files (x86)\cloudflared\cloudflared.exe`
  - 检查：在**新开的**终端里执行 `cloudflared --version`
  - 旧终端可能读不到 PATH，此时用全路径即可
  - 重装命令：
    ```powershell
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    ```
- **Python 环境可运行本项目**（能正常 `python main.py`）

---

## 3. 日常操作

### 方式 A：一键脚本（推荐）

双击 `scripts\start_public.cmd`，它做两件事：

1. 新开一个窗口启动应用：`HOST=127.0.0.1`、`PORT=8300`
2. 在当前窗口运行 cloudflared 隧道，并打印公网网址

**停止服务**：两个窗口分别按 `Ctrl+C`，或直接关掉窗口。

### 方式 B：手动敲两条命令

窗口 1（启动应用）：

```powershell
cd "c:\Users\13594\Desktop\工作区_trae\基于RAG的---"
$env:HOST = "127.0.0.1"
$env:PORT = "8300"
python main.py
```

窗口 2（建立隧道）：

```powershell
cloudflared tunnel --url http://127.0.0.1:8300 --no-autoupdate
```

> `--no-autoupdate` 是关闭自动更新，避免它在运行中自己重启导致网址变动。
> 如果提示 `cloudflared` 不是可识别的命令，换成：
> `& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8300 --no-autoupdate`

---

## 4. 公网网址在哪里看

隧道启动约 5 秒后会打印一个方框，**框里那一行就是你的公网地址**：

```
|  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
|  https://allowance-acid-circuit-genes.trycloudflare.com                                     |
```

- 这个网址**每次启动都会变**，换一次就是新地址，旧地址立即失效。
- 把网址发给别人时注意：**不要带端口号**，它走标准 443。

---

## 5. 怎么确认隧道通了

先在本机自测，能排除「服务没起来」和「隧道没连上」两类问题：

```powershell
curl.exe https://你的网址/healthz
# 期望输出：{"status":"ok"}
```

再打开浏览器访问 `https://你的网址`，能看到问命页面即成功。

开机运行时，隧道日志里出现下面这行说明已连上 Cloudflare：

```
INF Registered tunnel connection connIndex=0 ... location=lax11 protocol=quic
```

---

## 6. 常见问题排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 浏览器报 `ERR_EMPTY_RESPONSE`、502，或隧道日志出现 `Unable to reach the origin service` | **本机应用没在跑或已崩**（最常见） | 看窗口 1 是否还活着；`netstat -ano \| findstr :8300` 确认端口有监听 |
| 启动应用报 `10048 端口已被占用` | 已有一个实例占着 8300 | `netstat -ano \| findstr :8300` 找到 PID，再 `taskkill /PID <PID> /F`；或改 `PORT` 换端口（隧道命令里的端口要同步改） |
| 提示 `Allow outbound QUIC traffic on port 7844 or use HTTP2` | 网络封了 UDP 7844，cloudflared 已自动降级到 HTTP/2 | 属正常，可忽略；想显式指定就加 `--protocol http2` |
| 提示 `Cannot determine default configuration path` | 没有 config.yml，快速隧道本来就无需配置文件 | 忽略 |
| 之前能访问，突然全挂 | 窗口被关掉 / 进程被系统回收 / 电脑休眠 | 重新运行脚本，**网址会变**，需要把新网址再发一次 |
| 对方访问很慢或打不开 | 国内访问 `trycloudflare.com` 有时不稳定 | 换个时段或让他换网络；稳定性要求高就改用下文第 9 节方案 |
| 命令 `cloudflared` 找不到 | 新装后没刷新 PATH | 用全路径，或重开终端 |

---

## 7. 必须记住的三条限制

1. **网址每次启动都会变** —— 快速隧道是匿名临时隧道，不绑定你的账号。
2. **没有可用性保证** —— Cloudflare 明确声明 quick tunnel 不承诺 uptime，不适合正式对外提供服务。
3. **没有任何访问控制** —— 拿到网址的人都能用，会消耗你自己的 DashScope 额度。所以：
   - 不要把链接发到公开群组 / 社交平台
   - 需要长期共享的话，建议给服务加一道访问口令（当前尚未实现，需要时再补）

---

## 8. 常用运维命令速查

```powershell
# 查 8300 占用情况
netstat -ano | findstr :8300

# 杀掉占用进程（PID 换成上一步查到的）
taskkill /PID <PID> /F

# 看 cloudflared 是否在跑
Get-Process cloudflared

# 看应用是否在监听
Get-NetTCPConnection -LocalPort 8300 -State Listen
```

---

## 9. 想要固定网址？（进阶，可选）

快速隧道做不到固定网址。如果以后要长期对外提供，改用**带账号的命名隧道（named tunnel）**：

1. 需要一个自己的域名，并把 NS 托管到 Cloudflare（域名要花钱，且国内访问 Cloudflare 需看网络情况）
2. 登录并创建隧道：
   ```powershell
   cloudflared tunnel login
   cloudflared tunnel create rag-fate
   ```
3. 写 `config.yml` 绑定域名与本地服务，然后：
   ```powershell
   cloudflared tunnel run rag-fate
   ```

好处：网址固定、可配置访问策略（Cloudflare Access 做登录鉴权）、有正式 SLA。
坏处：需要域名和额外配置。要走这条路时再单独弄即可。

---

## 10. 方案对比（为什么最后选了它）

| 方案 | 公网地址 | 备案 | 稳定性 | 配置复杂度 |
|---|---|---|---|---|
| 花生壳（TCP 映射） | `域名:随机端口` | TCP 一般免备案 | 免费版限制多、易断 | 中（要在控制台配映射） |
| **cloudflared 快速隧道** | `https://xxx.trycloudflare.com` | **不需要** | 临时隧道，无 SLA | **低（一条命令）** |
| cloudflared 命名隧道 | 自己的域名，固定 | 不需要 | 好 | 高（需域名 + 配置文件） |