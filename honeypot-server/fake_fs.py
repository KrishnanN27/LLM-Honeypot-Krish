# fake_fs.py

FAKE_FS = {
    "/": ["home", "etc", "var", "bin", "usr"],
    "/home": ["user"],
    "/home/user": ["Desktop", "Downloads", "Documents"],
    "/etc": ["passwd", "shadow", "hosts", "os-release"],
    "/var": ["log"],
    "/var/log": ["auth.log", "syslog"],
}

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

    # sudo -l
    if parts[0] == "sudo" and len(parts) > 1 and parts[1] == "-l":
        return cwd, (
            "Matching Defaults entries for root on localhost:\n"
            "    env_reset, mail_badpass,\n"
            "    secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n\n"
            "User root may run the following commands on localhost:\n"
            "    (ALL) NOPASSWD: /usr/bin/vim\n"
        )

    # ps
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
        target = "/home/user" if len(parts) == 1 else resolve_path(cwd, parts[1])
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
