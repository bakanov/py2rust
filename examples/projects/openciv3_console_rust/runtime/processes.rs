//! Foreground Linux pipelines. Parsing, command lookup and shell policy stay in Python.
use crate::Result;
use indexmap::IndexMap;

type PipelineResult = (Vec<i64>, Vec<u8>, Vec<Vec<u8>>);

#[derive(Debug)]
struct ExecutionFailure {
    kind: &'static str,
    message: String,
    interrupt_signal: i64,
    stdout: Vec<u8>,
    stderr: Vec<Vec<u8>>,
}

impl ExecutionFailure {
    fn new(kind: &'static str, message: String, interrupt_signal: i64) -> Self {
        Self {
            kind,
            message,
            interrupt_signal,
            stdout: Vec::new(),
            stderr: Vec::new(),
        }
    }
}

impl std::fmt::Display for ExecutionFailure {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.message)
    }
}

impl std::error::Error for ExecutionFailure {}

#[cfg(target_os = "linux")]
pub(crate) mod linux {
    use super::*;
    use std::io::{self, Read, Write};
    use std::os::fd::{AsRawFd, OwnedFd, RawFd};
    use std::os::unix::process::CommandExt;
    use std::path::Path;
    use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
    use std::sync::atomic::{AtomicBool, AtomicI32, Ordering};
    use std::time::{Duration, Instant};

    pub(crate) static INTERRUPTED: AtomicI32 = AtomicI32::new(0);
    static ACTIVE: AtomicBool = AtomicBool::new(false);

    extern "C" fn interrupt(signal: libc::c_int) {
        let _ = INTERRUPTED.compare_exchange(0, signal, Ordering::Relaxed, Ordering::Relaxed);
    }

    pub(crate) struct Signals {
        saved: Vec<(libc::c_int, libc::sigaction)>,
    }
    impl Signals {
        pub(crate) fn install() -> Result<Self> {
            // Only the main thread may temporarily own these process-wide dispositions.
            if unsafe { libc::syscall(libc::SYS_gettid) } != i64::from(std::process::id()) {
                return Err("pipeline requires the main thread".into());
            }
            let mut child_action: libc::sigaction = unsafe { std::mem::zeroed() };
            if unsafe { libc::sigaction(libc::SIGCHLD, std::ptr::null(), &mut child_action) } != 0
                || child_action.sa_sigaction != libc::SIG_DFL
                || child_action.sa_flags & libc::SA_NOCLDWAIT != 0
            {
                return Err("pipeline requires the default SIGCHLD disposition".into());
            }
            if ACTIVE
                .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
                .is_err()
            {
                return Err("process signal ownership is already active".into());
            }
            let mut signals = Self { saved: Vec::new() };
            INTERRUPTED.store(0, Ordering::Relaxed);
            for signal in [libc::SIGINT, libc::SIGTERM] {
                let mut action: libc::sigaction = unsafe { std::mem::zeroed() };
                let mut old: libc::sigaction = unsafe { std::mem::zeroed() };
                action.sa_sigaction = interrupt as usize;
                // No allocation or locks occur in the signal handler.
                unsafe { libc::sigemptyset(&mut action.sa_mask) };
                if unsafe { libc::sigaction(signal, &action, &mut old) } != 0 {
                    return Err("pipeline signal setup failed".into());
                }
                signals.saved.push((signal, old));
            }
            Ok(signals)
        }
    }
    impl Drop for Signals {
        fn drop(&mut self) {
            for (signal, action) in self.saved.iter().rev() {
                unsafe { libc::sigaction(*signal, action, std::ptr::null_mut()) };
            }
            ACTIVE.store(false, Ordering::SeqCst);
        }
    }

    #[derive(Default)]
    struct Children(Vec<Child>);
    impl Children {
        fn kill_groups(&self) {
            for child in &self.0 {
                // Leaders are not reaped until after group cleanup, so their IDs remain owned.
                unsafe { libc::kill(-(child.id() as i32), libc::SIGKILL) };
            }
        }
    }
    impl Drop for Children {
        fn drop(&mut self) {
            self.kill_groups();
            for child in &mut self.0 {
                loop {
                    match child.wait() {
                        Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
                        _ => break,
                    }
                }
            }
        }
    }

    pub(crate) fn nonblocking(fd: RawFd) -> Result<()> {
        // These descriptors are live, owned pipe ends; fcntl preserves existing flags.
        let flags = unsafe { libc::fcntl(fd, libc::F_GETFL) };
        if flags < 0 || unsafe { libc::fcntl(fd, libc::F_SETFL, flags | libc::O_NONBLOCK) } < 0 {
            return Err("pipeline I/O setup failed".into());
        }
        Ok(())
    }

    pub(crate) fn peek(child: &Child) -> Result<Option<i64>> {
        let mut status: libc::siginfo_t = unsafe { std::mem::zeroed() };
        let result = unsafe {
            libc::waitid(
                libc::P_PID,
                child.id(),
                &mut status,
                libc::WEXITED | libc::WNOHANG | libc::WNOWAIT,
            )
        };
        if result != 0 {
            if io::Error::last_os_error().kind() == io::ErrorKind::Interrupted {
                return Ok(None);
            }
            return Err("pipeline child status unavailable".into());
        }
        if unsafe { status.si_pid() } == 0 {
            return Ok(None);
        }
        let code = i64::from(unsafe { status.si_status() });
        Ok(Some(if status.si_code == libc::CLD_EXITED {
            code
        } else {
            -code
        }))
    }

    pub(crate) fn validate(
        commands: &[Vec<String>],
        environments: &[IndexMap<String, String>],
        cwd: &str,
        input: &[u8],
        timeout_ms: i64,
        max_output: i64,
    ) -> Result<()> {
        if !(1..=8).contains(&commands.len()) {
            return Err("pipeline requires 1..8 stages".into());
        }
        if environments.len() != commands.len() {
            return Err("pipeline environment count mismatch".into());
        }
        if !(1..=60000).contains(&timeout_ms) || !(0..=16777216).contains(&max_output) {
            return Err("pipeline timeout/output bounds invalid".into());
        }
        if input.len() > 16777216 {
            return Err("pipeline input exceeds 16 MiB".into());
        }
        if cwd.len() > 4096
            || cwd.contains('\0')
            || !Path::new(cwd).is_absolute()
            || !Path::new(cwd).is_dir()
        {
            return Err("pipeline cwd must be an absolute directory".into());
        }
        for (arguments, environment) in commands.iter().zip(environments) {
            if !(1..=128).contains(&arguments.len())
                || arguments.iter().any(|value| value.contains('\0'))
                || arguments.iter().map(|value| value.len() + 1).sum::<usize>() > 65536
                || !Path::new(&arguments[0]).is_absolute()
            {
                return Err("pipeline argv requires an absolute executable and 1..128 NUL-free arguments within 64 KiB".into());
            }
            if environment.len() > 256
                || environment.iter().any(|(key, value)| {
                    key.is_empty()
                        || key.len() > 128
                        || !key.bytes().enumerate().all(|(i, b)| {
                            b == b'_' || b.is_ascii_alphabetic() || (i > 0 && b.is_ascii_digit())
                        })
                        || value.contains('\0')
                })
                || environment
                    .iter()
                    .map(|(key, value)| key.len() + value.len() + 2)
                    .sum::<usize>()
                    > 65536
            {
                return Err("pipeline environment requires at most 256 ASCII names and NUL-free values within 64 KiB".into());
            }
        }
        Ok(())
    }

    fn cancellation(deadline: Instant) -> Result<()> {
        let signal = INTERRUPTED.load(Ordering::Relaxed);
        if signal != 0 {
            return Err(ExecutionFailure::new(
                "interrupted",
                format!("pipeline interrupted by signal {signal}"),
                i64::from(signal),
            )
            .into());
        }
        if Instant::now() >= deadline {
            return Err(
                ExecutionFailure::new("timeout", "pipeline deadline exceeded".into(), 0).into(),
            );
        }
        Ok(())
    }

    pub(super) fn run(
        commands: &[Vec<String>],
        environments: &[IndexMap<String, String>],
        cwd: &str,
        input: &[u8],
        timeout_ms: i64,
        max_output: i64,
    ) -> Result<PipelineResult> {
        validate(commands, environments, cwd, input, timeout_ms, max_output)?;
        let _signals = Signals::install()?;
        let deadline = Instant::now() + Duration::from_millis(timeout_ms as u64);
        let mut captured: Vec<Vec<u8>> = (0..=commands.len()).map(|_| Vec::new()).collect();
        let result: Result<PipelineResult> = (|| {
            let mut children = Children::default();
            let mut incoming: Option<ChildStdout> = None;
            let mut writer: Option<ChildStdin> = None;
            // Reader zero is final stdout; readers 1.. are each stage's stderr.
            let mut readers: Vec<Option<std::fs::File>> =
                (0..=commands.len()).map(|_| None).collect();
            for (index, (arguments, environment)) in commands.iter().zip(environments).enumerate() {
                cancellation(deadline)?;
                let mut command = Command::new(&arguments[0]);
                command
                    .args(&arguments[1..])
                    .env_clear()
                    .envs(environment)
                    .current_dir(cwd)
                    .stdin(
                        incoming
                            .take()
                            .map(Stdio::from)
                            .unwrap_or_else(Stdio::piped),
                    )
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .process_group(0);
                let child = command.spawn().map_err(|_| {
                    ExecutionFailure::new(
                        "spawn_error",
                        format!("pipeline spawn failed at stage {index}"),
                        0,
                    )
                })?;
                children.0.push(child);
                let child = children.0.last_mut().unwrap();
                if index == 0 {
                    writer = child.stdin.take();
                }
                readers[index + 1] = Some(std::fs::File::from(OwnedFd::from(
                    child.stderr.take().unwrap(),
                )));
                incoming = child.stdout.take();
            }
            readers[0] = Some(std::fs::File::from(OwnedFd::from(incoming.take().unwrap())));
            for reader in readers.iter().flatten() {
                nonblocking(reader.as_raw_fd())?;
            }
            nonblocking(writer.as_ref().unwrap().as_raw_fd())?;
            if input.is_empty() {
                writer = None;
            }
            let mut position = 0;
            let mut total = 0;
            let mut statuses: Vec<Option<i64>> = vec![None; commands.len()];
            let mut groups_killed = false;
            loop {
                cancellation(deadline)?;
                for (index, child) in children.0.iter().enumerate() {
                    if statuses[index].is_none() {
                        statuses[index] = peek(child)?;
                    }
                }
                if statuses.iter().all(Option::is_some) {
                    if !groups_killed {
                        children.kill_groups();
                        groups_killed = true;
                        writer = None;
                    }
                    if readers.iter().all(Option::is_none) {
                        break;
                    }
                }
                let mut polling: Vec<libc::pollfd> = readers
                    .iter()
                    .map(|reader| libc::pollfd {
                        fd: reader.as_ref().map(AsRawFd::as_raw_fd).unwrap_or(-1),
                        events: libc::POLLIN,
                        revents: 0,
                    })
                    .collect();
                polling.push(libc::pollfd {
                    fd: writer.as_ref().map(AsRawFd::as_raw_fd).unwrap_or(-1),
                    events: libc::POLLOUT,
                    revents: 0,
                });
                let remaining = deadline
                    .saturating_duration_since(Instant::now())
                    .as_millis()
                    .min(10) as i32;
                let ready = unsafe {
                    libc::poll(
                        polling.as_mut_ptr(),
                        polling.len() as libc::nfds_t,
                        remaining,
                    )
                };
                if ready < 0 {
                    if io::Error::last_os_error().kind() == io::ErrorKind::Interrupted {
                        continue;
                    }
                    return Err("pipeline I/O polling failed".into());
                }
                for index in 0..readers.len() {
                    if polling[index].revents == 0 || readers[index].is_none() {
                        continue;
                    }
                    let mut buffer = [0u8; 65536];
                    let wanted = buffer.len().min(max_output as usize - total + 1);
                    match readers[index].as_mut().unwrap().read(&mut buffer[..wanted]) {
                        Ok(0) => readers[index] = None,
                        Ok(count) => {
                            let keep = count.min(max_output as usize - total);
                            captured[index].extend_from_slice(&buffer[..keep]);
                            total += count;
                            if total > max_output as usize {
                                return Err(ExecutionFailure::new(
                                    "output_limit",
                                    "pipeline output limit exceeded".into(),
                                    0,
                                )
                                .into());
                            }
                        }
                        Err(error)
                            if matches!(
                                error.kind(),
                                io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                            ) => {}
                        Err(_) => return Err("pipeline output read failed".into()),
                    }
                }
                if polling.last().unwrap().revents != 0 {
                    if let Some(stream) = writer.as_mut() {
                        let end = input.len().min(position + 65536);
                        match stream.write(&input[position..end]) {
                            Ok(count) => {
                                position += count;
                                if position == input.len() || count == 0 {
                                    writer = None;
                                }
                            }
                            Err(error) if error.kind() == io::ErrorKind::BrokenPipe => {
                                writer = None
                            }
                            Err(error)
                                if matches!(
                                    error.kind(),
                                    io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                                ) => {}
                            Err(_) => return Err("pipeline input write failed".into()),
                        }
                    }
                }
            }
            let stdout = captured.remove(0);
            Ok((
                statuses.into_iter().map(Option::unwrap).collect(),
                stdout,
                std::mem::take(&mut captured),
            ))
            // Pipes close, groups are killed and direct children reaped before handlers restore.
        })();
        match result {
            Ok(value) => Ok(value),
            Err(error) => match error.downcast::<ExecutionFailure>() {
                Ok(mut failure) => {
                    failure.stdout = captured.remove(0);
                    failure.stderr = captured;
                    Err(failure)
                }
                Err(error) => Err(error),
            },
        }
    }
}

pub fn process_pipeline(
    commands: &[Vec<String>],
    environments: &[IndexMap<String, String>],
    cwd: &str,
    input: &[u8],
    timeout_ms: i64,
    max_output: i64,
) -> Result<PipelineResult> {
    #[cfg(target_os = "linux")]
    {
        linux::run(commands, environments, cwd, input, timeout_ms, max_output)
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = (commands, environments, cwd, input, timeout_ms, max_output);
        Err("pipeline currently requires Linux".into())
    }
}

/// One direct-argv command with bounded captured prefixes on expected execution failures.
pub fn process_run(
    arguments: &[String],
    environment: &IndexMap<String, String>,
    cwd: &str,
    input: &[u8],
    timeout_ms: i64,
    max_output: i64,
) -> Result<(crate::Json, Vec<u8>, Vec<u8>)> {
    match process_pipeline(
        &[arguments.to_vec()],
        &[environment.clone()],
        cwd,
        input,
        timeout_ms,
        max_output,
    ) {
        Ok((codes, output, mut errors)) => Ok((
            serde_json::json!({"kind": "exited", "returncode": codes[0], "interrupt_signal": 0}),
            output,
            errors.remove(0),
        )),
        Err(error) => match error.downcast::<ExecutionFailure>() {
            Ok(mut failure) => Ok((
                serde_json::json!({"kind": failure.kind, "returncode": null, "interrupt_signal": failure.interrupt_signal}),
                failure.stdout,
                failure.stderr.remove(0),
            )),
            Err(error) => Err(error),
        },
    }
}
