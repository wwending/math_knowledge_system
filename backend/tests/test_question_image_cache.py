from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import threading
import time

import pytest

from app.services import question_image_cache as cache


def process_request(source, root, counter):
    def render(path, bbox):
        with counter.get_lock():
            counter.value += 1
        time.sleep(.1)
        return b"png", "image/png"
    cache.cached_question_image(source, {}, root=root, render=render)


@pytest.fixture
def images(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"original")
    root = tmp_path / "cache"
    calls = []
    def render(path, bbox):
        calls.append((path.read_bytes(), bbox))
        return path.read_bytes() + str(bbox).encode(), "image/png"
    def get(bbox=None, **kwargs):
        return cache.cached_question_image(source, {} if bbox is None else bbox, root=root, render=render, **kwargs)
    return source, root, calls, get


def test_hit_source_crop_spec_invalidation_and_corruption(images):
    source, root, calls, get = images
    assert get() == get()
    assert len(calls) == 1
    source.write_bytes(b"modified")  # same byte length
    assert get()[0].startswith(b"modified")
    get([0, 0, .5, .5])
    get(spec="next-png-version")
    assert len(calls) == 4
    for artifact in root.glob("*.qic"):
        artifact.write_bytes(b"broken")
    assert get()[0].startswith(b"modified")
    assert len(calls) == 5
    with pytest.raises(ValueError):
        get([0, 0, 0, 1])
    assert source.read_bytes() == b"modified"


def test_capacity_and_oversize_do_not_delete_sources(images):
    source, root, calls, get = images
    root.mkdir()
    foreign = root / "keep.txt"
    foreign.write_text("original")
    for width in (.2, .3, .4, .5):
        get([0, 0, width, 1], max_entries=2, max_bytes=200)
    artifacts = list(root.glob("*.qic"))
    assert len(artifacts) <= 2
    assert sum(p.stat().st_size for p in artifacts) <= 200
    get(max_bytes=1)
    assert list(root.glob("*.qic")) == []
    assert source.exists() and foreign.exists()
    assert len(list(root.glob("*.lock"))) <= cache.STRIPES + 1
    assert not list(root.glob("*.tmp"))


def test_failure_recovers_and_source_mutation_does_not_publish(images):
    source, root, calls, get = images
    def broken(path, bbox):
        raise ValueError("cannot encode")
    with pytest.raises(ValueError):
        cache.cached_question_image(source, {}, root=root, render=broken)
    assert not list(root.glob("*.qic"))
    get()
    def changing(path, bbox):
        path.write_bytes(b"changed while rendering")
        return b"stale", "image/png"
    with pytest.raises(ValueError, match="changed"):
        cache.cached_question_image(source, {}, root=root, render=changing, spec="new")
    assert get()[0].startswith(b"changed while rendering")


def test_same_key_threads_generate_once(images):
    source, root, calls, get = images
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: get(), range(8)))
    assert len(calls) == 1
    assert all(result == results[0] for result in results)


def test_cross_process_generation_is_exclusive(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"source")
    context = multiprocessing.get_context("spawn")
    counter = context.Value("i", 0)
    workers = [context.Process(target=process_request, args=(source, tmp_path / "cache", counter)) for _ in range(3)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(20)
        if worker.is_alive():
            worker.terminate()
            worker.join()
        assert worker.exitcode == 0
    assert counter.value == 1


def test_busy_generation_does_not_block_other_cache_hits(images, monkeypatch):
    source, root, calls, get = images
    expected = get()
    started, release = threading.Event(), threading.Event()
    def slow(path, bbox):
        started.set()
        assert release.wait(3)
        return b"new image", "image/png"
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(cache.cached_question_image, source, {}, root=root, render=slow, spec="slow")
        try:
            assert started.wait(2)
            assert get() == expected
        finally:
            release.set()
        future.result()
    monkeypatch.setattr(cache, "LOCK_TIMEOUT", .01)
    cache._locks[cache.STRIPES].acquire()
    try:
        with pytest.raises(TimeoutError):
            get()
    finally:
        cache._locks[cache.STRIPES].release()
