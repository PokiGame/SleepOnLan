using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Windows.Forms;

namespace SleepOnLan
{
    static class Program
    {
        private static bool shouldExit = false;
        private static NotifyIcon notifyIcon;
        private static ManualResetEvent exitEvent = new ManualResetEvent(false);
        private static int PORT;
        private const string CONFIG_FILE = "config.cfg";
        private const int DEFAULT_PORT = 9;

        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            // Зчитування порту з конфігураційного файлу
            if (!LoadConfig())
            {
                MessageBox.Show("Помилка читання конфігураційного файлу!", "Помилка", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            // Підготовка іконки у треї
            notifyIcon = new NotifyIcon
            {
                Icon = System.Drawing.SystemIcons.Information,
                Visible = true
            };

            // Налаштування контекстного меню для трея
            ContextMenu menu = new ContextMenu();
            menu.MenuItems.Add("Exit", OnExit); // Додати пункт "Exit" до контекстного меню
            notifyIcon.ContextMenu = menu;

            // Початок прослуховування на порті для WOL пакетів
            Thread listenerThread = new Thread(WolListener);
            listenerThread.Start();

            // Головний цикл програми, очікування на закриття
            Application.Run();

            // Сигнал про завершення роботи
            shouldExit = true;
            exitEvent.Set();
            listenerThread.Join();

            // Завершення роботи програми
            notifyIcon.Dispose();
        }

        private static bool LoadConfig()
        {
            try
            {
                string configPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, CONFIG_FILE);
                if (!File.Exists(configPath))
                {
                    // Якщо файл не існує, створити його зі стандартним портом
                    File.WriteAllText(configPath, $"PORT={DEFAULT_PORT}");
                    PORT = DEFAULT_PORT;
                    return true;
                }

                string[] lines = File.ReadAllLines(configPath);
                foreach (string line in lines)
                {
                    if (line.StartsWith("PORT="))
                    {
                        string portStr = line.Substring(5).Trim();
                        if (int.TryParse(portStr, out int port))
                        {
                            PORT = port;
                            return true;
                        }
                        else
                        {
                            throw new FormatException("Неправильний формат порту в конфігураційному файлі.");
                        }
                    }
                }

                throw new Exception("Порт не знайдено в конфігураційному файлі.");
            }
            catch (Exception ex)
            {
                Console.WriteLine("Помилка при читанні конфігураційного файлу: " + ex.Message);
                return false;
            }
        }

        private static void WolListener()
        {
            UdpClient listener = null;
            try
            {
                listener = new UdpClient(PORT);
                while (!shouldExit)
                {
                    if (listener.Available > 0)
                    {
                        // Очікування на отримання даних
                        IPEndPoint anyIP = new IPEndPoint(IPAddress.Any, 0);
                        byte[] data = listener.Receive(ref anyIP);

                        // Перевірка на наявність WOL пакета (мінімальна перевірка, можна розширити)
                        if (data.Length >= 6 && data[0] == 0xFF && data[5] != 0)
                        {
                            // Вимкнення комп'ютера
                            System.Diagnostics.Process.Start("shutdown", "/s /t 0");
                            shouldExit = true; // вихід з програми після вимкнення комп'ютера
                        }
                    }
                    else
                    {
                        exitEvent.WaitOne(100); // Перевіряємо вихід кожні 100 мс
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error: " + ex.Message);
            }
            finally
            {
                listener?.Close();
            }
        }

        private static void OnExit(object sender, EventArgs e)
        {
            // Встановлюємо флаг для виходу з програми
            shouldExit = true;
            exitEvent.Set(); // Сигналізуємо потоку про завершення

            // Завершення роботи програми
            Application.Exit();
        }
    }
}
