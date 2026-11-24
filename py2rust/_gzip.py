"""Bounded, single-member gzip streams with explicit writer finalization."""

# ruff: noqa: PLR1711 - explicit returns required by repository guidelines

import os
import stat
import threading
import zlib
from typing import BinaryIO


def _limit(value: int) -> None:
    if type(value) is not int or not 0 <= value < 2**63:
        raise ValueError("gzip limits must be nonnegative signed 64-bit integers")
    return


def _open(path: str, writing: bool) -> BinaryIO:
    if not path or "\0" in path:
        raise ValueError("gzip path must be nonempty and NUL-free")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL if writing else os.O_RDONLY
    descriptor = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("gzip requires a regular file")
        return os.fdopen(descriptor, "wb" if writing else "rb", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise


class GzipWriter:
    """Aliases share one stream. Close aborts; finish is the only success receipt."""

    def __init__(self, file: BinaryIO, level: int, compressed: int, expanded: int) -> None:
        self.file = file
        self.lock = threading.RLock()
        self.encoder = zlib.compressobj(level, zlib.DEFLATED, -15)
        self.compressed_limit = compressed
        self.expanded_limit = expanded
        self.compressed = 0
        self.expanded = 0
        self.crc = 0
        return

    def emit(self, data: bytes) -> None:
        if len(data) > self.compressed_limit - self.compressed:
            raise ValueError("gzip compressed output exceeds limit")
        pending = memoryview(data)
        while pending:
            count = self.file.write(pending)
            if not count:
                raise OSError("gzip write made no progress")
            self.compressed += count
            pending = pending[count:]
        return

    def __enter__(self) -> "GzipWriter":  # noqa: PYI034 - Python 3.10 baseline
        with self.lock:
            if self.file.closed:
                raise ValueError("gzip writer is closed")
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        gzip_writer_close(self)
        return


def gzip_create(path: str, level: int, compressed_limit: int, expanded_limit: int) -> GzipWriter:
    """Create a new file exclusively, with mtime=0, OS=255 and no optional header fields."""
    _limit(compressed_limit)
    _limit(expanded_limit)
    if type(level) is not int or not 0 <= level <= 9:
        raise ValueError("gzip compression level must be 0..9")
    if compressed_limit < 10:
        raise ValueError("gzip output limit is smaller than its header")
    writer = GzipWriter(_open(path, True), level, compressed_limit, expanded_limit)
    try:
        flag = 2 if level == 9 else 4 if level <= 1 else 0
        writer.emit(b"\x1f\x8b\x08\x00\x00\x00\x00\x00" + bytes([flag, 255]))
        return writer
    except BaseException:
        writer.file.close()
        raise


def gzip_write(handle: GzipWriter, data: bytes) -> None:
    if type(data) is not bytes or len(data) > 1048576:
        raise ValueError("gzip write requires at most 1 MiB of bytes")
    with handle.lock:
        try:
            if handle.file.closed:
                raise ValueError("gzip writer is closed")
            if len(data) > handle.expanded_limit - handle.expanded:
                raise ValueError("gzip expanded output exceeds limit")
            handle.emit(handle.encoder.compress(data))
            handle.crc = zlib.crc32(data, handle.crc)
            handle.expanded += len(data)
        except BaseException:
            handle.file.close()
            raise
    return


def gzip_finish(handle: GzipWriter) -> tuple[int, int]:
    """Write and sync the complete member, close all aliases, return compressed/expanded sizes."""
    with handle.lock:
        try:
            if handle.file.closed:
                raise ValueError("gzip writer is closed")
            handle.emit(handle.encoder.flush())
            handle.emit(handle.crc.to_bytes(4, "little") + (handle.expanded & 0xFFFFFFFF).to_bytes(4, "little"))
            os.fsync(handle.file.fileno())
            return handle.compressed, handle.expanded
        finally:
            handle.file.close()


def gzip_writer_close(handle: GzipWriter) -> None:
    with handle.lock:
        handle.file.close()
    return


class GzipReader:
    """Bounded single-member decoder. Only a successful empty read validates the entire file."""

    def __init__(self, file: BinaryIO, compressed: int, expanded: int) -> None:
        self.file = file
        self.lock = threading.RLock()
        self.decoder = zlib.decompressobj(-15)
        self.compressed_limit = compressed
        self.expanded_limit = expanded
        self.compressed = 0
        self.expanded = 0
        self.crc = 0
        self.pending = b""
        self.eof = False
        return

    def source(self, count: int) -> bytes:
        data = self.file.read(min(count, self.compressed_limit - self.compressed + 1))
        if len(data) > self.compressed_limit - self.compressed:
            raise ValueError("gzip compressed input exceeds limit")
        self.compressed += len(data)
        return data

    def exact(self, count: int) -> bytes:
        result = self.pending[:count]
        self.pending = self.pending[len(result) :]
        while len(result) < count:
            part = self.source(count - len(result))
            if not part:
                raise ValueError("truncated gzip input")
            result += part
        return result

    def header(self) -> None:
        data = self.exact(10)
        if data[:3] != b"\x1f\x8b\x08" or data[3] & 224:
            raise ValueError("invalid gzip header")
        flags = data[3]
        checksum = zlib.crc32(data)
        if flags & 4:
            length = self.exact(2)
            checksum = zlib.crc32(length, checksum)
            checksum = zlib.crc32(self.exact(int.from_bytes(length, "little")), checksum)
        for flag in [8, 16]:
            if flags & flag:
                length = 0
                while True:
                    byte = self.exact(1)
                    checksum = zlib.crc32(byte, checksum)
                    if byte == b"\0":
                        break
                    length += 1
                    if length > 65535:
                        raise ValueError("gzip name or comment exceeds 65535 bytes")
        if flags & 2 and int.from_bytes(self.exact(2), "little") != checksum & 65535:
            raise ValueError("invalid gzip header CRC")
        return

    def __enter__(self) -> "GzipReader":  # noqa: PYI034 - Python 3.10 baseline
        with self.lock:
            if self.file.closed:
                raise ValueError("gzip reader is closed")
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        gzip_reader_close(self)
        return


def gzip_open(path: str, compressed_limit: int, expanded_limit: int) -> GzipReader:
    _limit(compressed_limit)
    _limit(expanded_limit)
    reader = GzipReader(_open(path, False), compressed_limit, expanded_limit)
    try:
        if os.fstat(reader.file.fileno()).st_size > compressed_limit:
            raise ValueError("gzip compressed input exceeds limit")
        reader.header()
        return reader
    except BaseException:
        reader.file.close()
        raise


def gzip_read(handle: GzipReader, count: int) -> bytes:
    if type(count) is not int or not 1 <= count <= 1048576:
        raise ValueError("gzip read size must be 1..1 MiB")
    with handle.lock:
        try:
            if handle.file.closed:
                raise ValueError("gzip reader is closed")
            output = bytearray()
            while len(output) < count and not handle.eof:
                if handle.decoder.eof:
                    trailer = handle.exact(8)
                    if int.from_bytes(trailer[:4], "little") != handle.crc:
                        raise ValueError("invalid gzip CRC")
                    if int.from_bytes(trailer[4:], "little") != handle.expanded & 0xFFFFFFFF:
                        raise ValueError("invalid gzip size")
                    if handle.pending or handle.source(1):
                        raise ValueError("expected exactly one gzip member without trailing data")
                    handle.eof = True
                    break
                if not handle.pending:
                    handle.pending = handle.source(65536)
                    if not handle.pending:
                        raise ValueError("truncated gzip input")
                available = min(count - len(output), handle.expanded_limit - handle.expanded + 1)
                data = handle.decoder.decompress(handle.pending, available)
                handle.pending = handle.decoder.unused_data if handle.decoder.eof else handle.decoder.unconsumed_tail
                if len(data) > handle.expanded_limit - handle.expanded:
                    raise ValueError("gzip expanded input exceeds limit")
                handle.expanded += len(data)
                handle.crc = zlib.crc32(data, handle.crc)
                output.extend(data)
            return bytes(output)
        except BaseException:
            handle.file.close()
            raise


def gzip_reader_close(handle: GzipReader) -> None:
    with handle.lock:
        handle.file.close()
    return
