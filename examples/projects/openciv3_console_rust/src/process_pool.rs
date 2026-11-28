//! Nonblocking owned child groups. Scheduling, restarts and log policy belong to applications.
use crate::{Json, Result};
use indexmap::IndexMap;

#[cfg(target_os = "linux")]
mod linux {
    use super::*;
    use crate::processes::linux::{nonblocking, peek, validate, Signals, INTERRUPTED};
    use crate::resources::Resource;
    use std::collections::BTreeMap;
    use std::fs::File;
    use std::io::{self, Read};
    use std::os::fd::{AsRawFd, OwnedFd};
    use std::os::unix::process::CommandExt;
    use std::process::{Child, Command, Stdio};
    use std::sync::{atomic::Ordering, Arc, Mutex, MutexGuard};

    struct Entry {
        child: Child,
        output: Option<File>,
        error: Option<File>,
        code: Option<i64>,
    }
    impl Entry {
        fn signal(&self, number: i32) -> Result<()> {
            // waitid uses WNOWAIT; this leader remains owned until Entry::drop.
            if unsafe { libc::kill(-(self.child.id() as i32), number) } != 0 {
                let error = io::Error::last_os_error();
                if error.raw_os_error() != Some(libc::ESRCH) {
                    return Err(error.into());
                }
            }
            Ok(())
        }
    }
    impl Drop for Entry {
        fn drop(&mut self) {
            let _ = self.signal(libc::SIGKILL);
            self.output = None;
            self.error = None;
            loop {
                match self.child.wait() {
                    Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
                    _ => break,
                }
            }
        }
    }
    struct Pool {
        entries: BTreeMap<i64, Entry>,
        next_id: i64,
        _signals: Signals,
    }
    impl Drop for Pool {
        fn drop(&mut self) {
            // Cancel every group before reaping any leader. Handlers restore last.
            for entry in self.entries.values() {
                let _ = entry.signal(libc::SIGKILL);
            }
            self.entries.clear();
        }
    }
    #[derive(Clone)]
    pub struct ProcessPool(Arc<Mutex<Option<Pool>>>);
    impl std::fmt::Debug for ProcessPool {
        fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            formatter.write_str("ProcessPool")
        }
    }
    impl ProcessPool {
        fn lock(&self) -> Result<MutexGuard<'_, Option<Pool>>> {
            if unsafe { libc::syscall(libc::SYS_gettid) } != i64::from(std::process::id()) {
                return Err("process pool requires the main thread".into());
            }
            Ok(self.0.lock().map_err(|_| "process pool lock poisoned")?)
        }
    }
    impl Resource for ProcessPool {
        fn check_open(&self) -> Result<()> {
            self.lock()?.as_ref().ok_or("process pool is closed")?;
            Ok(())
        }
        fn close(&self) -> Result<()> {
            self.lock()?.take();
            Ok(())
        }
    }
    pub fn process_pool() -> Result<ProcessPool> {
        let signals = Signals::install()?;
        Ok(ProcessPool(Arc::new(Mutex::new(Some(Pool {
            entries: BTreeMap::new(),
            next_id: 1,
            _signals: signals,
        })))))
    }
    pub fn process_pool_close(pool: &ProcessPool) -> Result<()> {
        pool.close()
    }
    pub fn process_pool_signal(pool: &ProcessPool) -> Result<i64> {
        pool.check_open()?;
        Ok(i64::from(INTERRUPTED.load(Ordering::Relaxed)))
    }
    pub fn process_spawn(
        pool: &ProcessPool,
        arguments: &[String],
        environment: &IndexMap<String, String>,
        cwd: &str,
    ) -> Result<i64> {
        let mut guard = pool.lock()?;
        let pool = guard.as_mut().ok_or("process pool is closed")?;
        validate(
            &[arguments.to_vec()],
            &[environment.clone()],
            cwd,
            &[],
            1,
            0,
        )?;
        if INTERRUPTED.load(Ordering::Relaxed) != 0 {
            return Err("process pool is interrupted".into());
        }
        if pool.entries.len() >= 32 || pool.next_id == i64::MAX {
            return Err("process pool capacity exceeded".into());
        }
        let mut child = Command::new(&arguments[0])
            .args(&arguments[1..])
            .env_clear()
            .envs(environment)
            .current_dir(cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .process_group(0)
            .spawn()
            .map_err(|_| "process pool spawn failed")?;
        let output = File::from(OwnedFd::from(child.stdout.take().unwrap()));
        let error = File::from(OwnedFd::from(child.stderr.take().unwrap()));
        let entry = Entry {
            child,
            output: Some(output),
            error: Some(error),
            code: None,
        };
        nonblocking(entry.output.as_ref().unwrap().as_raw_fd())?;
        nonblocking(entry.error.as_ref().unwrap().as_raw_fd())?;
        let identifier = pool.next_id;
        pool.next_id += 1;
        pool.entries.insert(identifier, entry);
        Ok(identifier)
    }
    pub fn process_signal(pool: &ProcessPool, identifier: i64, number: i64) -> Result<()> {
        let guard = pool.lock()?;
        let pool = guard.as_ref().ok_or("process pool is closed")?;
        if number != 15 && number != 9 {
            return Err("process pool signal must be TERM or KILL".into());
        }
        pool.entries
            .get(&identifier)
            .ok_or("unknown process pool child")?
            .signal(number as i32)
    }
    fn read_once(stream: &mut Option<File>, limit: usize) -> Result<Vec<u8>> {
        let mut data = vec![0; limit];
        if let Some(file) = stream {
            match file.read(&mut data) {
                Ok(count) => {
                    data.truncate(count);
                    if count == 0 {
                        *stream = None;
                    }
                    return Ok(data);
                }
                Err(error)
                    if matches!(
                        error.kind(),
                        io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                    ) => {}
                Err(error) => return Err(error.into()),
            }
        }
        Ok(Vec::new())
    }
    pub fn process_poll(
        pool: &ProcessPool,
        identifier: i64,
        limit: i64,
    ) -> Result<(Json, Vec<u8>, Vec<u8>)> {
        let mut guard = pool.lock()?;
        let pool = guard.as_mut().ok_or("process pool is closed")?;
        if !(1..=65536).contains(&limit) {
            return Err("process pool read limit must be 1..65536".into());
        }
        let entry = pool
            .entries
            .get_mut(&identifier)
            .ok_or("unknown process pool child")?;
        if entry.code.is_none() {
            entry.code = peek(&entry.child)?;
            if entry.code.is_some() {
                entry.signal(libc::SIGKILL)?;
            }
        }
        let output = read_once(&mut entry.output, limit as usize)?;
        let error = read_once(&mut entry.error, limit as usize)?;
        let complete = entry.code.is_some() && entry.output.is_none() && entry.error.is_none();
        let status = serde_json::json!({"pid": entry.child.id(), "exited": entry.code.is_some(), "returncode": entry.code, "complete": complete});
        if complete {
            // Dropping the entry kills the group and reaps its still-owned leader.
            pool.entries.remove(&identifier);
        }
        Ok((status, output, error))
    }
}
#[cfg(target_os = "linux")]
pub use linux::*;

#[cfg(not(target_os = "linux"))]
mod unavailable {
    use super::*;
    #[derive(Clone, Debug)]
    pub struct ProcessPool;
    impl crate::resources::Resource for ProcessPool {
        fn check_open(&self) -> Result<()> {
            Err("process pool currently requires Linux".into())
        }
        fn close(&self) -> Result<()> {
            Ok(())
        }
    }
    pub fn process_pool() -> Result<ProcessPool> {
        Err("process pool currently requires Linux".into())
    }
    pub fn process_pool_close(_: &ProcessPool) -> Result<()> {
        Ok(())
    }
    pub fn process_pool_signal(_: &ProcessPool) -> Result<i64> {
        Err("process pool currently requires Linux".into())
    }
    pub fn process_spawn(
        _: &ProcessPool,
        _: &[String],
        _: &IndexMap<String, String>,
        _: &str,
    ) -> Result<i64> {
        Err("process pool currently requires Linux".into())
    }
    pub fn process_signal(_: &ProcessPool, _: i64, _: i64) -> Result<()> {
        Err("process pool currently requires Linux".into())
    }
    pub fn process_poll(_: &ProcessPool, _: i64, _: i64) -> Result<(Json, Vec<u8>, Vec<u8>)> {
        Err("process pool currently requires Linux".into())
    }
}
#[cfg(not(target_os = "linux"))]
pub use unavailable::*;
