# 上班练枪摸鱼小游戏

一个适用于 Windows 的轻量桌面点击训练工具。运行后，目标会显示在全透明的桌面悬浮层上，不遮挡当前工作内容；参数面板可以随时收进系统托盘，适合利用短暂空闲时间做反应和鼠标控制练习。

## 功能特点

- 全透明、全屏、置顶的目标悬浮层
- 随机出现、逐个点击、移动目标三种训练模式
- 支持鼠标移动命中和点击命中
- 可调整颜色、大小、透明度、出现间隔、消失时间和命中范围
- 可使用自己的 PNG、JPG、WebP 等图片作为目标
- 可将目标限制在整个屏幕、中央 70% 或中央 45% 区域
- 关闭参数面板后自动收进系统托盘
- 全局暂停和快速退出热键

## 运行方法

1. 安装 Python 3.10 或更高版本。
2. 在项目目录执行：

   ```powershell
   pip install -r requirements.txt
   ```

3. 双击 `启动.bat`，或执行：

   ```powershell
   python desktop_aim_trainer.py
   ```

## 模式说明

- **随机出现**：目标按设定间隔出现，到时未命中会自动消失。
- **逐个点击**：屏幕始终只有一个目标，点击命中后才出现下一个。
- **移动目标**：屏幕上保持一个无规律移动的目标，用鼠标持续跟随。

## 快捷键

- `Ctrl + Alt + P`：全局暂停或继续
- `Ctrl + Alt + Q`：立即退出程序
- `Esc`：隐藏参数面板

## 环境

- Windows 10 / Windows 11
- Python 3.10+
- PySide6

## ROFL 部署

本仓库包含一个最小 Oasis ROFL 容器部署骨架：

- `Dockerfile`
- `compose.yaml`
- `rofl.yaml`
- `app.py`

本机检查：

```powershell
docker compose build
docker compose up
```

ROFL 流程：

```powershell
oasis rofl create --network testnet
oasis rofl build
oasis rofl update
oasis rofl deploy
oasis rofl machine show
oasis rofl machine logs
```

部署前需要配置：

- Oasis 钱包账户，并准备测试网或主网 ROSE。
- `compose.yaml` 中的 GitHub Container Registry 镜像名。
- 如果要运行真实挖矿程序，需要替换容器启动命令，并配置矿池地址和钱包地址。

本项目是一个轻量的休闲鼠标训练小游戏，请合理安排工作和休息时间。
