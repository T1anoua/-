# 上传到 GitHub

## 网页上传源码

1. 登录 GitHub，新建仓库，例如 `b220-ore-vision`。
2. 打开仓库，选择 **Add file → Upload files**。
3. 从本地 `b220-ore-vision` 文件夹中选取源码文件和子文件夹上传，保留目录结构。文件较多时可分批上传。
4. 填写提交说明，例如“整理矿石多目标检测源码与部署步骤”，点击 **Commit changes**。
5. 返回仓库首页，确认 README、`src/ps/app_ps.py` 和 `src/ps/badges/` 可以浏览。

应上传文件夹中的内容，README.md 位于仓库根目录。GitHub 不会自动解压 RAR；源码直接上传后才能在线浏览、比较修改和下载完整项目。

## 上传 RAR 下载包

在仓库的 **Releases → Draft a new release** 中填写版本号及说明，将完整 RAR 和所需的单文件 RAR 拖入附件区，检查后发布。也可以将单个 RAR 作为普通文件上传，但仓库页面只能下载，不能直接查看里面的代码。

单文件 RAR 都保留了原文件的相对路径，附有简短说明。它们用于按文件下载或覆盖到完整项目中，不代表每个文件可以独立运行。

## 使用 Git

安装 Git 后，在本地 `b220-ore-vision` 文件夹打开 PowerShell，执行以下命令。将远程地址替换成实际仓库地址：

```powershell
git init
git add .
git commit -m "Add B220 ore vision source"
git branch -M main
git remote add origin https://github.com/ACCOUNT/b220-ore-vision.git
git push -u origin main
```

`.gitignore` 已排除虚拟环境、运行缓存、SSH 本地连接记录、测试输出和新采集日志。板卡密码和 GitHub 令牌不写入配置或源码。
