from hub.core.storage import MemoryProvider, LocalProvider, S3Provider
from hub.util.cache_chain import get_cache_chain
import pytest
from hub.util.s3 import has_s3_credentials
from uuid import uuid1

NUM_FILES = 20
MB = 1024 * 1024

SESSION_ID = str(uuid1())
local_provider = LocalProvider(
    f"./test/hub2/core/storage/test/test_storage_provider_{SESSION_ID}"
)
memory_provider = MemoryProvider(
    f"test/hub2/core/storage/tests/test_storage_provider_{SESSION_ID}"
)
s3_provider = S3Provider(
    f"snark-test/hub2/core/storage/tests/test_storage_provider_{SESSION_ID}"
)


def check_storage_provider(provider):
    FILE_1 = "abc.txt"
    FILE_2 = "def.txt"

    provider[FILE_1] = b"hello world"
    assert provider[FILE_1] == b"hello world"
    assert provider.get_bytes(FILE_1, 2, 5) == b"llo"

    provider.set_bytes(FILE_1, b"abcde", 6)
    assert provider[FILE_1] == b"hello abcde"

    provider.set_bytes(FILE_1, b"tuvwxyz", 6)
    assert provider[FILE_1] == b"hello tuvwxyz"

    provider.set_bytes(FILE_2, b"hello world", 3)
    assert provider[FILE_2] == b"\x00\x00\x00hello world"
    provider.set_bytes(FILE_2, b"new_text", overwrite=True)
    assert provider[FILE_2] == b"new_text"

    assert len(provider) >= 1

    for _ in provider:
        pass

    del provider[FILE_1]
    del provider[FILE_2]

    with pytest.raises(KeyError):
        provider[FILE_1]

    provider.flush()


def test_memory_provider():
    check_storage_provider(memory_provider)


def test_local_provider():
    check_storage_provider(local_provider)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_s3_provider():
    check_storage_provider(s3_provider)


def test_lru_mem_local():
    lru = get_cache_chain([memory_provider, local_provider], [32 * MB])
    check_storage_provider(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_lru_mem_s3():
    lru = get_cache_chain([memory_provider, s3_provider], [32 * MB])
    check_storage_provider(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_lru_local_s3():
    lru = get_cache_chain([local_provider, s3_provider], [160 * MB])
    check_storage_provider(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_lru_mem_local_s3():
    lru = get_cache_chain(
        [memory_provider, local_provider, s3_provider],
        [32 * MB, 160 * MB],
    )
    check_storage_provider(lru)


def detailed_check_lru(lru):
    chunk = b"0123456789123456" * MB
    assert lru.dirty_keys == set()
    assert set(lru.lru_sizes.keys()) == set()
    assert len(lru.cache_storage) == 0
    assert len(lru.next_storage) == 0
    assert lru.cache_used == 0
    assert len(lru) == 0

    lru["file_1"] = chunk
    assert lru.dirty_keys == {"file_1"}
    assert set(lru.lru_sizes.keys()) == {"file_1"}
    assert len(lru.cache_storage) == 1
    assert len(lru.next_storage) == 0
    assert lru.cache_used == 16 * MB
    assert len(lru) == 1

    lru["file_2"] = chunk
    assert lru.dirty_keys == {"file_1", "file_2"}
    assert set(lru.lru_sizes.keys()) == {"file_1", "file_2"}
    assert len(lru.cache_storage) == 2
    assert len(lru.next_storage) == 0
    assert lru.cache_used == 32 * MB
    assert len(lru) == 2

    lru["file_3"] = chunk
    assert lru.dirty_keys == {"file_3", "file_2"}
    assert set(lru.lru_sizes.keys()) == {"file_2", "file_3"}
    assert len(lru.cache_storage) == 2
    assert len(lru.next_storage) == 1
    assert lru.cache_used == 32 * MB
    assert len(lru) == 3

    lru["file_1"]
    assert lru.dirty_keys == {"file_3"}
    assert set(lru.lru_sizes.keys()) == {"file_1", "file_3"}
    assert len(lru.cache_storage) == 2
    assert len(lru.next_storage) == 2
    assert lru.cache_used == 32 * MB
    assert len(lru) == 3

    lru["file_3"]
    assert lru.dirty_keys == {"file_3"}
    assert set(lru.lru_sizes.keys()) == {"file_1", "file_3"}
    assert len(lru.cache_storage) == 2
    assert len(lru.next_storage) == 2
    assert lru.cache_used == 32 * MB
    assert len(lru) == 3

    del lru["file_3"]
    assert lru.dirty_keys == set()
    assert set(lru.lru_sizes.keys()) == {"file_1"}
    assert len(lru.cache_storage) == 1
    assert len(lru.next_storage) == 2
    assert lru.cache_used == 16 * MB
    assert len(lru) == 2

    del lru["file_1"]
    assert lru.dirty_keys == set()
    assert set(lru.lru_sizes.keys()) == set()
    assert len(lru.cache_storage) == 0
    assert len(lru.next_storage) == 1
    assert lru.cache_used == 0
    assert len(lru) == 1

    del lru["file_2"]
    assert lru.dirty_keys == set()
    assert set(lru.lru_sizes.keys()) == set()
    assert len(lru.cache_storage) == 0
    assert len(lru.next_storage) == 0
    assert lru.cache_used == 0
    assert len(lru) == 0

    with pytest.raises(KeyError):
        lru["file_1"]

    lru["file_1"] = chunk
    assert lru.dirty_keys == {"file_1"}
    assert set(lru.lru_sizes.keys()) == {"file_1"}
    assert len(lru.cache_storage) == 1
    assert len(lru.next_storage) == 0
    assert lru.cache_used == 16 * MB
    assert len(lru) == 1

    lru["file_2"] = chunk
    assert lru.dirty_keys == {"file_1", "file_2"}
    assert set(lru.lru_sizes.keys()) == {"file_1", "file_2"}
    assert len(lru.cache_storage) == 2
    assert len(lru.next_storage) == 0
    assert lru.cache_used == 32 * MB
    assert len(lru) == 2

    lru.flush()
    assert lru.dirty_keys == set()
    assert set(lru.lru_sizes.keys()) == {"file_1", "file_2"}
    assert len(lru.cache_storage) == 2
    assert len(lru.next_storage) == 2
    assert lru.cache_used == 32 * MB
    assert len(lru) == 2

    del lru["file_1"]
    del lru["file_2"]

    assert lru.dirty_keys == set()
    assert set(lru.lru_sizes.keys()) == set()
    assert len(lru.cache_storage) == 0
    assert len(lru.next_storage) == 0
    assert lru.cache_used == 0
    assert len(lru) == 0


def test_detailed_lru_mem_local():
    lru = get_cache_chain([memory_provider, local_provider], [32 * MB])
    detailed_check_lru(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_detailed_lru_mem_s3(benchmark):
    lru = get_cache_chain([memory_provider, s3_provider], [32 * MB])
    detailed_check_lru(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_detailed_lru_local_s3(benchmark):
    lru = get_cache_chain([local_provider, s3_provider], [32 * MB])
    detailed_check_lru(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_detailed_lru_mem_local_s3(benchmark):
    lru = get_cache_chain(
        [memory_provider, local_provider, s3_provider],
        [32 * MB, 160 * MB],
    )
    detailed_check_lru(lru)


def write_to_files(provider):
    chunk = b"0123456789123456" * MB
    for i in range(NUM_FILES):
        provider[f"file_{i}"] = chunk
    provider.flush()


def read_from_files(provider):
    for i in range(NUM_FILES):
        provider[f"file_{i}"]


def delete_files(provider):
    for i in range(NUM_FILES):
        del provider[f"file_{i}"]


def test_write_memory(benchmark):
    benchmark(write_to_files, memory_provider)
    delete_files(memory_provider)


def test_write_local(benchmark):
    benchmark(write_to_files, local_provider)
    delete_files(local_provider)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_write_s3(benchmark):
    benchmark(write_to_files, s3_provider)
    delete_files(s3_provider)


def test_write_lru_mem_local(benchmark):
    lru = get_cache_chain([memory_provider, local_provider], [32 * MB])
    benchmark(write_to_files, lru)
    delete_files(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_write_lru_mem_s3(benchmark):
    lru = get_cache_chain([memory_provider, s3_provider], [32 * MB])
    benchmark(write_to_files, lru)
    delete_files(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_write_lru_local_s3(benchmark):
    lru = get_cache_chain([local_provider, s3_provider], [160 * MB])
    benchmark(write_to_files, lru)
    delete_files(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_write_lru_mem_local_s3(benchmark):
    lru = get_cache_chain(
        [memory_provider, local_provider, s3_provider],
        [32 * MB, 160 * MB],
    )
    benchmark(write_to_files, lru)
    delete_files(lru)


def test_read_memory(benchmark):
    write_to_files(memory_provider)
    benchmark(read_from_files, memory_provider)
    delete_files(memory_provider)


def test_read_local(benchmark):
    write_to_files(local_provider)
    benchmark(read_from_files, local_provider)
    delete_files(local_provider)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_read_s3(benchmark):
    write_to_files(s3_provider)
    benchmark(read_from_files, s3_provider)
    delete_files(s3_provider)


def test_read_lru_mem_local(benchmark):
    write_to_files(local_provider)
    lru = get_cache_chain([memory_provider, local_provider], [32 * MB])
    benchmark(read_from_files, lru)
    delete_files(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_read_lru_mem_s3(benchmark):
    write_to_files(s3_provider)
    lru = get_cache_chain([memory_provider, s3_provider], [32 * MB])
    benchmark(read_from_files, lru)
    delete_files(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_read_lru_local_s3(benchmark):
    write_to_files(s3_provider)
    lru = get_cache_chain([local_provider, s3_provider], [160 * MB])
    benchmark(read_from_files, lru)
    delete_files(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_read_lru_mem_local_s3(benchmark):
    write_to_files(s3_provider)
    lru = get_cache_chain(
        [memory_provider, local_provider, s3_provider],
        [32 * MB, 160 * MB],
    )
    benchmark(read_from_files, lru)
    delete_files(lru)


def test_full_cache_read_lru_mem_local(benchmark):
    write_to_files(local_provider)
    lru = get_cache_chain([memory_provider, local_provider], [320 * MB])
    read_from_files(lru)
    benchmark(read_from_files, lru)
    delete_files(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_full_cache_read_lru_mem_s3(benchmark):
    write_to_files(s3_provider)
    lru = get_cache_chain([memory_provider, s3_provider], [320 * MB])
    read_from_files(lru)
    benchmark(read_from_files, lru)
    delete_files(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_full_cache_read_lru_local_s3(benchmark):
    write_to_files(s3_provider)
    lru = get_cache_chain([local_provider, s3_provider], [320 * MB])
    read_from_files(lru)
    benchmark(read_from_files, lru)
    delete_files(lru)


@pytest.mark.skipif(not has_s3_credentials(), reason="requires s3 credentials")
def test_full_cache_read_lru_mem_local_s3(benchmark):
    write_to_files(s3_provider)
    lru = get_cache_chain(
        [memory_provider, local_provider, s3_provider],
        [32 * MB, 320 * MB],
    )
    read_from_files(lru)
    benchmark(read_from_files, lru)
    delete_files(lru)
