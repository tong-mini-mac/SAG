import time
import os
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .Refinery import DataRefinery
from .Utils import CONFIG, NotificationManager
import signal


def _pid_alive(pid):
    """True if pid is a running process. os.kill(pid, 0) is unreliable on Windows (WinError 11)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except OSError:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True

class RawDataHandler(FileSystemEventHandler):
    def __init__(self, refinery, department="General"):
        self.refinery = refinery
        self.department = department

    def on_created(self, event):
        if not event.is_directory:
            file_path = event.src_path
            # Avoid processing hidden files or temp files
            if os.path.basename(file_path).startswith("."):
                return
            
            print(f"🔔 Auto-Refinery: New file detected: {file_path}")
            # Wait a moment for file to be fully written (e.g., Google Drive sync)
            time.sleep(2) 
            self.refinery.process_file(file_path, self.department)

class BackgroundMonitor:
    def __init__(self, watch_path=None, department="General"):
        self.watch_path = watch_path or CONFIG["RAW_DATA_PATH"]
        self.department = department
        self.refinery = DataRefinery()
        self.observer = Observer()
        self.pid_file = os.path.join(os.path.dirname(__file__), "..", ".monitor.pid")
        self.notifier = NotificationManager()

    def cleanup_old_processes(self):
        """Zombie Cleanup: Kill any existing monitor process based on .pid file."""
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, "r") as f:
                    old_pid = int(f.read().strip())
                
                # Check if process is still running and NOT the current process
                if old_pid == os.getpid():
                    return

                if _pid_alive(old_pid):
                    print(f"🧹 Zombie Cleanup: Killing existing Monitor (PID {old_pid})")
                    try:
                        os.kill(old_pid, signal.SIGTERM)
                    except OSError:
                        pass
                    time.sleep(1)  # Allow time for cleanup
            except (ProcessLookupError, ValueError):
                pass  # Stale pid file or invalid content
            finally:
                if os.path.exists(self.pid_file):
                    os.remove(self.pid_file)

    def write_pid(self):
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

    def start(self):
        self.cleanup_old_processes()
        self.write_pid()
        
        event_handler = RawDataHandler(self.refinery, self.department)
        self.observer.schedule(event_handler, self.watch_path, recursive=False)
        self.observer.start()
        
        start_msg = f"👀 Monitor started on: {self.watch_path} (PID: {os.getpid()})"
        print(start_msg)
        self.notifier.send_line(f"🚀 SAG Monitor Active\n{start_msg}")

    def stop(self):
        self.observer.stop()
        self.observer.join()
        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)
        self.notifier.send_line("🛑 SAG Monitor Stopped.")
