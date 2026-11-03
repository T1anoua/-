using System;
using System.IO;
using System.Diagnostics;
using System.Windows.Forms;
using System.Reflection;
using System.Text;
using System.Net;
using System.Web.Script.Serialization;
using System.Collections.Generic;

[assembly: AssemblyTitle("B220 矿石识别")]
[assembly: AssemblyDescription("可配置开发板地址的独立应用入口")]
[assembly: AssemblyVersion("3.1.0.0")]

internal static class OreAppLauncher
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            string exeDirectory = AppDomain.CurrentDomain.BaseDirectory;
            string configPath = Path.Combine(exeDirectory, "config.json");
            DirectoryInfo ancestor = Directory.GetParent(exeDirectory.TrimEnd(Path.DirectorySeparatorChar));
            while (!File.Exists(configPath) && ancestor != null)
            {
                configPath = Path.Combine(ancestor.FullName, "config.json");
                ancestor = ancestor.Parent;
            }
            if (!File.Exists(configPath)) throw new FileNotFoundException("缺少 config.json，请重新运行 03_install_desktop.bat。");
            var serializer = new JavaScriptSerializer();
            var config = serializer.Deserialize<Dictionary<string, object>>(File.ReadAllText(configPath, Encoding.UTF8));
            string host = Convert.ToString(config["host"]);
            int port = Convert.ToInt32(config["http_port"]);
            if (!System.Text.RegularExpressions.Regex.IsMatch(host, @"^[A-Za-z0-9][A-Za-z0-9.-]*$") || port < 1 || port > 65535)
                throw new ArgumentException("config.json 中的 host 或 http_port 无效。");
            string board = "http://" + host + ":" + port;
            string cacheDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "B220OreVision", "cache", host + "_" + port);
            Directory.CreateDirectory(cacheDirectory);
            string launcher = Path.Combine(cacheDirectory, "launcher.html");
            using (Stream resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("OreApp.StartPage"))
            {
                if (resource == null) throw new InvalidOperationException("启动页缺失，请重新构建应用。");
                using (StreamReader reader = new StreamReader(resource, Encoding.UTF8))
                {
                    string content = reader.ReadToEnd().Replace("@@BOARD_URL_JSON@@", serializer.Serialize(board)).Replace("@@BOARD_URL_HTML@@", WebUtility.HtmlEncode(board));
                    File.WriteAllText(launcher, content, new UTF8Encoding(false));
                }
            }
            // Allows reproducible resource/configuration checks without opening a window.
            if (Array.IndexOf(args, "--prepare-only") >= 0) return 0;
            string edge = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Microsoft", "Edge", "Application", "msedge.exe");
            if (!File.Exists(edge)) edge = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Microsoft", "Edge", "Application", "msedge.exe");
            if (!File.Exists(edge)) edge = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Microsoft", "Edge", "Application", "msedge.exe");
            if (!File.Exists(edge)) throw new FileNotFoundException("未找到 Microsoft Edge。请用浏览器打开 " + board + "/ 。");
            var info = new ProcessStartInfo(edge);
            info.Arguments = "--app=\"" + new Uri(launcher).AbsoluteUri + "\"";
            info.UseShellExecute = true;
            Process.Start(info);
            return 0;
        }
        catch (Exception error)
        {
            if (Array.IndexOf(args, "--prepare-only") < 0)
                MessageBox.Show(error.Message, "B220 矿石识别", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return 1;
        }
    }
}
