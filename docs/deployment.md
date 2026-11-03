# 部署与日常操作

## 电脑和板卡

电脑首次部署建议使用 Windows 10/11 与 Python 3.12。板端使用发行版提供的 OpenCV 和 NumPy；原环境为 Python 3.10.4、OpenCV 4.5.4、NumPy 1.21.5，不强制在板上安装电脑端的测试依赖。

相机接开发板 USB-A 主机口。传送带独立供电、独立启停。镜头朝向带面，先确认画面清晰，再调阈值；多个样品之间留出空隙。

## 配置和部署

`config.example.json` 是默认示例，实际运行读取 `config.json`。修改 `host`、`username`、`remote_dir`、`camera_device` 和 `http_port` 时应与板端一致；`serial_port` 留空可在工具里选择串口。电脑和板卡必须在同一可达网段。

1. `01_setup.bat`：在项目目录创建虚拟环境，安装电脑部署和串口依赖。
2. `02_deploy.bat`：输入板卡密码；首次连接核对 SSH 指纹。上传程序，备份旧应用，安装并启用服务。已保存的板端参数予以保留。
3. `05_check.bat`：检查状态、图像和帧号是否更新。
4. `03_install_desktop.bat`：安装桌面入口和配置。
5. `04_serial.bat`：接收系统调试串口中的 ORE JSON。

初次部署必须完成 SSH 和相机节点检查。板端安装脚本会自动生成与路径、账号相匹配的 service；仓库中的 `board/ore-vision.service` 是原环境参考，不必手工覆盖。

## 手动安装

将整个项目复制到板上，例如 `/home/xilinx/b220-ore-vision`，然后执行：

```bash
sudo bash /home/xilinx/b220-ore-vision/board/install_board.sh /home/xilinx/jupyter_notebooks/ore xilinx /dev/video0 8000 /usr/bin/python3
systemctl status ore-vision --no-pager
```

账号、相机节点和目录按实际环境替换。打开 `http://板卡地址:8000/`。停止服务后也可以手动调试：

```bash
sudo systemctl stop ore-vision
cd /home/xilinx/jupyter_notebooks/ore
python3 app_ps.py --device /dev/video0 --port 8000
```

结束调试后执行 `sudo systemctl start ore-vision`，避免两个程序同时占用相机。

## 日常使用和采集日志

开发板通电，接好相机和网络，等待服务启动，再打开桌面入口。先停带检查画面和参数，再低速启动传送带。电脑重启后重新打开入口即可；板端系统和相机应已正常启动。

```powershell
python tools/collect_logs.py --url http://192.168.2.99:8000 --samples 30 --out logs
python tools/serial_log.py --port COM12 --out logs/uart.txt
```

COM12 只是示例，按设备管理器中的端口修改。串口输出以 `ORE ` 开头，后接 JSON；系统启动日志可能混在其中。关闭其他占用串口的软件后再打开接收工具。
