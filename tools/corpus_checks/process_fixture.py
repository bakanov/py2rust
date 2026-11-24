"""Native subprocess fixtures used by checks, never linked into transpiled applications."""

import shutil
import subprocess
import time
from pathlib import Path

SOURCE = r"""
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

static void output(int fd, const void *buffer, size_t count) {
    const char *data = buffer;
    while (count) {
        ssize_t n = write(fd, data, count);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) _exit(120);
        data += n; count -= (size_t)n;
    }
}
static void record(const char *path, pid_t pid) {
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0600);
    if (fd < 0) _exit(121);
    char text[64]; int n = snprintf(text, sizeof(text), "%ld\n", (long)pid);
    output(fd, text, (size_t)n); close(fd);
}
int main(int argc, char **argv) {
    if (argc < 2) return 119;
    const char *mode = argv[1];
    if (!strcmp(mode,"args")) {
        const char *hex = "0123456789abcdef";
        for (int i=2; i<argc; ++i) {
            for (const unsigned char *p=(unsigned char *)argv[i]; *p; ++p) {
                char out[2] = {hex[*p >> 4],hex[*p & 15]}; output(1,out,2);
            }
            output(1,"\n",1);
        }
    } else if (!strcmp(mode,"copy") || !strcmp(mode,"upper") || !strcmp(mode,"take")) {
        size_t remaining = !strcmp(mode,"take") ? strtoul(argv[2],NULL,10) : (size_t)-1;
        unsigned char buffer[16384];
        while (remaining) {
            size_t want = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
            ssize_t count = read(0,buffer,want);
            if (count < 0 && errno == EINTR) continue;
            if (count < 0) return 122;
            if (!count) break;
            if (!strcmp(mode,"upper")) for (ssize_t i=0;i<count;++i) {
                if (buffer[i]>='a' && buffer[i]<='z') buffer[i]-=32;
            }
            output(1,buffer,(size_t)count); remaining-=(size_t)count;
        }
    } else if (!strcmp(mode,"emit")) {
        size_t stdout_left=strtoul(argv[2],NULL,10), stderr_left=strtoul(argv[3],NULL,10), position=0;
        unsigned char buffer[4096];
        while (stdout_left || stderr_left) {
            size_t count=stdout_left<sizeof(buffer)?stdout_left:sizeof(buffer);
            for (size_t i=0;i<count;++i) buffer[i]=(unsigned char)((position+i)%256);
            output(1,buffer,count);stdout_left-=count;position+=count;
            count=stderr_left<sizeof(buffer)?stderr_left:sizeof(buffer);
            memset(buffer,'e',count);output(2,buffer,count);stderr_left-=count;
        }
        return argc>4?atoi(argv[4]):0;
    } else if (!strcmp(mode,"exit")) {
        return atoi(argv[2]);
    } else if (!strcmp(mode,"signal")) {
        raise(atoi(argv[2]));return 123;
    } else if (!strcmp(mode,"env")) {
        const char *value=getenv(argv[2]);if(!value)value="<unset>";output(1,value,strlen(value));
    } else if (!strcmp(mode,"cwd")) {
        char value[4096];if(!getcwd(value,sizeof(value)))return 124;output(1,value,strlen(value));
    } else if (!strcmp(mode,"hold") || !strcmp(mode,"orphan")) {
        record(argv[2],getpid());
        pid_t child=fork();if(child<0)return 125;
        if(!child){signal(SIGTERM,SIG_IGN);for(;;)pause();}
        record(argv[2],child);
        if(!strcmp(mode,"orphan"))return 0;
        signal(SIGTERM,SIG_IGN);for(;;)pause();
    } else if (!strcmp(mode,"record")) {
        record(argv[2],getpid());
    } else if (!strcmp(mode,"ignore-chld")) {
        signal(SIGCHLD,SIG_IGN);execv(argv[2],argv+2);return 126;
    } else return 118;
    return 0;
}
"""


def build_fixture(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "process-fixture.c"
    binary = directory / "process-fixture"
    source.write_text(SOURCE)
    compiler = shutil.which("cc")
    assert compiler is not None, "the process checks require a C compiler for native child fixtures"
    result = subprocess.run(
        [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", str(source), "-o", str(binary)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return binary.resolve()


def alive(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        return state not in ["Z", "X"]
    except FileNotFoundError:
        return False


def gone(path: Path, minimum: int = 0) -> None:
    pids = [int(line) for line in path.read_text().splitlines()] if path.exists() else []
    assert len(pids) >= minimum, (path, pids)
    until = time.monotonic() + 2
    while any(alive(pid) for pid in pids) and time.monotonic() < until:
        time.sleep(0.01)
    assert not any(alive(pid) for pid in pids), pids
    return  # noqa: PLR1711 - explicit repository returns


def ready(path: Path, process: subprocess.Popen, lines: int = 2) -> None:
    until = time.monotonic() + 5
    while time.monotonic() < until:
        assert process.poll() is None, process.communicate()
        if path.exists() and len(path.read_text().splitlines()) >= lines:
            return
        time.sleep(0.005)
    raise AssertionError("process fixture did not become ready")
