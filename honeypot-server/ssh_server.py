# server.py
import socket, sys, threading, json
import paramiko
from datetime import datetime
from fake_fs import handle_builtin
from llm import LLM
import uuid

HOST_KEY = paramiko.RSAKey(filename='server.key')
SSH_PORT = 2222

LOG_LOCK = threading.Lock()

# ------------------------------------------------
# Async JSON log writer
# ------------------------------------------------
def async_log(logfile, log_dict):
    def _write():
        line = json.dumps(log_dict) + "\n"
        with LOG_LOCK:
            with open(logfile, "a") as f:
                f.write(line)
    threading.Thread(target=_write, daemon=True).start()


# ------------------------------------------------
# SSH Session Handler
# ------------------------------------------------
class SSHServerHandler(paramiko.ServerInterface):
    def __init__(self, model):
        self.event = threading.Event()
        self.llm = model
        self.cwd = "/home/user"
        self.history = []
        self.session_id = str(uuid.uuid4())[:8]   # short readable session
        self.ip = None


    def get_allowed_auths(self, username): 
        return "password"

    def check_auth_password(self, user, pwd):
        with LOG_LOCK:
            with open("logs/auth.log", "a") as f:
                f.write(f"{user}:{pwd}\n")
        self.username = user
        return paramiko.AUTH_SUCCESSFUL

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def check_channel_shell_request(self, channel):
        self.channel = channel
        return True

    def check_channel_pty_request(self, *a):
        return True

    # ------------------------------------------------
    # Async profiling (NEVER shown to attacker)
    # ------------------------------------------------
    def async_profile(self, cmd, resp, logfile):
        def _run():
            profile_str = self.llm.profile(cmd)

            # Try to decode profile JSON
            try:
                profile = json.loads(profile_str)
            except:
                profile = {"raw": profile_str}

            record = {
                "ts": datetime.now().isoformat(),
                "session": self.session_id,
                "ip": self.ip,
                "cmd": cmd,
                "resp": resp,
                "profile": profile
            }

            async_log(logfile, record)

        threading.Thread(target=_run, daemon=True).start()



    # ------------------------------------------------
    # MAIN SHELL LOOP (clean + fast)
    # ------------------------------------------------
    def handle_shell(self):
        logfile = f"logs/log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

        while True:
            try:
                self.channel.sendall(f"{self.username}@honeypot:{self.cwd}$ ")

                raw = self.channel.recv(1024)
                if not raw:
                    continue

                cmd = raw.decode().strip()
                if not cmd:
                    continue

                # attempt builtin
                new_dir, out = handle_builtin(cmd, self.cwd)

                if out is not None:
                    self.cwd = new_dir
                    self.channel.sendall(out + "\n")

                    # ---- unified logging ----
                    self.async_profile(cmd, out, logfile)
                    continue

                # LLM fallback
                resp = self.llm.answer(cmd, self.history)
                self.history.extend([cmd, resp])

                self.channel.sendall(resp + "\n")

                # ---- unified logging ----
                self.async_profile(cmd, resp, logfile)

            except Exception as e:
                print("Shell closed:", e)
                break

        self.channel.close()
        self.event.set()

# ------------------------------------------------
# Start Server
# ------------------------------------------------
def start_ssh_server():
    model = LLM()

    server_socket = socket.socket()
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('', SSH_PORT))
    server_socket.listen(100)

    print(f"SSH Honeypot running on port {SSH_PORT}...")

    while True:
        client, addr = server_socket.accept()
        print("Connection:", addr)
        threading.Thread(
            target=handle_client,
            args=(client, model),
            daemon=True
        ).start()


def handle_client(client, model):
    transport = paramiko.Transport(client)
    transport.add_server_key(HOST_KEY)
    handler = SSHServerHandler(model)
    handler.ip = client.getpeername()[0]

    transport.start_server(server=handler)
    chan = transport.accept()
    if chan:
        handler.channel = chan
        handler.handle_shell()
