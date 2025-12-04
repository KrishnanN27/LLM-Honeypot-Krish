import socket, sys, threading
import paramiko
from datetime import datetime

# ------------------------ Fake Filesystem ------------------------
FAKE_FS = {
    "/": ["home", "etc", "var", "bin", "usr"],
    "/home": ["user"],
    "/home/user": ["Desktop", "Downloads", "Documents"],
    "/etc": ["passwd", "shadow", "hosts", "os-release"],
    "/var": ["log"],
    "/var/log": ["auth.log", "syslog"],
}

# Global working directory per-session (simple version)
CURRENT_DIR = "/home/user"
# -----------------------------------------------------------------

def resolve_path(cwd, path):
    if path.startswith("/"):
        return path
    if path == "..":
        parent = "/".join(cwd.rstrip("/").split("/")[:-1])
        return parent if parent else "/"
    if path == ".":
        return cwd
    if cwd == "/":
        return f"/{path}"
    return f"{cwd}/{path}"

def handle_builtin(cmd, cwd):
    parts = cmd.strip().split()

    if not parts:
        return cwd, ""

    # pwd
    if parts[0] == "pwd":
        return cwd, cwd
    
    if parts[0] == "ps":
        return cwd, (
            "USER   PID  %CPU %MEM VSZ   RSS TTY   STAT START   TIME COMMAND\n"
            "root     1   0.0  0.1  1712  532 ?     Ss   10:00   0:00 /sbin/init\n"
            "root   543   0.0  0.3  2148  789 ?     Ss   10:01   0:00 /usr/sbin/sshd\n"
            "user  1221   0.1  1.0  5123  2345 pts/0 S+   10:02   0:00 bash\n"
        )


    # ls
    if parts[0] == "ls":
        target = cwd if len(parts) == 1 else resolve_path(cwd, parts[1])
        if target in FAKE_FS:
            return cwd, "  ".join(FAKE_FS[target])
        return cwd, f"ls: cannot access '{target}': No such file or directory"

    # cd
    if parts[0] == "cd":
        target = cwd if len(parts) == 1 else resolve_path(cwd, parts[0])
        if len(parts) > 1:
            target = resolve_path(cwd, parts[1])
        else:
            target = "/home/user"
        if target in FAKE_FS:
            return target, ""
        return cwd, f"cd: no such file or directory: {target}"

    # cat
    if parts[0] == "cat":
        if len(parts) < 2:
            return cwd, "cat: missing filename"
        target = resolve_path(cwd, parts[1])

        if target == "/etc/passwd":
            return cwd, (
                "root:x:0:0:root:/root:/bin/bash\n"
                "user:x:1000:1000:User:/home/user:/bin/bash"
            )

        if target == "/etc/os-release":
            return cwd, (
                'NAME="Ubuntu"\n'
                'VERSION="22.04 LTS"\n'
                'PRETTY_NAME="Ubuntu 22.04.4 LTS"\n'
            )

        return cwd, f"cat: {target}: No such file"

    return cwd, None



# ------------------------- SSH Server Core -------------------------

# Generate keys with 'ssh-keygen -t rsa -f server.key'
HOST_KEY = paramiko.RSAKey(filename='server.key')
SSH_PORT = 2222

# Log the user:password combinations to files
LOGFILE = 'logs/auth.log'
LOGFILE_LOCK = threading.Lock()


class SSHServerHandler(paramiko.ServerInterface):
    def __init__(self, llm_model):
        self.event = threading.Event()
        self.llm_model = llm_model
        self.log_history = []
        self.cwd = "/home/user"   # Session working directory

    def check_channel_request(self, kind, channelID):
        return paramiko.OPEN_SUCCEEDED

    def check_channel_shell_request(self, channel):
        print("Channel", channel)
        self.channel = channel
        return True

    def check_channel_pty_request(self, c, t, w, h, p, ph, m):
        return True

    def get_allowed_auths(self, username):
        return 'password'

    def check_auth_password(self, username, password):
        self.username = username

        LOGFILE_LOCK.acquire()
        try:
            logfile_handle = open(LOGFILE, "a")
            print("New login: " + username + ":" + password)
            logfile_handle.write(username + ":" + password + "\n")
            logfile_handle.close()
        finally:
            LOGFILE_LOCK.release()

        return paramiko.AUTH_SUCCESSFUL

    def handle_shell(self):
        log_filename = f"logs/log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"

        while not self.channel.exit_status_ready():
            try:
                # Show real prompt with cwd
                self.channel.sendall(f'{self.username}@localhost:{self.cwd} $ ')
                command = self.channel.recv(1024).decode("utf-8").strip()

                if not command:
                    continue

                print("CMD:", command)

                # 1) Builtin command check
                new_dir, builtin_output = handle_builtin(command, self.cwd)

                if builtin_output is not None:
                    self.cwd = new_dir
                    self.channel.sendall(builtin_output + "\n")
                    continue

                # 2) Fall back to LLM for unknown commands
                response = self.llm_model.answer(command, self.log_history)

                # Save logs
                self.log_history.append(command)
                self.log_history.append(response)

                with open(log_filename, "a") as log_file:
                    log_file.write(f"@CMD: {command}\n@RESP: {response}\n\n")

                self.channel.sendall(f"{response}\n")

            except Exception as e:
                print("Channel closed:", e)
                self.channel.close()
                self.event.set()
                return

        self.channel.close()
        self.event.set()


def handleConnection(client, llm_model):
    transport = paramiko.Transport(client)
    transport.add_server_key(HOST_KEY)

    server_handler = SSHServerHandler(llm_model)
    transport.start_server(server=server_handler)

    channel = transport.accept()

    if channel is None:
        transport.close()
        return

    server_handler.channel = channel
    server_handler.handle_shell()


def start_ssh_server(llm_model):
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', SSH_PORT))
        server_socket.listen(100)
        print('Server started...')

        while True:
            try:
                client_socket, client_addr = server_socket.accept()
                print(f'New Connection: {client_addr}')
                threading.Thread(target=handleConnection, args=(client_socket, llm_model)).start()
            except Exception as e:
                print("ERROR: Client handling")
                print(e)

    except Exception as e:
        print("ERROR: Failed to create socket")
        print(e)
        sys.exit(1)
