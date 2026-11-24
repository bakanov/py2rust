//! Filesystem observations; traversal, exclusions and reporting belong in Python.
use crate::{Json, Result};
use std::path::{Path, PathBuf};

fn path(value: &str) -> Result<PathBuf> {
    if value.is_empty() || value.as_bytes().contains(&0) {
        return Err("filesystem path must be nonempty and NUL-free".into());
    }
    Ok(Path::new(value).components().collect())
}

#[cfg(unix)]
pub fn path_stat(value: &str, follow_links: bool) -> Result<Json> {
    use std::os::unix::fs::{FileTypeExt, MetadataExt};
    let path = path(value)?;
    let metadata = if follow_links {
        std::fs::metadata(path)?
    } else {
        std::fs::symlink_metadata(path)?
    };
    let file_type = metadata.file_type();
    let kind = if file_type.is_file() {
        "file"
    } else if file_type.is_dir() {
        "directory"
    } else if file_type.is_symlink() {
        "symlink"
    } else if file_type.is_fifo() {
        "fifo"
    } else if file_type.is_socket() {
        "socket"
    } else if file_type.is_block_device() {
        "block"
    } else if file_type.is_char_device() {
        "char"
    } else {
        "other"
    };
    fn number(value: u64) -> Result<i64> {
        Ok(i64::try_from(value).map_err(|_| "metadata exceeds signed 64-bit range")?)
    }
    fn nanoseconds(seconds: i64, nanos: i64) -> Result<i64> {
        Ok(
            i64::try_from(i128::from(seconds) * 1_000_000_000 + i128::from(nanos))
                .map_err(|_| "metadata timestamp exceeds signed 64-bit nanoseconds")?,
        )
    }
    Ok(serde_json::json!({
        "kind": kind, "size": number(metadata.size())?, "mode": i64::from(metadata.mode() & 0o7777),
        "device": number(metadata.dev())?, "inode": number(metadata.ino())?, "links": number(metadata.nlink())?,
        "mtime_ns": nanoseconds(metadata.mtime(), metadata.mtime_nsec())?,
        "atime_ns": nanoseconds(metadata.atime(), metadata.atime_nsec())?,
        "ctime_ns": nanoseconds(metadata.ctime(), metadata.ctime_nsec())?,
    }))
}
#[cfg(not(unix))]
pub fn path_stat(_value: &str, _follow_links: bool) -> Result<Json> {
    Err("filesystem metadata currently requires Unix".into())
}

pub fn directory_names(value: &str, limit: i64) -> Result<Vec<String>> {
    if !(1..=100000).contains(&limit) {
        return Err("directory name limit must be 1..100000".into());
    }
    let path = path(value)?;
    if !std::fs::symlink_metadata(&path)?.is_dir() {
        return Err("directory listing requires a directory, not a symlink".into());
    }
    let mut names = Vec::new();
    for entry in std::fs::read_dir(path)? {
        let entry = entry?;
        if names.len() == limit as usize {
            return Err("directory name limit exceeded".into());
        }
        names.push(
            entry
                .file_name()
                .into_string()
                .map_err(|_| "non-UTF8 filename")?,
        );
    }
    names.sort();
    Ok(names)
}

pub fn read_link(value: &str) -> Result<String> {
    Ok(std::fs::read_link(path(value)?)?
        .into_os_string()
        .into_string()
        .map_err(|_| "non-UTF8 symlink target")?)
}

/// Atomically move a directory entry without replacing any existing destination.
/// Unsupported kernels/filesystems return an error; never fall back to rename().
#[cfg(target_os = "linux")]
pub fn rename_no_replace(source: &str, destination: &str) -> Result<()> {
    use std::ffi::CString;
    use std::os::unix::ffi::OsStrExt;
    let source = CString::new(path(source)?.as_os_str().as_bytes())?;
    let destination = CString::new(path(destination)?.as_os_str().as_bytes())?;
    // SAFETY: both pointers reference live, NUL-terminated C strings for this call.
    let result = unsafe {
        libc::renameat2(
            libc::AT_FDCWD,
            source.as_ptr(),
            libc::AT_FDCWD,
            destination.as_ptr(),
            libc::RENAME_NOREPLACE,
        )
    };
    if result != 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    Ok(())
}
#[cfg(not(target_os = "linux"))]
pub fn rename_no_replace(_source: &str, _destination: &str) -> Result<()> {
    Err("rename_no_replace currently requires Linux".into())
}

#[cfg(unix)]
pub fn mkdir_new(value: &str) -> Result<()> {
    use std::os::unix::fs::DirBuilderExt;
    std::fs::DirBuilder::new()
        .mode(0o700)
        .create(path(value)?)?;
    Ok(())
}
#[cfg(not(unix))]
pub fn mkdir_new(_value: &str) -> Result<()> {
    Err("private directory creation requires Unix".into())
}

#[cfg(unix)]
pub fn create_symlink(target: &str, value: &str) -> Result<()> {
    if target.is_empty() || target.as_bytes().contains(&0) {
        return Err("symlink target must be nonempty and NUL-free".into());
    }
    std::os::unix::fs::symlink(target, path(value)?)?;
    Ok(())
}
#[cfg(not(unix))]
pub fn create_symlink(_target: &str, _value: &str) -> Result<()> {
    Err("symlink creation requires Unix".into())
}

#[cfg(unix)]
#[allow(clippy::useless_conversion)] // time_t/c_long can be narrower on other Unix targets.
pub fn path_set_metadata(value: &str, mode: i64, mtime_ns: i64) -> Result<()> {
    use std::ffi::CString;
    use std::os::fd::AsRawFd;
    use std::os::unix::ffi::OsStrExt;
    use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
    if !(0..=0o777).contains(&mode) {
        return Err("mode must contain only ordinary permission bits".into());
    }
    let path = path(value)?;
    let metadata = std::fs::symlink_metadata(&path)?;
    let times = [
        libc::timespec {
            tv_sec: 0,
            tv_nsec: libc::UTIME_OMIT,
        },
        libc::timespec {
            tv_sec: mtime_ns.div_euclid(1_000_000_000).try_into()?,
            tv_nsec: mtime_ns.rem_euclid(1_000_000_000).try_into()?,
        },
    ];
    if metadata.file_type().is_symlink() {
        if mode != 0o777 {
            return Err("symlink mode must be 0777".into());
        }
        let name = CString::new(path.as_os_str().as_bytes())?;
        let result = unsafe {
            libc::utimensat(
                libc::AT_FDCWD,
                name.as_ptr(),
                times.as_ptr(),
                libc::AT_SYMLINK_NOFOLLOW,
            )
        };
        if result != 0 {
            return Err(std::io::Error::last_os_error().into());
        }
    } else {
        let file = std::fs::OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
            .open(path)?;
        let metadata = file.metadata()?;
        if !(metadata.is_file() || metadata.is_dir()) {
            return Err("metadata update requires a file, directory or symlink".into());
        }
        file.set_permissions(std::fs::Permissions::from_mode(mode as u32))?;
        let result = unsafe { libc::futimens(file.as_raw_fd(), times.as_ptr()) };
        if result != 0 {
            return Err(std::io::Error::last_os_error().into());
        }
        file.sync_all()?;
    }
    Ok(())
}
#[cfg(not(unix))]
pub fn path_set_metadata(_value: &str, _mode: i64, _mtime_ns: i64) -> Result<()> {
    Err("metadata updates require Unix".into())
}

/// Atomic regular-file publication; callers protect directory entries from races.
#[cfg(unix)]
pub fn replace_file(source: &str, destination: &str) -> Result<()> {
    use std::os::unix::fs::MetadataExt;
    let source = path(source)?;
    let destination = path(destination)?;
    let before = std::fs::symlink_metadata(&source)?;
    if !before.is_file() {
        return Err("replacement source must be a regular file".into());
    }
    match std::fs::symlink_metadata(&destination) {
        Ok(previous) => {
            if !previous.is_file() {
                return Err("replacement destination must be a regular file or absent".into());
            }
            if before.dev() == previous.dev() && before.ino() == previous.ino() {
                return Err("replacement paths alias".into());
            }
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(error) => return Err(error.into()),
    }
    std::fs::rename(source, destination)?;
    Ok(())
}
#[cfg(not(unix))]
pub fn replace_file(_source: &str, _destination: &str) -> Result<()> {
    Err("regular-file replacement currently requires Unix".into())
}
