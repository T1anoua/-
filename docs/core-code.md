# 核心代码索引

RAR编号对应外层“核心代码RAR”文件夹。每个压缩包保留原相对路径；完整运行请使用整个项目。

| 编号 | 文件 | 用途 | 入口或依赖 |
| --- | --- | --- | --- |
| 01 | [src/ps/app_ps.py](../src/ps/app_ps.py) | 板端入口：相机采集、HTTP服务、状态管理、配置保存和串口输出。 | main、camera_loop、State；依赖同目录算法、index.html、settings.json、badges/。 |
| 02 | [src/ps/multi_vision.py](../src/ps/multi_vision.py) | 多目标检测：阈值分割、轮廓筛选、中心和方向计算及画面标注。 | detect_all、process_frame；依赖OpenCV、NumPy及颜色和跟踪模块。 |
| 03 | [src/ps/multi_tracking.py](../src/ps/multi_tracking.py) | 多目标跟踪：轨迹预测、全局关联、滤波与短时丢失处理。 | MultiTracker、Tracker、assign；由multi_vision.py调用。 |
| 04 | [src/ps/color_labels.py](../src/ps/color_labels.py) | 颜色规则：目标内部HSV统计、九色判断和暗场混色拒绝。 | classify_color；依赖OpenCV和NumPy。 |
| 05 | [src/ps/specimen_catalog.py](../src/ps/specimen_catalog.py) | 标本名称库：42项标本名称、九色映射及名称查找。 | SPECIMENS、DEFAULT_MAPPING、apply_name。 |
| 06 | [src/ps/settings.json](../src/ps/settings.json) | 默认视觉参数：阈值、面积、目标数和名称映射初始值。 | 由app_ps.py读取；页面保存后更新板端配置。 |
| 07 | [src/ps/index.html](../src/ps/index.html) | 网页界面：视频、参数、目标列表及名称选择界面。 | 由板端HTTP服务提供，依赖/api/status等接口。 |
| 08 | [board/deploy.py](../board/deploy.py) | 上传部署：通过SSH和SFTP上传应用并执行板端安装。 | 电脑运行；依赖paramiko、configuration.py和config.json。 |
| 09 | [board/configuration.py](../board/configuration.py) | 部署配置：读取并校验连接、目录、相机和串口参数。 | load_config、base_url；默认读取根目录config.json。 |
| 10 | [board/check_live.py](../board/check_live.py) | 取流检查：读取板端接口检查状态、帧号和图像。 | 电脑运行；板端服务需已启动。 |
| 11 | [board/install_board.sh](../board/install_board.sh) | 板端安装：备份、安装应用并生成启用systemd服务。 | 板端sudo bash执行；需要完整src/ps目录或部署暂存目录。 |
| 12 | [board/ore-vision.service](../board/ore-vision.service) | 自启服务参考：原环境的systemd服务配置。 | 实际部署优先使用install_board.sh自动生成匹配账号和目录的service。 |
| 13 | [src/pc/ore_app_launcher.cs](../src/pc/ore_app_launcher.cs) | 桌面入口源码：读取配置并打开板端独立应用窗口。 | 使用build/build_app.ps1编译；依赖launcher.html和图标。 |
| 14 | [src/pc/launcher.html](../src/pc/launcher.html) | 桌面启动页面：为桌面入口提供连接页面。 | 构建时嵌入C#程序，不直接替代板端index.html。 |
| 15 | [src/pc/install_desktop.ps1](../src/pc/install_desktop.ps1) | 桌面入口安装：复制应用及配置并创建桌面快捷方式。 | 依赖b220_ore_app.exe和根目录config.json。 |
| 16 | [src/pc/serial_monitor.py](../src/pc/serial_monitor.py) | 串口查看：列出串口并接收ORE识别结果。 | 电脑运行；依赖pyserial及配置模块。 |
| 17 | [build/windows_task.ps1](../build/windows_task.ps1) | Windows任务入口：连接六个BAT入口与部署、桌面、串口和测试工具。 | 由01_setup.bat至06_test.bat调用。 |
| 18 | [build/build_app.ps1](../build/build_app.ps1) | 桌面应用编译：调用Windows .NET Framework C#编译器。 | 输出src/pc/b220_ore_app.exe。 |
| 19 | [build/make_badges.py](../build/make_badges.py) | 中文标牌生成：根据标本名称生成中文标牌图片。 | 需要Pillow和中文字体；运行所需52张标牌已随源码提供。 |
| 20 | [tools/collect_logs.py](../tools/collect_logs.py) | HTTP日志采集：采集状态并生成带电脑时间戳的CSV和JSONL。 | 电脑运行；--url指定板端地址。 |
| 21 | [tools/serial_log.py](../tools/serial_log.py) | 串口日志采集：保存串口原始数据。 | 电脑运行；--port指定实际COM口，依赖pyserial。 |

`src/ps/badges/` 共52张运行标牌：42项标本名称、九色兼容标签和未知标签。文件索引不将它们拆成单文件RAR，完整资源包含在完整包中。

运行相机识别使用 `app_ps.py`，其他算法由它间接调用；无需逐个启动算法文件。
