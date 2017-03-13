"""
Utility WebGL functions, translated from Mozilla Developer Network.

Orignial code covered by Mozilla Public License, version 2.0.
"""

import asyncio
import traceback

import numpy as np
from numpy.core.umath_tests import inner1d


def normalize(v, axis=None):
    return v / np.linalg.norm(v, axis=axis)


def load_identity():
    return np.eye(4, dtype=np.float32)


def translate(matrix, v):
    matrix[3, :3] += v


async def _ensure_shader(gl, source, type):
    """Ensure that the shader compile status is OK.

    Note: This function is a coroutine, and therefore needs
    to be called with a branched GL context
    """
    shader = gl.createShader(type)
    with gl.chunk():
        gl.shaderSource(shader, source)
        gl.compileShader(shader)
    status = gl.getShaderParameter(shader, gl.COMPILE_STATUS)
    if not await status:
        log = gl.getShaderInfoLog(shader)
        gl.deleteShader(shader)
        raise RuntimeError(
            'An error occurred compiling the shaders: %s' % await log)
    return shader


def make_shader(gl, source, type):
    return asyncio.ensure_future(_ensure_shader(gl.branch(), source, type))


async def _ensure_program(gl, vertex_shader_source, fragment_shader_source):
    """Ensure that the shader program status is OK.

    Note: This function is a coroutine, and therefore needs
    to be called with a branched GL context
    """
    program = gl.createProgram()
    vertex_shader = await _ensure_shader(gl, vertex_shader_source, gl.VERTEX_SHADER)
    frag_shader = await _ensure_shader(gl, fragment_shader_source, gl.FRAGMENT_SHADER)

    with gl.chunk():
        gl.attachShader(program, vertex_shader)
        gl.attachShader(program, frag_shader)
        gl.linkProgram(program)

    status = gl.getProgramParameter(program, gl.LINK_STATUS)
    if not await status:
        log = gl.getProgramInfoLog(program)
        gl.deleteProgram(program)
        raise ValueError(
            'Unable to initialize the shader program: %s' % await log)
    return await program


def make_program(gl, vertex_shader_source, fragment_shader_source):
    f = asyncio.ensure_future(_ensure_program(
        gl.branch(), vertex_shader_source, fragment_shader_source))
    f._debug_repr_str = 'make_program'
    return f


def make_texture(gl, texture_data, gl_type):
    texture = gl.createTexture()
    gl.bindTexture(gl.TEXTURE_2D, texture)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl_type, texture_data)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
    gl.bindTexture(gl.TEXTURE_2D, None)
    return texture


# gluLookAt
def make_look_at(ex, ey, ez,
                 cx, cy, cz,
                 ux, uy, uz):
    eye = np.array([ex, ey, ez], dtype=np.float32)
    center = np.array([cx, cy, cz], dtype=np.float32)
    up = np.array([ux, uy, uz], dtype=np.float32)

    z = normalize(eye - center)
    x = normalize(np.cross(up, z))
    y = normalize(np.cross(z, x))

    m = np.array([np.pad(x, (0, 1), 'constant'),
                  np.pad(y, (0, 1), 'constant'),
                  np.pad(z, (0, 1), 'constant'),
                  [0, 0, 0, 1]], dtype=np.float32)

    t = np.array([[1, 0, 0, -ex],
                  [0, 1, 0, -ey],
                  [0, 0, 1, -ez],
                  [0, 0, 0, 1]], dtype=np.float32)
    return (m * t).T


# gluPerspective
def make_perspective(fovy, aspect, znear, zfar):
    ymax = znear * np.tan(fovy * np.pi / 360.0)
    ymin = -ymax
    xmin = ymin * aspect
    xmax = ymax * aspect

    return make_frustum(xmin, xmax, ymin, ymax, znear, zfar)


# glFrustum
def make_frustum(left, right, bottom, top, znear, zfar):
    X = 2 * znear / (right - left)
    Y = 2 * znear / (top - bottom)
    A = (right + left) / (right - left)
    B = (top + bottom) / (top - bottom)
    C = -(zfar + znear) / (zfar - znear)
    D = -2 * zfar * znear / (zfar - znear)

    return np.array([[X, 0, A, 0],
                     [0, Y, B, 0],
                     [0, 0, C, D],
                     [0, 0, -1, 0]], dtype=np.float32).T


# glOrtho
def make_ortho(left, right, bottom, top, znear, zfar):
    tx = - (right + left) / (right - left)
    ty = - (top + bottom) / (top - bottom)
    tz = - (zfar + znear) / (zfar - znear)

    return np.array([
        [2 / (right - left), 0, 0, tx],
        [0, 2 / (top - bottom), 0, ty],
        [0, 0, -2 / (zfar - znear), tz],
        [0, 0, 0, 1]], dtype=np.float32).T


def task_status():
    print("Status:")
    for task in asyncio.Task.all_tasks(asyncio.get_event_loop()):
        print('- %s\n' % _format_task(task).rstrip('\n'))


def _format_task(task):
    status = 'pending'
    if task.done():
        if task.cancelled():
            status = 'cancelled'
        elif task.exception() is not None:
            e = task.exception()
            return 'Task - error: %s' % (
                "".join(traceback.format_exception(
                    e.__class__,
                    e,
                    e.__traceback__
                )))
        else:
            status = 'success'
    if hasattr(task, '_coro'):
        return 'Task - %s: %s' % (status, task._coro)
    else:
        return 'Task - %s' % status


def calulate_tangents(vertices, normals, tex_coords, faces):
    """Calculate the tangents for a set of faces"""
    vertex_count = vertices.shape[0]
    tangents = np.zeros((vertex_count, 3))

    i1 = faces[:, 0]
    i2 = faces[:, 1]
    i3 = faces[:, 2]

    v1 = vertices[i1]
    v2 = vertices[i2]
    v3 = vertices[i3]

    w1 = tex_coords[i1]
    w2 = tex_coords[i2]
    w3 = tex_coords[i3]

    dv1 = v2 - v1
    dv2 = v3 - v2

    dw1 = w2 - w1
    dw2 = w3 - w2

    dw1u = dw1[:, 0]
    dw1v = dw1[:, 1]
    dw2u = dw2[:, 0]
    dw2v = dw2[:, 1]

    r = 1.0 / (dw1u * dw2v - dw1v * dw2u)
    sdir = ((dw2v * dv1.T - dw1v * dv2.T) * r).T

    tangents[i1] += sdir
    tangents[i2] += sdir
    tangents[i3] += sdir

     # Gram-Schmidt orthogonalize
    tangents[:] = normalize(tangents - (normals.T * inner1d(normals, tangents)).T)

    return tangents


def bump_map_to_normal_map(bump_map):
    gradient = np.gradient(bump_map.astype(np.float) / 255.)
    z = np.sqrt(1.0 - np.dot(gradient[0] ** 2, gradient[1] ** 2))
    gradient = np.array(gradient + [z])
    gradient = (127 * (1.0 + gradient)).astype(np.uint8)
    return np.rollaxis(gradient, 0, 3)
