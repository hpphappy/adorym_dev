import warnings
import os
import gc
import numpy as np

import adorym.global_settings as global_settings

engine_dict = {}
try:
    import autograd.numpy as anp
    import autograd as ag
    engine_dict['autograd'] = anp
except:
    warnings.warn('Autograd backend is not available.')
try:
    import torch as tc
    import torch.autograd as tag
    engine_dict['pytorch'] = tc
except:
    warnings.warn('PyTorch backend is not available.')


func_mapping_dict = {'zeros':       {'autograd': 'zeros',      'tensorflow': 'zeros',      'pytorch': 'zeros'},
                     'ones':        {'autograd': 'ones',       'tensorflow': 'ones',       'pytorch': 'ones'},
                     'zeros_like':  {'autograd': 'zeros_like', 'tensorflow': 'zeros_like', 'pytorch': 'zeros_like'},
                     'ones_like':   {'autograd': 'ones_like',  'tensorflow': 'ones_like',  'pytorch': 'ones_like'},
                     'stack':       {'autograd': 'stack',      'tensorflow': 'stack',      'pytorch': 'stack'},
                     'concatenate': {'autograd': 'concatenate','tensorflow': 'cat',        'pytorch': 'cat'},
                     'exp':         {'autograd': 'exp',        'tensorflow': 'exp',        'pytorch': 'exp'},
                     'log':         {'autograd': 'log',        'tensorflow': 'log',        'pytorch': 'log'},
                     'round':       {'autograd': 'round',      'tensorflow': 'round',      'pytorch': 'round'},
                     'clip':        {'autograd': 'clip',       'tensorflow': 'clip',       'pytorch': 'clamp'},
                     'reshape':     {'autograd': 'reshape',    'tensorflow': 'reshape',    'pytorch': 'reshape'},
                     'floor':       {'autograd': 'floor',      'tensorflow': 'floor',      'pytorch': 'floor'},
                     'ceil':        {'autograd': 'ceil',       'tensorflow': 'ceil',       'pytorch': 'ceil'},
                     'sqrt':        {'autograd': 'sqrt',       'tensorflow': 'sqrt',       'pytorch': 'sqrt'},
                     'real':        {'autograd': 'real',       'tensorflow': 'real',       'pytorch': 'real'},
                     'imag':        {'autograd': 'imag',       'tensorflow': 'imag',       'pytorch': 'imag'},
                     'sin':         {'autograd': 'sin',        'tensorflow': 'sin',        'pytorch': 'sin'},
                     'cos':         {'autograd': 'cos',        'tensorflow': 'cos',        'pytorch': 'cos'},
                     'abs':         {'autograd': 'abs',        'tensorflow': 'abs',        'pytorch': 'abs'},
                     'sum':         {'autograd': 'sum',        'tensorflow': 'reduce_sum', 'pytorch': 'sum'},
                     'prod':        {'autograd': 'prod',       'tensorflow': 'prod',       'pytorch': 'prod'},
                     'arctan2':     {'autograd': 'arctan2',    'tensorflow': 'atan2',      'pytorch': 'atan2'},
                     'nonzero':     {'autograd': 'nonzero',    'tensorflow': 'nonzero',      'pytorch': 'nonzero'},
                     }

dtype_mapping_dict = {'float32':    {'autograd': 'float32',    'tensorflow': 'float32',    'pytorch': 'float'},
                      'float64':    {'autograd': 'float64',    'tensorflow': 'float64',    'pytorch': 'double'},
                      'float16':    {'autograd': 'float16',    'tensorflow': 'float16',    'pytorch': 'half'},
                      'int8':       {'autograd': 'int8',       'tensorflow': 'int8',       'pytorch': 'int8'},
                      'int16':      {'autograd': 'int16',      'tensorflow': 'int16',      'pytorch': 'short'},
                      'int32':      {'autograd': 'int32',      'tensorflow': 'int32',      'pytorch': 'int'},
                      'int64':      {'autograd': 'int64',      'tensorflow': 'int64',      'pytorch': 'long'},
                      'bool':       {'autograd': 'bool',       'tensorflow': 'bool',       'pytorch': 'bool'},
                      }

# _____________
# |Flow control|_____________________________________________________________

class EmptyWith(object):
    def __init__(self):
        pass

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, tb):
        pass

def create_variable(arr, dtype=None, device=None, requires_grad=True, override_backend=None):
    """
    Create a variable wrapper.
    :param arr: Numpy array of the intial value.
    :param dtype: str; Data type.
    :param device: A device object from PyTorch, etc. Use None for CPU.
    """
    bn = override_backend if override_backend is not None else global_settings.backend
    args = {}
    if bn == 'autograd':
        if dtype is not None:
            args['dtype'] = dtype_mapping_dict[dtype]['autograd']
        var = anp.array(arr, **args)
    elif bn == 'pytorch':
        if dtype is not None:
            args['dtype'] = getattr(engine_dict['pytorch'], dtype_mapping_dict[dtype]['pytorch'])
        if device is not None:
            args['device'] = device
        args['requires_grad'] = requires_grad
        var = tc.tensor(arr, **args)
    return var


def to_numpy(var):
    if isinstance(var, np.ndarray):
        return var
    else:
        if global_settings.backend == 'autograd':
            return var._value
        elif global_settings.backend == 'pytorch':
            if var.device.type == 'cpu':
                return var.data.numpy()
            else:
                return var.cpu().data.numpy()


def get_device(index=None):
    """
    Get device object.
    :param index: index of GPU. Set to None if the tensor is kept on host.
    """
    if global_settings.backend == 'autograd': return None
    elif global_settings.backend == 'pytorch':
        if index is None: return None
        else:
            return tc.device('cuda:{}'.format(index))


def prepare_loss_node(loss, opt_args_ls=None):
    if global_settings.backend == 'autograd':
        return ag.grad(loss, opt_args_ls)
    elif global_settings.backend == 'pytorch':
        return loss


def get_gradients(loss_node, opt_args_ls=None, **kwargs):
    if global_settings.backend == 'autograd':
        # For Autograd, loss_node is the grad function that takes the loss function arguments and
        # returns the gradients.
        return loss_node(*list(kwargs.values()))
    elif global_settings.backend == 'pytorch':
        # For PyTorch, loss_node is the loss function itself.
        l = loss_node(**kwargs)
        kwargs_ls = list(kwargs.values())
        dx_ls = []
        for i, node in enumerate(kwargs_ls):
            if i in opt_args_ls: dx_ls.append(node)
        grads = tag.grad(l, dx_ls, retain_graph=True, create_graph=False)
        # grads = []
        # l.backward(retain_graph=True)
        # for n in dx_ls:
        #     print(n.grad)
        #     grads.append(n.grad)
        l.detach()
        del l

        return grads


def get_gpu_memory_usage_mb():
    if global_settings.backend == 'autograd':
        return 0
    elif global_settings.backend == 'pytorch':
        return tc.cuda.memory_allocated() / 1024 ** 2


def get_gpu_memory_cache_mb():
    if global_settings.backend == 'autograd':
        return 0
    elif global_settings.backend == 'pytorch':
        return tc.cuda.memory_cached() / 1024 ** 2


def get_peak_gpu_memory_usage_mb():
    if global_settings.backend == 'autograd':
        return 0
    elif global_settings.backend == 'pytorch':
        return tc.cuda.max_memory_allocated() / 1024 ** 2

def collect_gpu_garbage():
    if global_settings.backend == 'autograd':
        pass
    elif global_settings.backend == 'pytorch':
        tc.cuda.empty_cache()

def get_allocated_tensors():

    def _getr(slist, olist, seen):
        for e in slist:
            if id(e) in seen:
                continue
            seen[id(e)] = None
            olist.append(e)
            tl = gc.get_referents(e)
            if tl:
                _getr(tl, olist, seen)

    def get_all_objects():
        """Return a list of all live Python
        objects, not including the list itself."""
        gcl = gc.get_objects()
        olist = []
        seen = {}
        # Just in case:
        seen[id(gcl)] = None
        seen[id(olist)] = None
        seen[id(seen)] = None
        # _getr does the real work.
        _getr(gcl, olist, seen)
        return olist

    if global_settings.backend == 'pytorch':
        objects = get_all_objects()
        for obj in objects:
            try:
                if tc.is_tensor(obj) or (hasattr(obj, 'data') and tc.is_tensor(obj.data)):
                    print(type(obj), obj.shape, obj.device)
            except:
                pass

def no_grad():
    if global_settings.backend == 'pytorch':
        return tc.no_grad()
    else:
        return EmptyWith()

def reattach(var):
    if global_settings.backend == 'pytorch':
        var.requires_grad_()
        return var
    else:
        return var

# ________________
# |Maths functions|_____________________________________________________________

def zeros(shape, dtype=None, device=None, requires_grad=True):
    kwargs = {}
    if dtype is not None: kwargs['dtype'] = dtype
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['zeros'][global_settings.backend])
    if global_settings.backend == 'pytorch':
        arr = func(shape, device=device, requires_grad=requires_grad, **kwargs)
    else:
        arr = func(shape, **kwargs)
    return arr


def ones(shape, dtype=None, device=None, requires_grad=True):
    kwargs = {}
    if dtype is not None: kwargs['dtype'] = dtype
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['ones'][global_settings.backend])
    if global_settings.backend == 'pytorch':
        arr = func(shape, device=device, requires_grad=requires_grad, **kwargs)
    else:
        arr = func(shape, **kwargs)
    return arr


def zeros_like(var, dtype=None, device=None, requires_grad=True):
    """
    :param var: ADVariable or tensor.
    """
    kwargs = {}
    if dtype is not None: kwargs['dtype'] = dtype
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['zeros_like'][global_settings.backend])
    if global_settings.backend == 'pytorch':
        arr = func(var, device=device, requires_grad=requires_grad, **kwargs)
    else:
        arr = func(var, **kwargs)
    return arr


def ones_like(var, dtype=None, device=None, requires_grad=True):
    """
    :param var: ADVariable or tensor.
    """
    kwargs = {}
    if dtype is not None: kwargs['dtype'] = dtype
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['ones_like'][global_settings.backend])
    if global_settings.backend == 'pytorch':
        arr = func(var, device=device, requires_grad=requires_grad, **kwargs)
    else:
        arr = func(var, **kwargs)
    return arr


def exp(var):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['exp'][global_settings.backend])
    arr = func(var)
    return arr


def log(var):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['log'][global_settings.backend])
    arr = func(var)
    return arr


def sin(var):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['sin'][global_settings.backend])
    arr = func(var)
    return arr


def cos(var):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['cos'][global_settings.backend])
    arr = func(var)
    return arr


def exp_complex(var_real, var_imag):
    if global_settings.backend == 'pytorch':
        if not isinstance(var_real, tc.Tensor):
            var_real = tc.tensor(var_real)
        if not isinstance(var_imag, tc.Tensor):
            var_real = tc.tensor(var_imag)
    e = exp(var_real)
    return e * cos(var_imag), e * sin(var_imag)


def abs(var):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['abs'][global_settings.backend])
    arr = func(var)
    return arr


def stack(var_list, axis=0, override_backend=None):
    bn = override_backend if override_backend is not None else global_settings.backend
    func = getattr(engine_dict[bn], func_mapping_dict['stack'][bn])
    arr = func(var_list, axis)
    return arr


def concatenate(var_list, axis=0):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['concatenate'][global_settings.backend])
    arr = func(var_list, axis)
    return arr


def cast(var, dtype, override_backend=None):
    bn = override_backend if override_backend is not None else global_settings.backend
    dtype = str(dtype)
    if bn == 'autograd':
        return var.astype(dtype)
    elif bn == 'pytorch':
        return getattr(var, dtype_mapping_dict[dtype]['pytorch'])()


def round(var, override_backend=None):
    bn = override_backend if override_backend is not None else global_settings.backend
    func = getattr(engine_dict[bn], func_mapping_dict['round'][bn])
    arr = func(var)
    return arr


def round_and_cast(var, dtype='int32', override_backend=None):
    return cast(round(var), dtype=dtype, override_backend=override_backend)


def fft2(var_real, var_imag, axes=(-2, -1), override_backend=None, normalize=False):
    bn = override_backend if override_backend is not None else global_settings.backend
    if bn == 'autograd':
        var = var_real + 1j * var_imag
        norm = None if not normalize else 'ortho'
        var = anp.fft.fft2(var, axes=axes, norm=norm)
        return anp.real(var), anp.imag(var)
    elif bn == 'pytorch':
        var = tc.stack([var_real, var_imag], axis=-1)
        var = tc.fft(var, signal_ndim=2, normalized=normalize)
        var_real, var_imag = tc.split(var, 1, dim=-1)
        slicer = [slice(None)] * (var_real.ndim - 1) + [0]
        return var_real[tuple(slicer)], var_imag[tuple(slicer)]


def ifft2(var_real, var_imag, axes=(-2, -1), override_backend=None, normalize=False):
    bn = override_backend if override_backend is not None else global_settings.backend
    if bn == 'autograd':
        var = var_real + 1j * var_imag
        norm = None if not normalize else 'ortho'
        var = anp.fft.ifft2(var, axes=axes, norm=norm)
        return anp.real(var), anp.imag(var)
    elif bn == 'pytorch':
        var = tc.stack([var_real, var_imag], axis=-1)
        var = tc.ifft(var, signal_ndim=2, normalized=normalize)
        var_real, var_imag = tc.split(var, 1, dim=-1)
        slicer = [slice(None)] * (var_real.ndim - 1) + [0]
        return var_real[tuple(slicer)], var_imag[tuple(slicer)]


def fft2_and_shift(var_real, var_imag, axes=(-2, -1), override_backend=None, normalize=False):
    bn = override_backend if override_backend is not None else global_settings.backend
    if bn == 'autograd':
        var = var_real + 1j * var_imag
        norm = None if not normalize else 'ortho'
        var = anp.fft.fftshift(anp.fft.fft2(var, axes=axes, norm=norm), axes=axes)
        return anp.real(var), anp.imag(var)
    elif bn == 'pytorch':
        var = tc.stack([var_real, var_imag], dim=-1)
        var = tc.fft(var, signal_ndim=2, normalized=normalize)
        var_real, var_imag = tc.split(var, 1, dim=-1)
        slicer = [slice(None)] * (var_real.ndim - 1) + [0]
        var_real = var_real[tuple(slicer)]
        var_imag = var_imag[tuple(slicer)]
        var_real = fftshift(var_real, axes=axes)
        var_imag = fftshift(var_imag, axes=axes)
        return var_real, var_imag


def ifft2_and_shift(var_real, var_imag, axes=(-2, -1), override_backend=None, normalize=False):
    bn = override_backend if override_backend is not None else global_settings.backend
    if bn == 'autograd':
        var = var_real + 1j * var_imag
        norm = None if not normalize else 'ortho'
        var = anp.fft.fftshift(anp.fft.ifft2(var, axes=axes, norm=norm), axes=axes)
        return anp.real(var), anp.imag(var)
    elif bn == 'pytorch':
        var = tc.stack([var_real, var_imag], dim=-1)
        var = tc.ifft(var, signal_ndim=2, normalized=normalize)
        var_real, var_imag = tc.split(var, 1, dim=-1)
        slicer = [slice(None)] * (var_real.ndim - 1) + [0]
        var_real = var_real[tuple(slicer)]
        var_imag = var_imag[tuple(slicer)]
        var_real = fftshift(var_real, axes=axes)
        var_imag = fftshift(var_imag, axes=axes)
        return var_real, var_imag


def ishift_and_ifft2(var_real, var_imag, axes=(-2, -1), override_backend=None, normalize=False):
    bn = override_backend if override_backend is not None else global_settings.backend
    if bn == 'autograd':
        var = var_real + 1j * var_imag
        norm = None if not normalize else 'ortho'
        var = anp.fft.ifft2(anp.fft.ifftshift(var, axes=axes), axes=axes, norm=norm)
        return anp.real(var), anp.imag(var)
    elif bn == 'pytorch':
        var_real = ifftshift(var_real, axes=axes)
        var_imag = ifftshift(var_imag, axes=axes)
        var = tc.stack([var_real, var_imag], dim=-1)
        var = tc.ifft(var, signal_ndim=2, normalized=normalize)
        var_real, var_imag = tc.split(var, 1, dim=-1)
        slicer = [slice(None)] * (var_real.ndim - 1) + [0]
        var_real = var_real[tuple(slicer)]
        var_imag = var_imag[tuple(slicer)]
        return var_real, var_imag


def convolve_with_transfer_function(arr_real, arr_imag, h_real, h_imag, axes=(-2, -1), override_backend=None):
    f_real, f_imag = fft2(arr_real, arr_imag, axes=axes, override_backend=override_backend)
    fh_real = f_real * h_real - f_imag * h_imag
    fh_imag = f_real * h_imag + f_imag * h_real
    return ifft2(fh_real, fh_imag, override_backend=override_backend)


def convolve_with_impulse_response(arr_real, arr_imag, h_real, h_imag, axes=(-2, -1), override_backend=None):
    f_real, f_imag = fft2(arr_real, arr_imag, axes=axes, override_backend=override_backend)
    h_real, h_imag = fft2(h_real, h_imag, override_backend=override_backend)
    fh_real = f_real * h_real - f_imag * h_imag
    fh_imag = f_real * h_imag + f_imag * h_real
    return ifft2(fh_real, fh_imag, override_backend=override_backend)


def fftshift(var, axes=(1, 2), override_backend=None):
    """
    :param var: [N, H, W, 2], where the last dimension represents real and imaginary parts.
    """
    bn = override_backend if override_backend is not None else global_settings.backend
    if bn == 'autograd':
        return anp.fft.fftshift(var, axes=axes)
    elif bn == 'pytorch':
        s = var.shape
        for i in axes:
            p2 = (s[i] + 1) // 2
            v = tc.split(var, p2, dim=i)
            if len(v) == 3:
                v1, v2 = (v[0], tc.cat([v[1], v[2]], dim=i))
            else:
                v1, v2 = v
            var = tc.cat([v2, v1], dim=i)
        return var


def ifftshift(var, axes=(1, 2), override_backend=None):
    """
    :param var: [N, H, W, 2], where the last dimension represents real and imaginary parts.
    """
    bn = override_backend if override_backend is not None else global_settings.backend
    if bn == 'autograd':
        return anp.fft.ifftshift(var, axes=axes)
    elif bn == 'pytorch':
        s = var.shape
        for i in axes:
            p2 = s[i] - (s[i] + 1) // 2
            v = tc.split(var, p2, dim=i)
            if len(v) == 3:
                v1, v2 = (v[0], tc.cat([v[1], v[2]], dim=i))
            else:
                v1, v2 = v
            var = tc.cat([v2, v1], dim=i)
        return var


def split_channel(var, override_backend=None):
    bn = override_backend if override_backend is not None else global_settings.backend
    if bn == 'autograd':
        var0, var1 = anp.split(var, var.shape[-1], axis=-1)
        slicer = [slice(None)] * (var.ndim - 1) + [0]
        return var0[tuple(slicer)], var1[tuple(slicer)]
    elif bn == 'pytorch':
        var0, var1 = tc.split(var, 1, dim=-1)
        slicer = [slice(None)] * (var.ndim - 1) + [0]
        return var0[tuple(slicer)], var1[tuple(slicer)]
   
    
def clip(var, a1, a2, override_backend=None):
    bn = override_backend if override_backend is not None else global_settings.backend
    func = getattr(engine_dict[bn], func_mapping_dict['clip'][bn])
    if bn == 'pytorch':
        if not isinstance(var, tc.Tensor):
            var = tc.tensor(var)
    arr = func(var, a1, a2)
    return arr


def reshape(var, newshape, override_backend=None):
    bn = override_backend if override_backend is not None else global_settings.backend
    func = getattr(engine_dict[bn], func_mapping_dict['reshape'][bn])
    arr = func(var, newshape)
    return arr


def floor(var, override_backend=None):
    bn = override_backend if override_backend is not None else global_settings.backend
    func = getattr(engine_dict[bn], func_mapping_dict['floor'][bn])
    arr = func(var)
    return arr


def floor_and_cast(var, dtype='int32', override_backend=None):
    return cast(floor(var, override_backend=override_backend), dtype=dtype, override_backend=override_backend)


def ceil(var, override_backend=None):
    bn = override_backend if override_backend is not None else global_settings.backend
    func = getattr(engine_dict[bn], func_mapping_dict['ceil'][bn])
    arr = func(var)
    return arr


def ceil_and_cast(var, dtype='int32', override_backend=None):
    return cast(ceil(var, override_backend=override_backend), dtype=dtype, override_backend=override_backend)


def sqrt(var):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['sqrt'][global_settings.backend])
    arr = func(var)
    return arr


def mean(var, axis=None):
    args = {}
    if axis is not None:
        args['dim'] = axis
    if global_settings.backend == 'autograd':
        return anp.mean(var, **args)
    elif global_settings.backend == 'pytorch':
        return tc.mean(var, **args)


def max(var, return_number=True, axis=None):
    if global_settings.backend == 'autograd':
        a = anp.max(var, axis=axis)
    elif global_settings.backend == 'pytorch':
        if axis is None:
            a = tc.max(var)
            if return_number:
                a = float(to_numpy(a))
        else:
            a = tc.max(var, dim=axis)
    return a


def min(var, return_number=True, axis=None):
    if global_settings.backend == 'autograd':
        a = anp.min(var, axis=axis)
    elif global_settings.backend == 'pytorch':
        if axis is None:
            a = tc.min(var)
            if return_number:
                a = float(to_numpy(a))
        else:
            a = tc.min(var, dim=axis)
    return a


def real(var, override_backend=None):
    bn = override_backend if override_backend is not None else global_settings.backend
    func = getattr(engine_dict[bn], func_mapping_dict['real'][bn])
    arr = func(var)
    return arr


def imag(var, override_backend=None):
    bn = override_backend if override_backend is not None else global_settings.backend
    func = getattr(engine_dict[bn], func_mapping_dict['imag'][bn])
    arr = func(var)
    return arr


def tile(var, cp):
    if global_settings.backend == 'autograd':
        return anp.tile(var, cp)
    elif global_settings.backend == 'pytorch':
        return var.repeat(*cp)


def pad(var, pad_len, mode='constant', constant_values=0, override_backend=None):
    """
    :param pad_len: A tuple of tuples. Consistent with the format of numpy.pad.
    :param mode: Choose from 'constant', 'reflect'.
    """
    bn = override_backend if override_backend is not None else global_settings.backend
    args = {}
    if mode == 'constant':
        args['constant_values'] = 0
    if bn == 'autograd':
        return anp.pad(var, pad_len, mode=mode, **args)
    elif bn == 'pytorch':
        pad_len = [x for y in pad_len[::-1] for x in y]
        return tc.nn.functional.pad(var, pad_len, mode=mode, value=constant_values)
    elif bn == 'numpy':
        return np.pad(var, pad_len, mode=mode, **args)


def sum(var, axis=None):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['sum'][global_settings.backend])
    if global_settings.backend == 'autograd':
        arr = func(var, axis=axis)
    elif global_settings.backend == 'pytorch':
        if axis is None:
            arr = tc.sum(var)
        else:
            arr = tc.sum(var, dim=axis)
    return arr


def prod(var, axis=None):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['prod'][global_settings.backend])
    if global_settings.backend == 'autograd':
        args = {}
        if axis is not None:
            args['axis'] = axis
        arr = func(var, **args)
    elif global_settings.backend == 'pytorch':
        args = {}
        if axis is not None:
            args['dim'] = axis
        arr = tc.prod(var, **args)
    return arr


def roll(var, shifts, axes=0):
    if global_settings.backend == 'autograd':
        return anp.roll(var, shifts, axis=axes)
    elif global_settings.backend == 'pytorch':
        return tc.roll(var, shifts, dims=axes)


def arctan2(var1, var2):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['arctan2'][global_settings.backend])
    arr = func(var1, var2)
    return arr


def nonzero(var):
    func = getattr(engine_dict[global_settings.backend], func_mapping_dict['nonzero'][global_settings.backend])
    arr = func(var)
    return arr


def norm(var_real, var_imag):
    if global_settings.backend == 'autograd':
        return abs(var_real + 1j * var_imag)
    elif global_settings.backend == 'pytorch':
        return tc.norm(tc.stack([var_real, var_imag], dim=0), dim=0)


def swap_axes(arr, axes=(0, 1)):
    if global_settings.backend == 'autograd':
        if axes[0] < axes[1]:
            axes = [axes[1], axes[0]]
        axes = list(range(min(axes))) + axes + list(range(max(axes) + 1, len(arr.shape)))
        return anp.tranpose(arr, axes)
    elif global_settings.backend == 'pytorch':
        return tc.transpose(arr, axes[0], axes[1])