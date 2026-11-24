"""Independent native services record actual launch/exit times and process IDs."""

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
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stopped=0;
static void term(int number){(void)number;stopped=1;}
static void output(int fd,const void *buffer,size_t size){
 const unsigned char *p=buffer;
 while(size){ssize_t n=write(fd,p,size);if(n<0&&errno==EINTR)continue;if(n<=0)_exit(120);p+=n;size-=(size_t)n;}
}
static void line(const char *path,const char *text){
 int fd=open(path,O_WRONLY|O_CREAT|O_APPEND,0600);if(fd<0)_exit(121);output(fd,text,strlen(text));close(fd);
}
static long long clock_ns(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))_exit(122);return (long long)t.tv_sec*1000000000LL+t.tv_nsec;}
static void event(const char *path,const char *kind,int attempt,int code){
 char row[160];snprintf(row,sizeof(row),"%s %ld %d %lld %d\n",kind,(long)getpid(),attempt,clock_ns(),code);line(path,row);
}
static void pid(const char *path,pid_t value){char row[64];snprintf(row,sizeof(row),"%ld\n",(long)value);line(path,row);}
static void emit(size_t out,size_t err,int attempt){
 unsigned char block[4096];
 while(out||err){size_t n=out<sizeof(block)?out:sizeof(block);memset(block,attempt%256,n);output(1,block,n);out-=n;
 n=err<sizeof(block)?err:sizeof(block);memset(block,'e',n);output(2,block,n);err-=n;}
}
int main(int argc,char **argv){
 if(argc<8)return 119;
 const char *mode=argv[1],*log=argv[2];int attempt=1;
 FILE *counter=fopen(argv[3],"r");if(counter){if(fscanf(counter,"%d",&attempt)!=1)return 118;fclose(counter);++attempt;}
 counter=fopen(argv[3],"w");if(!counter)return 117;fprintf(counter,"%d\n",attempt);fclose(counter);
 event(log,"start",attempt,0);
 if(!strcmp(mode,"copy")){
  if(argc<9)return 115;
  int input=open(argv[8],O_RDONLY);if(input<0)return 114;
  unsigned char buffer[4096];
  for(;;){ssize_t n=read(input,buffer,sizeof(buffer));if(n<0&&errno==EINTR)continue;if(n<0)return 113;if(!n)break;output(1,buffer,(size_t)n);}
  close(input);event(log,"end",attempt,0);return 0;
 }
 size_t out=strtoul(argv[4],NULL,10),err=strtoul(argv[5],NULL,10);long delay=strtol(argv[6],NULL,10);int failures=atoi(argv[7]);
 if(!strcmp(mode,"term"))signal(SIGTERM,term);
 if(!strcmp(mode,"hold")||!strcmp(mode,"flood")||!strcmp(mode,"orphan")||!strcmp(mode,"closed")){
  char path[4096];snprintf(path,sizeof(path),"%s.pids",log);pid(path,getpid());
  pid_t child=fork();if(child<0)return 116;
  if(!child){signal(SIGTERM,SIG_IGN);for(;;)pause();}
  pid(path,child);signal(SIGTERM,SIG_IGN);
 }
 if(!strcmp(mode,"closed")){close(0);close(1);close(2);for(;;)pause();}
 emit(out,err,attempt);
 if(!strcmp(mode,"orphan")){event(log,"end",attempt,0);return 0;}
 if(!strcmp(mode,"flood")){for(;;)emit(4096,4096,attempt);}
 if(!strcmp(mode,"hold")){for(;;)pause();}
 if(!strcmp(mode,"term")){while(!stopped)pause();event(log,"end",attempt,0);return 0;}
 struct timespec wait={delay/1000,(delay%1000)*1000000};
 while(nanosleep(&wait,&wait)&&errno==EINTR){}
 int code=attempt<=failures?7:0;
 event(log,"end",attempt,code);return code;
}
"""


def build_fixture(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "supervisor-fixture.c"
    binary = directory / "supervisor-fixture"
    source.write_text(SOURCE)
    compiler = shutil.which("cc")
    assert compiler is not None
    result = subprocess.run(
        [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", str(source), "-o", str(binary)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return binary.resolve()
