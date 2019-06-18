import asyncio
import itertools
import pytest
from contextlib import asynccontextmanager

import ucp


@asynccontextmanager
async def echo_pair(cuda_info=None):
    ucp.init()
    loop = asyncio.get_event_loop()
    listener = ucp.start_listener(ucp.make_server(cuda_info),
                                  is_coroutine=True)
    #t = loop.create_task(listener.coroutine) # ucx-py internally does this
    address = ucp.get_address()
    client = await ucp.get_endpoint(address.encode(), listener.port)
    try:
        yield listener, client
    finally:
        ucp.stop_listener(listener)
        ucp.destroy_ep(client)
        ucp.fin()


@pytest.mark.asyncio
async def test_send_recv_bytes():
    async with echo_pair() as (_, client):
        msg = b"hi"

        await client.send_obj(b'2')
        await client.send_obj(msg)
        resp = await client.recv_obj(len(msg))
        result = ucp.get_obj_from_msg(resp)

    assert result.tobytes() == msg


@pytest.mark.asyncio
async def test_send_recv_large_bytes():
    async with echo_pair() as (_, client):
        x = "a"
        x = x * 4194304
        msg = bytes(x, encoding='utf-8')

        await client.send_obj(b'4194304')
        await client.send_obj(msg)
        resp = await client.recv_obj(len(msg))
        result = ucp.get_obj_from_msg(resp)

    assert result.tobytes() == msg


@pytest.mark.asyncio
async def test_send_recv_memoryview():
    async with echo_pair() as (_, client):
        msg = memoryview(b"hi")

        await client.send_obj(b'2')
        await client.send_obj(msg)
        resp = await client.recv_obj(len(msg))
        result = ucp.get_obj_from_msg(resp)

    assert result == msg


@pytest.mark.asyncio
async def test_send_recv_large_memoryview():
    async with echo_pair() as (_, client):
        x = "a"
        x = x * 4194304
        msg = bytes(x, encoding='utf-8')
        msg = memoryview(msg)

        await client.send_obj(b'4194304')
        await client.send_obj(msg)
        resp = await client.recv_obj(len(msg))
        result = ucp.get_obj_from_msg(resp)

    assert result == msg


@pytest.mark.asyncio
async def test_send_recv_numpy():
    np = pytest.importorskip('numpy')
    async with echo_pair() as (_, client):
        msg = np.frombuffer(memoryview(b"hi"), dtype='u1')

        await client.send_obj(b'2')
        await client.send_obj(msg)
        resp = await client.recv_obj(len(msg))
        result = ucp.get_obj_from_msg(resp)
        result = np.frombuffer(result, 'u1')


@pytest.mark.asyncio
async def test_send_recv_large_numpy():
    np = pytest.importorskip('numpy')
    async with echo_pair() as (_, client):
        x = "a"
        x = x * 4194304
        msg = bytes(x, encoding='utf-8')
        msg = memoryview(msg)
        msg = np.frombuffer(msg, dtype='u1')

        await client.send_obj(b'4194304')
        await client.send_obj(msg)
        resp = await client.recv_obj(len(msg))
        result = ucp.get_obj_from_msg(resp)
        result = np.frombuffer(result, 'u1')

    np.testing.assert_array_equal(result, msg)


@pytest.mark.asyncio
async def test_send_recv_cupy():
    cupy = pytest.importorskip('cupy')
    cuda_info = {
        'shape': [2],
        'typestr': '|u1'
    }
    async with echo_pair(cuda_info) as (_, client):
        msg = cupy.array(memoryview(b"hi"), dtype='u1')

        client.send_obj(b'2')
        await client.send_obj(msg)
        resp = await client.recv_obj(len(msg), cuda=True)
        result = ucp.get_obj_from_msg(resp)

    assert hasattr(result, '__cuda_array_interface__')
    result.typestr = msg.__cuda_array_interface__['typestr']
    result = cupy.asarray(result)
    cupy.testing.assert_array_equal(msg, result)


@pytest.mark.asyncio
async def test_send_recv_large_cupy():
    cupy = pytest.importorskip('cupy')
    cuda_info = {
        'shape': [4194304],
        'typestr': '|u1'
    }
    async with echo_pair(cuda_info) as (_, client):
        x = "a"
        x = x * 4194304
        msg = bytes(x, encoding='utf-8')
        msg = memoryview(msg)
        msg = cupy.array(msg, dtype='u1')

        await client.send_obj(b'4194304')
        await client.send_obj(msg)
        resp = await client.recv_obj(len(msg), cuda=True)
        result = ucp.get_obj_from_msg(resp)

    assert hasattr(result, '__cuda_array_interface__')
    result.typestr = msg.__cuda_array_interface__['typestr']
    result = cupy.asarray(result)
    cupy.testing.assert_array_equal(msg, result)


@pytest.mark.asyncio
async def test_send_recv_numba():
    numba = pytest.importorskip('numba')
    pytest.importorskip('numba.cuda')
    import numpy as np

    cuda_info = {
        'shape': [2],
        'typestr': '|u1'
    }
    async with echo_pair(cuda_info) as (_, client):
        arr = np.array(memoryview(b"hi"), dtype='u1')
        msg = numba.cuda.to_device(arr)

        client.send_obj(b'2')
        await client.send_obj(msg)
        resp = await client.recv_obj(len(msg), cuda=True)
        result = ucp.get_obj_from_msg(resp)

    assert hasattr(result, '__cuda_array_interface__')
    result.typestr = msg.__cuda_array_interface__['typestr']
    result = numba.cuda.as_cuda_array(result)
    assert isinstance(result, numba.cuda.devicearray.DeviceNDArray)
    result = np.asarray(result, dtype='|u1')
    msg = np.asarray(msg, dtype='|u1')

    np.testing.assert_array_equal(msg, result)


@pytest.mark.asyncio
async def test_send_recv_large_numba():
    numba = pytest.importorskip('numba')
    pytest.importorskip('numba.cuda')
    import numpy as np

    cuda_info = {
        'shape': [4194304],
        'typestr': '|u1'
    }
    async with echo_pair(cuda_info) as (_, client):
        x = "a"
        x = x * 4194304
        msg = bytes(x, encoding='utf-8')
        msg = memoryview(msg)
        arr = np.array(msg, dtype='u1')
        msg = numba.cuda.to_device(arr)

        await client.send_obj(b'4194304')
        await client.send_obj(msg)
        resp = await client.recv_obj(len(msg), cuda=True)
        result = ucp.get_obj_from_msg(resp)

    assert hasattr(result, '__cuda_array_interface__')
    result.typestr = msg.__cuda_array_interface__['typestr']
    result = numba.cuda.as_cuda_array(result)
    assert isinstance(result, numba.cuda.devicearray.DeviceNDArray)
    result = np.asarray(result, dtype='|u1')
    msg = np.asarray(msg, dtype='|u1')

    np.testing.assert_array_equal(msg, result)


@pytest.mark.asyncio
async def test_send_recv_into():
    sink = bytearray(2)
    async with echo_pair() as (_, client):
        msg = b'hi'
        await client.send_obj(b'2')
        await client.send_obj(msg)

        resp = await client.recv_into(sink, 2)
        result = resp.get_obj()

    assert result == b'hi'
    assert sink == b'hi'


@pytest.mark.asyncio
async def test_send_recv_into_large():
    sink = bytearray(4194304)
    async with echo_pair() as (_, client):
        x = "a"
        x = x * 4194304
        msg = bytes(x, encoding='utf-8')

        await client.send_obj(b'4194304')
        await client.send_obj(msg)

        resp = await client.recv_into(sink, 4194304)
        result = resp.get_obj()

    assert result == bytes(x, encoding='utf-8')
    assert sink == bytes(x, encoding='utf-8')


@pytest.mark.asyncio
async def test_send_recv_into_cuda():
    cupy = pytest.importorskip("cupy")
    sink = cupy.zeros(10, dtype='u1')
    msg = cupy.arange(10, dtype='u1')

    async with echo_pair() as (_, client):
        await client.send_obj(str(msg.nbytes).encode())
        await client.send_obj(msg)

        resp = await client.recv_into(sink, msg.nbytes)
        result = resp.get_obj()

    result = cupy.asarray(result)
    cupy.testing.assert_array_equal(result, msg)
    cupy.testing.assert_array_equal(sink, msg)

@pytest.mark.asyncio
async def test_send_recv_into_large_cuda():
    cupy = pytest.importorskip("cupy")
    sink = cupy.zeros(4194304, dtype='u1')
    msg = cupy.arange(4194304, dtype='u1')

    async with echo_pair() as (_, client):
        await client.send_obj(str(msg.nbytes).encode())
        await client.send_obj(msg)

        resp = await client.recv_into(sink, msg.nbytes)
        result = resp.get_obj()

    result = cupy.asarray(result)
    cupy.testing.assert_array_equal(result, msg)
    cupy.testing.assert_array_equal(sink, msg)
