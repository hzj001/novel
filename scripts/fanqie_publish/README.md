# 番茄小说自动发布脚本

在你**自己的电脑**上运行，用 Playwright 控制浏览器：你负责登录，脚本负责按章节填标题/正文并保存或发布。

> ⚠️ **安全提示**：不要把账号密码写进脚本。使用 `login.py` 手动登录后保存本地会话文件即可。  
> ⚠️ **合规提示**：请遵守番茄小说平台规则，控制发布频率，避免触发风控。

## 一、环境准备

```bash
# 1. 进入仓库根目录
cd /path/to/9Y

# 2. 安装依赖
pip install -r scripts/fanqie_publish/requirements.txt

# 3. 安装 Chromium（Playwright 浏览器）
playwright install chromium
```

## 二、配置

编辑 `scripts/fanqie_publish/config.yaml`：

```yaml
writer_id: "你的作家ID"
book_id: "你的书籍ID"
chapters_dir: "novels/雨夜来电/chapters"
default_mode: "draft"   # 建议先用 draft 只存草稿
```

你的发布页链接示例：

`https://fanqienovel.com/main/writer/7650920070733892670/publish/7651092222896505406`

其中 `7650920070733892670` = writer_id，`7651092222896505406` = book_id。

## 三、首次登录（只需一次）

```bash
python scripts/fanqie_publish/login.py
```

1. 弹出浏览器  
2. **手动扫码/登录**番茄作家后台  
3. 登录成功后回终端按回车  
4. 生成 `scripts/fanqie_publish/state.json`（已加入 .gitignore，勿上传）

登录过期后，重新运行 `login.py` 即可。

## 四、发布章节

### 1. 预览计划（不打开浏览器）

```bash
python scripts/fanqie_publish/publish.py --dry-run --start 1 --end 5
```

### 2. 先试发 1 章草稿（强烈推荐）

```bash
python scripts/fanqie_publish/publish.py --start 1 --end 1 --mode draft
```

成功后去番茄后台检查：标题、正文、排版是否正确。

### 3. 批量存草稿

```bash
python scripts/fanqie_publish/publish.py --start 1 --end 10 --mode draft
```

### 4. 正式发布（会点「下一步」「确认发布」）

```bash
python scripts/fanqie_publish/publish.py --start 1 --end 5 --mode publish
```

### 5. 断点续发（跳过已发章节）

```bash
python scripts/fanqie_publish/publish.py --resume --mode draft
```

已发记录保存在 `scripts/fanqie_publish/published_log.json`。

## 五、常用参数

| 参数 | 说明 |
|------|------|
| `--start N` | 从第 N 章开始 |
| `--end N` | 到第 N 章结束 |
| `--count N` | 最多发 N 章 |
| `--mode draft` | 只存草稿（默认，更安全） |
| `--mode publish` | 尝试正式发布 |
| `--resume` | 跳过已记录在 log 里的章节 |
| `--dry-run` | 只打印计划 |
| `--delay 10` | 章与章之间等待 10 秒 |

## 六、章节文件格式

脚本读取 `novels/雨夜来电/chapters/chapter_XX.md`：

```markdown
# 第一章 错拨

正文第一段...

正文第二段...
```

- 第一行 `# 第X章 标题` → 番茄章节标题  
- 其余为正文（自动去掉 `**加粗**` 和 `---` 分隔线）

## 七、故障排查

### 1. 提示找不到登录状态

```bash
python scripts/fanqie_publish/login.py
```

### 2. 标题/正文填不进去

番茄页面可能改版。用浏览器 F12 检查元素，修改 `publish.py` 顶部选择器：

```python
SEL_TITLE = 'input.serial-editor-input-hint-area[placeholder="请输入标题"]'
SEL_EDITOR = '.serial-editor-container .ProseMirror[contenteditable="true"]'
```

### 3. 发布按钮点不了

- 先用 `--mode draft` 只存草稿  
- 检查章节字数是否达到平台要求  
- 在浏览器里手动完成最后一步确认

### 4. 登录失效 / 要求重新扫码

重新运行 `login.py`。

## 八、文件说明

| 文件 | 作用 |
|------|------|
| `login.py` | 手动登录，保存会话 |
| `publish.py` | 自动填章/发布 |
| `config.yaml` | 书籍 ID、路径、间隔等配置 |
| `state.json` | 登录会话（本地，勿提交） |
| `published_log.json` | 已发章节记录 |

## 九、推荐发布流程

1. `login.py` 登录  
2. `--dry-run` 看计划  
3. `--start 1 --end 1 --mode draft` 试一章  
4. 后台人工检查  
5. 小批量 `--mode draft` 或 `--mode publish`  
6. `--resume` 续发剩余章节  

---

**我不能替你在云端运行此脚本**（需要你的本机浏览器和你的登录态）。请把仓库拉到本地后按上述步骤操作。
