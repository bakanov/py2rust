"""Native build commands record actual invocations and produce independently predictable artifacts."""

import shutil
import subprocess
from pathlib import Path

SOURCE = r"""
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
static void put(int fd,const void *data,size_t size) {
    const char *p=data;
    while(size){ssize_t n=write(fd,p,size);if(n<0&&errno==EINTR)continue;if(n<=0)_exit(110);p+=n;size-=(size_t)n;}
}
static void record(const char *file,const char *text) {
    int fd=open(file,O_WRONLY|O_CREAT|O_APPEND,0600);if(fd<0)_exit(111);
    put(fd,text,strlen(text));put(fd,"\n",1);close(fd);
}
int main(int argc,char **argv) {
    if(argc<6)return 112;
    const char *id=argv[1],*mode=argv[2],*log=argv[3],*out=argv[4],*prefix=argv[5];
    record(log,id);
    if(!strcmp(mode,"hold")) {
        char path[4096],number[64];snprintf(path,sizeof(path),"%s.pids",log);
        snprintf(number,sizeof(number),"%ld",(long)getpid());record(path,number);
        pid_t child=fork();if(child<0)return 113;
        if(!child){signal(SIGTERM,SIG_IGN);for(;;)pause();}
        snprintf(number,sizeof(number),"%ld",(long)child);record(path,number);
        put(1,"waiting",7);signal(SIGTERM,SIG_IGN);for(;;)pause();
    }
    if(!strcmp(mode,"missing"))return 0;
    if(!strcmp(mode,"directory"))return mkdir(out,0700)?114:0;
    if(!strcmp(mode,"symlink"))return argc<7||symlink(argv[6],out)?115:0;
    if(!strcmp(mode,"hardlink"))return argc<7||link(argv[6],out)?116:0;
    int fd=open(out,O_WRONLY|O_CREAT|O_EXCL,0644);if(fd<0)return 117;if(fchmod(fd,0644))return 120;
    if(!strcmp(mode,"fail")){put(fd,"partial",7);close(fd);return 7;}
    if(!strcmp(mode,"oversized")) {
        char block[4096];memset(block,'x',sizeof(block));
        for(int i=0;i<1024;++i)put(fd,block,sizeof(block));put(fd,"x",1);close(fd);return 0;
    }
    if(strcmp(mode,"plain")) {
        const char *mark=getenv("MARK");if(!mark)mark="";
        put(fd,"[",1);put(fd,id,strlen(id));put(fd,"|",1);put(fd,prefix,strlen(prefix));
        put(fd,"|",1);put(fd,mark,strlen(mark));put(fd,"]",1);
    }
    for(int i=6;i<argc;++i) {
        int input=open(argv[i],O_RDONLY);if(input<0)return 118;
        char buffer[65536];for(;;){ssize_t n=read(input,buffer,sizeof(buffer));
            if(n<0&&errno==EINTR)continue;if(n<0)return 119;if(!n)break;put(fd,buffer,(size_t)n);}
        close(input);
    }
    close(fd);
    if(!strcmp(mode,"flood")){char b[4096];memset(b,'z',sizeof(b));for(int i=0;i<32;++i)put(1,b,sizeof(b));}
    if(!strcmp(mode,"signal"))raise(SIGTERM);
    return 0;
}
"""


def build_fixture(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "build-fixture.c"
    binary = directory / "build-fixture"
    source.write_text(SOURCE)
    compiler = shutil.which("cc")
    assert compiler is not None, "native build checks require a C compiler"
    result = subprocess.run(
        [
            compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-misleading-indentation",
            "-O2",
            str(source),
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return binary.resolve()
