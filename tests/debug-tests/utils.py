import argparse

from distributed.comm.utils import from_frames
from distributed.utils import nbytes, parse_bytes

import cupy
import numpy as np
import rmm
import ucp

ITERATIONS = 3


def cuda_array(size):
    return rmm.DeviceBuffer(size=size)


async def send(ep, frames):
    await ep.send(np.array([len(frames)], dtype=np.uint64))
    await ep.send(
        np.array(
            [hasattr(f, "__cuda_array_interface__") for f in frames], dtype=np.bool
        )
    )
    await ep.send(np.array([nbytes(f) for f in frames], dtype=np.uint64))
    # Send frames
    for frame in frames:
        if nbytes(frame) > 0:
            await ep.send(frame)


async def recv(ep):
    try:
        # Recv meta data
        nframes = np.empty(1, dtype=np.uint64)
        await ep.recv(nframes)
        is_cudas = np.empty(nframes[0], dtype=np.bool)
        await ep.recv(is_cudas)
        sizes = np.empty(nframes[0], dtype=np.uint64)
        await ep.recv(sizes)
    except (ucp.exceptions.UCXCanceled, ucp.exceptions.UCXCloseError) as e:
        msg = "SOMETHING TERRIBLE HAS HAPPENED IN THE TEST"
        raise e(msg)

    # Recv frames
    frames = []
    for is_cuda, size in zip(is_cudas.tolist(), sizes.tolist()):
        if size > 0:
            if is_cuda:
                frame = cuda_array(size)
            else:
                frame = np.empty(size, dtype=np.uint8)
            await ep.recv(frame)
            frames.append(frame)
        else:
            if is_cuda:
                frames.append(cuda_array(size))
            else:
                frames.append(b"")

    msg = await from_frames(frames)
    print("size of the message: ", len(msg["data"]))
    return frames, msg


def set_rmm():
    rmm.reinitialize(
        pool_allocator=True, managed_memory=False, initial_pool_size=parse_bytes("6GB")
    )
    cupy.cuda.set_allocator(rmm.rmm_cupy_allocator)


def parse_args(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--server", default=None, help="server address.")
    parser.add_argument("-p", "--port", default=13337, help="server port.", type=int)
    parser.add_argument(
        "-n",
        "--n-bytes",
        default="10 Mb",
        type=parse_bytes,
        help="Message size. Default '10 Mb'.",
    )
    parser.add_argument(
        "--n-iter",
        default=10,
        type=int,
        help="Numer of send / recv iterations (default 10).",
    )

    return parser.parse_args()
