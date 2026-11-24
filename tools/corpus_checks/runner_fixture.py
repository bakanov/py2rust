"""Native child fixtures with visible partial output and inherited process-group descendants."""

import shutil
import subprocess
from pathlib import Path

from .process_fixture import SOURCE as BASE_SOURCE

SOURCE = BASE_SOURCE.replace(
    '} else if (!strcmp(mode,"hold") || !strcmp(mode,"orphan")) {',
    """} else if (!strcmp(mode,"hold") || !strcmp(mode,"orphan") || !strcmp(mode,"prefix-hold")
               || !strcmp(mode,"closed-hold") || !strcmp(mode,"flood-hold")) {
        if(!strcmp(mode,"prefix-hold")) {
            const unsigned char prefix[]={'r','e','a','d','y',0,255};
            output(1,prefix,sizeof(prefix));output(2,"waiting",7);
        }
        if(!strcmp(mode,"closed-hold")) {close(0);close(1);close(2);}""",
).replace(
    'if(!strcmp(mode,"orphan"))return 0;',
    """if(!strcmp(mode,"orphan"))return 0;
        if(!strcmp(mode,"flood-hold")) {
            unsigned char block[4096];memset(block,'x',sizeof(block));
            for(int i=0;i<256;++i)output(1,block,sizeof(block));
        }""",
)


def build_runner_fixture(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "runner-fixture.c"
    binary = directory / "runner-fixture"
    source.write_text(SOURCE)
    compiler = shutil.which("cc")
    assert compiler is not None, "native child checks require a C compiler"
    result = subprocess.run(
        [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", str(source), "-o", str(binary)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return binary.resolve()
