'''
Author       : Thyssen Wen
Date         : 2022-05-11 19:04:30
LastEditors  : Thyssen Wen
LastEditTime : 2022-10-27 21:09:40
Description  : MoViNet model ref:https://github.com/Atze00/MoViNet-pytorch/blob/main/movinets/models.py
FilePath     : /SVTAS/svtas/model/backbones/video/movinet.py
'''
from ast import List
from collections import OrderedDict
import torch
from torch.nn.modules.utils import _triple, _pair
import torch.nn.functional as F
from mmcv.runner import load_checkpoint
from typing import Any, Callable, Optional, Tuple, Union
from einops import rearrange
from torch import nn, Tensor
from ....utils.logger import get_logger
from ...builder import BACKBONES

class ObjectDict(dict):
    def __getattr__(self, item):
        val = self.__getitem__(item)
        if isinstance(val, dict):
            return self.__class__(**val)
        elif isinstance(val, list):
            return [self.__class__(**d) for d in val]
        else:
            return val

def get_movinet_config(name):
    if name not in ["A0", "A1", "A2"]:
            raise ValueError("Only A0,A1,A2 networks are available reproducted")
    if name in ["A0"]:
        conv1 = {"input_channels": 3, "out_channels": 8, "kernel_size": (1, 3, 3), "stride": (1, 2, 2), "padding": (0, 1, 1)}
        blocks = [
            [{"input_channels": 8, "out_channels": 8, "expanded_channels": 24, "kernel_size": (1, 5, 5), "stride": (1, 2, 2), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)}],

            [{"input_channels": 8, "out_channels": 32, "expanded_channels": 80, "kernel_size": (3, 3, 3), "stride": (1, 2, 2), "padding": (1, 0, 0), "padding_avg": (0, 1, 1)},
             {"input_channels": 32, "out_channels": 32, "expanded_channels": 80, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 32, "out_channels": 32, "expanded_channels": 80, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],

            [{"input_channels": 32, "out_channels": 56, "expanded_channels": 184, "kernel_size": (5, 3, 3), "stride": (1, 2, 2), "padding": (2, 0, 0), "padding_avg": (0, 1, 1)},
             {"input_channels": 56, "out_channels": 56, "expanded_channels": 112, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 56, "out_channels": 56, "expanded_channels": 184, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],

            [{"input_channels": 56, "out_channels": 56, "expanded_channels": 184, "kernel_size": (5, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 56, "out_channels": 56, "expanded_channels": 184, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 56, "out_channels": 56, "expanded_channels": 184, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 56, "out_channels": 56, "expanded_channels": 184, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],

            [{"input_channels": 56, "out_channels": 104, "expanded_channels": 384, "kernel_size": (5, 3, 3), "stride": (1, 2, 2), "padding": (2, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 104, "out_channels": 104, "expanded_channels": 280, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 104, "out_channels": 104, "expanded_channels": 280, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 104, "out_channels": 104, "expanded_channels": 344, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)}]
        ]
        conv7 = {"input_channels": 104, "out_channels": 480, "kernel_size": (1, 1, 1), "stride": (1, 1, 1), "padding": (0, 0, 0)}
    elif name in ["A1"]:
        conv1 = {"input_channels": 3, "out_channels": 16, "kernel_size": (1, 3, 3), "stride": (1, 2, 2), "padding": (0, 1, 1)}
        blocks = [
            [{"input_channels": 16, "out_channels": 16, "expanded_channels": 40, "kernel_size": (1, 5, 5), "stride": (1, 2, 2), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 16, "out_channels": 16, "expanded_channels": 40, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],

            [{"input_channels": 16, "out_channels": 40, "expanded_channels": 96, "kernel_size": (3, 3, 3), "stride": (1, 2, 2), "padding": (1, 0, 0), "padding_avg": (0, 0, 0)},
             {"input_channels": 40, "out_channels": 40, "expanded_channels": 120, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 40, "out_channels": 40, "expanded_channels": 96, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 40, "out_channels": 40, "expanded_channels": 96, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],

            [{"input_channels": 40, "out_channels": 64, "expanded_channels": 216, "kernel_size": (5, 3, 3), "stride": (1, 2, 2), "padding": (2, 0, 0), "padding_avg": (0, 0, 0)},
             {"input_channels": 64, "out_channels": 64, "expanded_channels": 128, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 64, "out_channels": 64, "expanded_channels": 216, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 64, "out_channels": 64, "expanded_channels": 168, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 64, "out_channels": 64, "expanded_channels": 216, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],
             
            [{"input_channels": 64, "out_channels": 64, "expanded_channels": 216, "kernel_size": (5, 3, 3), "stride": (1, 1, 1), "padding": (2, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 64, "out_channels": 64, "expanded_channels": 216, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 64, "out_channels": 64, "expanded_channels": 216, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 64, "out_channels": 64, "expanded_channels": 128, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 64, "out_channels": 64, "expanded_channels": 128, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 64, "out_channels": 64, "expanded_channels": 216, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],

            [{"input_channels": 64, "out_channels": 136, "expanded_channels": 456, "kernel_size": (5, 3, 3), "stride": (1, 2, 2), "padding": (2, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 136, "out_channels": 136, "expanded_channels": 360, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 136, "out_channels": 136, "expanded_channels": 360, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 136, "out_channels": 136, "expanded_channels": 360, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 136, "out_channels": 136, "expanded_channels": 456, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 136, "out_channels": 136, "expanded_channels": 456, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 136, "out_channels": 136, "expanded_channels": 544, "kernel_size": (1, 3, 3), "stride": (1, 1, 1), "padding": (0, 1, 1), "padding_avg": (0, 1, 1)}]
        ]
        conv7 = {"input_channels": 136, "out_channels": 600, "kernel_size": (1, 1, 1), "stride": (1, 1, 1), "padding": (0, 0, 0)}
    elif name in ["A2"]:
        conv1 = {"input_channels": 3, "out_channels": 16, "kernel_size": (1, 3, 3), "stride": (1, 2, 2), "padding": (0, 1, 1)}
        blocks = [
            [{"input_channels": 16, "out_channels": 16, "expanded_channels": 40, "kernel_size": (1, 5, 5), "stride": (1, 2, 2), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 16, "out_channels": 16, "expanded_channels": 40, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 16, "out_channels": 16, "expanded_channels": 64, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],

            [{"input_channels": 16, "out_channels": 40, "expanded_channels": 96, "kernel_size": (3, 3, 3), "stride": (1, 2, 2), "padding": (1, 0, 0), "padding_avg": (0, 0, 0)},
             {"input_channels": 40, "out_channels": 40, "expanded_channels": 120, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 40, "out_channels": 40, "expanded_channels": 96, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 40, "out_channels": 40, "expanded_channels": 96, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 40, "out_channels": 40, "expanded_channels": 120, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],

            [{"input_channels": 40, "out_channels": 72, "expanded_channels": 240, "kernel_size": (5, 3, 3), "stride": (1, 2, 2), "padding": (2, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 72, "out_channels": 72, "expanded_channels": 160, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 72, "out_channels": 72, "expanded_channels": 240, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 72, "out_channels": 72, "expanded_channels": 192, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 72, "out_channels": 72, "expanded_channels": 240, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],
             
            [{"input_channels": 72, "out_channels": 72, "expanded_channels": 240, "kernel_size": (5, 3, 3), "stride": (1, 1, 1), "padding": (2, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 72, "out_channels": 72, "expanded_channels": 240, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 72, "out_channels": 72, "expanded_channels": 240, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 72, "out_channels": 72, "expanded_channels": 240, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 72, "out_channels": 72, "expanded_channels": 144, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 72, "out_channels": 72, "expanded_channels": 240, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)}],

            [{"input_channels": 72, "out_channels": 144, "expanded_channels": 480, "kernel_size": (5, 3, 3), "stride": (1, 2, 2), "padding": (2, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 144, "out_channels": 144, "expanded_channels": 384, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 144, "out_channels": 144, "expanded_channels": 384, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 144, "out_channels": 144, "expanded_channels": 480, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 144, "out_channels": 144, "expanded_channels": 480, "kernel_size": (1, 5, 5), "stride": (1, 1, 1), "padding": (0, 2, 2), "padding_avg": (0, 1, 1)},
             {"input_channels": 144, "out_channels": 144, "expanded_channels": 480, "kernel_size": (3, 3, 3), "stride": (1, 1, 1), "padding": (1, 1, 1), "padding_avg": (0, 1, 1)},
             {"input_channels": 144, "out_channels": 144, "expanded_channels": 576, "kernel_size": (1, 3, 3), "stride": (1, 1, 1), "padding": (0, 1, 1), "padding_avg": (0, 1, 1)}]
        ]
        conv7 = {"input_channels": 144, "out_channels": 640, "kernel_size": (1, 1, 1), "stride": (1, 1, 1), "padding": (0,0,0)}
    
    conv1 = ObjectDict(conv1)
    blocks = [[ObjectDict(blocks[i][j]) for j in range(len(blocks[i]))] for i in range(len(blocks))]
    conv7 = ObjectDict(conv7)
    return conv1, blocks, conv7
    
class Hardsigmoid(nn.Module):
    def __init__(self) -> None:
        super().__init__()

    def forward(self, x: Tensor) -> Tensor:
        x = (0.2 * x + 0.5).clamp(min=0.0, max=1.0)
        return x


class Swish(nn.Module):
    def __init__(self) -> None:
        super().__init__()

    def forward(self, x: Tensor) -> Tensor:
        return x * torch.sigmoid(x)


class CausalModule(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.activation = None

    def reset_activation(self) -> None:
        self.activation = None


class TemporalCGAvgPool3D(CausalModule):
    def __init__(self,) -> None:
        super().__init__()
        self.n_cumulated_values = 0
        self.register_forward_hook(self._detach_activation)

    def forward(self, x: Tensor) -> Tensor:
        input_shape = x.shape
        device = x.device
        cumulative_sum = torch.cumsum(x, dim=2)
        if self.activation is None:
            self.activation = cumulative_sum[:, :, -1:].clone()
        else:
            cumulative_sum += self.activation
            self.activation = cumulative_sum[:, :, -1:].clone()
        divisor = (torch.arange(1, input_shape[2]+1,
                   device=device)[None, None, :, None, None]
                   .expand(x.shape))
        x = cumulative_sum / (self.n_cumulated_values + divisor)
        self.n_cumulated_values += input_shape[2]
        return x

    @staticmethod
    def _detach_activation(module: CausalModule,
                           input: Tensor,
                           output: Tensor) -> None:
        module.activation.detach_()

    def reset_activation(self) -> None:
        super().reset_activation()
        self.n_cumulated_values = 0


class Conv2dBNActivation(nn.Sequential):
    def __init__(
                 self,
                 in_planes: int,
                 out_planes: int,
                 *,
                 kernel_size: Union[int, Tuple[int, int]],
                 padding: Union[int, Tuple[int, int]],
                 stride: Union[int, Tuple[int, int]] = 1,
                 groups: int = 1,
                 norm_layer: Optional[Callable[..., nn.Module]] = None,
                 activation_layer: Optional[Callable[..., nn.Module]] = None,
                 **kwargs: Any,
                 ) -> None:
        kernel_size = _pair(kernel_size)
        stride = _pair(stride)
        padding = _pair(padding)
        if norm_layer is None:
            norm_layer = nn.Identity
        if activation_layer is None:
            activation_layer = nn.Identity
        self.kernel_size = kernel_size
        self.stride = stride
        dict_layers = OrderedDict({
                            "conv2d": nn.Conv2d(in_planes, out_planes,
                                                kernel_size=kernel_size,
                                                stride=stride,
                                                padding=padding,
                                                groups=groups,
                                                **kwargs),
                            "norm": norm_layer(out_planes, eps=0.001),
                            "act": activation_layer()
                            })

        self.out_channels = out_planes
        super(Conv2dBNActivation, self).__init__(dict_layers)


class Conv3DBNActivation(nn.Sequential):
    def __init__(
                 self,
                 in_planes: int,
                 out_planes: int,
                 *,
                 kernel_size: Union[int, Tuple[int, int, int]],
                 padding: Union[int, Tuple[int, int, int]],
                 stride: Union[int, Tuple[int, int, int]] = 1,
                 groups: int = 1,
                 norm_layer: Optional[Callable[..., nn.Module]] = None,
                 activation_layer: Optional[Callable[..., nn.Module]] = None,
                 **kwargs: Any,
                 ) -> None:
        kernel_size = _triple(kernel_size)
        stride = _triple(stride)
        padding = _triple(padding)
        if norm_layer is None:
            norm_layer = nn.Identity
        if activation_layer is None:
            activation_layer = nn.Identity
        self.kernel_size = kernel_size
        self.stride = stride

        dict_layers = OrderedDict({
                                "conv3d": nn.Conv3d(in_planes, out_planes,
                                                    kernel_size=kernel_size,
                                                    stride=stride,
                                                    padding=padding,
                                                    groups=groups,
                                                    **kwargs),
                                "norm": norm_layer(out_planes, eps=0.001),
                                "act": activation_layer()
                                })

        self.out_channels = out_planes
        super(Conv3DBNActivation, self).__init__(dict_layers)


class ConvBlock3D(CausalModule):
    def __init__(
            self,
            in_planes: int,
            out_planes: int,
            *,
            kernel_size: Union[int, Tuple[int, int, int]],
            tf_like: bool,
            causal: bool,
            conv_type: str,
            padding: Union[int, Tuple[int, int, int]] = 0,
            stride: Union[int, Tuple[int, int, int]] = 1,
            norm_layer: Optional[Callable[..., nn.Module]] = None,
            activation_layer: Optional[Callable[..., nn.Module]] = None,
            bias: bool = False,
            **kwargs: Any,
            ) -> None:
        super().__init__()
        kernel_size = _triple(kernel_size)
        stride = _triple(stride)
        padding = _triple(padding)
        self.conv_2 = None
        if tf_like:
            # We neek odd kernel to have even padding
            # and stride == 1 to precompute padding,
            if kernel_size[0] % 2 == 0:
                raise ValueError('tf_like supports only odd'
                                 + ' kernels for temporal dimension')
            padding = ((kernel_size[0]-1)//2, 0, 0)
            if stride[0] != 1:
                raise ValueError('illegal stride value, tf like supports'
                                 + ' only stride == 1 for temporal dimension')
            if stride[1] > kernel_size[1] or stride[2] > kernel_size[2]:
                # these values are not tested so should be avoided
                raise ValueError('tf_like supports only'
                                 + '  stride <= of the kernel size')

        if causal is True:
            padding = (0, padding[1], padding[2])
        if conv_type != "2plus1d" and conv_type != "3d":
            raise ValueError("only 2plus2d or 3d are "
                             + "allowed as 3d convolutions")

        if conv_type == "2plus1d":
            self.conv_1 = Conv2dBNActivation(in_planes,
                                             out_planes,
                                             kernel_size=(kernel_size[1],
                                                          kernel_size[2]),
                                             padding=(padding[1],
                                                      padding[2]),
                                             stride=(stride[1], stride[2]),
                                             activation_layer=activation_layer,
                                             norm_layer=norm_layer,
                                             bias=bias,
                                             **kwargs)
            if kernel_size[0] > 1:
                self.conv_2 = Conv2dBNActivation(in_planes,
                                                 out_planes,
                                                 kernel_size=(kernel_size[0],
                                                              1),
                                                 padding=(padding[0], 0),
                                                 stride=(stride[0], 1),
                                                 activation_layer=activation_layer,
                                                 norm_layer=norm_layer,
                                                 bias=bias,
                                                 **kwargs)
        elif conv_type == "3d":
            self.conv_1 = Conv3DBNActivation(in_planes,
                                             out_planes,
                                             kernel_size=kernel_size,
                                             padding=padding,
                                             activation_layer=activation_layer,
                                             norm_layer=norm_layer,
                                             stride=stride,
                                             bias=bias,
                                             **kwargs)
        self.padding = padding
        self.kernel_size = kernel_size
        self.dim_pad = self.kernel_size[0]-1
        self.stride = stride
        self.causal = causal
        self.conv_type = conv_type
        self.tf_like = tf_like

    def _forward(self, x: Tensor) -> Tensor:
        device = x.device
        if self.dim_pad > 0 and self.conv_2 is None and self.causal is True:
            x = self._cat_stream_buffer(x, device)
        shape_with_buffer = x.shape
        if self.conv_type == "2plus1d":
            x = rearrange(x, "b c t h w -> (b t) c h w")
        x = self.conv_1(x)
        if self.conv_type == "2plus1d":
            x = rearrange(x,
                          "(b t) c h w -> b c t h w",
                          t=shape_with_buffer[2])

            if self.conv_2 is not None:
                if self.dim_pad > 0 and self.causal is True:
                    x = self._cat_stream_buffer(x, device)
                w = x.shape[-1]
                x = rearrange(x, "b c t h w -> b c t (h w)")
                x = self.conv_2(x)
                x = rearrange(x, "b c t (h w) -> b c t h w", w=w)
        return x

    def forward(self, x: Tensor) -> Tensor:
        if self.tf_like:
            x = same_padding(x, x.shape[-2], x.shape[-1],
                             self.stride[-2], self.stride[-1],
                             self.kernel_size[-2], self.kernel_size[-1])
        x = self._forward(x)
        return x

    def _cat_stream_buffer(self, x: Tensor, device: torch.device) -> Tensor:
        if self.activation is None:
            self._setup_activation(x.shape)
        x = torch.cat((self.activation.to(device), x), 2)
        self._save_in_activation(x)
        return x

    def _save_in_activation(self, x: Tensor) -> None:
        assert self.dim_pad > 0
        self.activation = x[:, :, -self.dim_pad:, ...].clone().detach()

    def _setup_activation(self, input_shape: Tuple[float, ...]) -> None:
        assert self.dim_pad > 0
        self.activation = torch.zeros(*input_shape[:2],  # type: ignore
                                      self.dim_pad,
                                      *input_shape[3:])

class SqueezeExcitation(nn.Module):

    def __init__(self, input_channels: int,  # TODO rename activations
                 activation_2: nn.Module,
                 activation_1: nn.Module,
                 conv_type: str,
                 causal: bool,
                 squeeze_factor: int = 4,
                 bias: bool = True) -> None:
        super().__init__()
        self.causal = causal
        se_multiplier = 2 if causal else 1
        squeeze_channels = _make_divisible(input_channels
                                           // squeeze_factor
                                           * se_multiplier, 8)
        self.temporal_cumualtive_GAvg3D = TemporalCGAvgPool3D()
        self.fc1 = ConvBlock3D(input_channels*se_multiplier,
                               squeeze_channels,
                               kernel_size=(1, 1, 1),
                               padding=0,
                               tf_like=False,
                               causal=causal,
                               conv_type=conv_type,
                               bias=bias)
        self.activation_1 = activation_1()
        self.activation_2 = activation_2()
        self.fc2 = ConvBlock3D(squeeze_channels,
                               input_channels,
                               kernel_size=(1, 1, 1),
                               padding=0,
                               tf_like=False,
                               causal=causal,
                               conv_type=conv_type,
                               bias=bias)

    def _scale(self, input: Tensor) -> Tensor:
        if self.causal:
            x_space = torch.mean(input, dim=[3, 4], keepdim=True)
            scale = self.temporal_cumualtive_GAvg3D(x_space)
            scale = torch.cat((scale, x_space), dim=1)
        else:
            scale = F.adaptive_avg_pool3d(input, 1)
        scale = self.fc1(scale)
        scale = self.activation_1(scale)
        scale = self.fc2(scale)
        return self.activation_2(scale)

    def forward(self, input: Tensor) -> Tensor:
        scale = self._scale(input)
        return scale * input


def _make_divisible(v: float,
                    divisor: int,
                    min_value: Optional[int] = None
                    ) -> int:
    """
    This function is taken from the original tf repo.
    It ensures that all layers have a channel number that is divisible by 8
    It can be seen here:
    https://github.com/tensorflow/models/blob/master/research/slim/nets/mobilenet/mobilenet.py
    """
    if min_value is None:
        min_value = divisor
    new_v = max(min_value, int(v + divisor / 2) // divisor * divisor)
    # Make sure that round down does not go down by more than 10%.
    if new_v < 0.9 * v:
        new_v += divisor
    return new_v


def same_padding(x: Tensor,
                 in_height: int, in_width: int,
                 stride_h: int, stride_w: int,
                 filter_height: int, filter_width: int) -> Tensor:
    if (in_height % stride_h == 0):
        pad_along_height = max(filter_height - stride_h, 0)
    else:
        pad_along_height = max(filter_height - (in_height % stride_h), 0)
    if (in_width % stride_w == 0):
        pad_along_width = max(filter_width - stride_w, 0)
    else:
        pad_along_width = max(filter_width - (in_width % stride_w), 0)
    pad_top = pad_along_height // 2
    pad_bottom = pad_along_height - pad_top
    pad_left = pad_along_width // 2
    pad_right = pad_along_width - pad_left
    padding_pad = (pad_left, pad_right, pad_top, pad_bottom)
    return torch.nn.functional.pad(x, padding_pad)


class tfAvgPool3D(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.avgf = nn.AvgPool3d((1, 3, 3), stride=(1, 2, 2))

    def forward(self, x: Tensor) -> Tensor:
        if x.shape[-1] != x.shape[-2]:
            raise RuntimeError('only same shape for h and w ' +
                               'are supported by avg with tf_like')
        if x.shape[-1] != x.shape[-2]:
            raise RuntimeError('only same shape for h and w ' +
                               'are supported by avg with tf_like')
        f1 = x.shape[-1] % 2 != 0
        if f1:
            padding_pad = (0, 0, 0, 0)
        else:
            padding_pad = (0, 1, 0, 1)
        x = torch.nn.functional.pad(x, padding_pad)
        if f1:
            x = torch.nn.functional.avg_pool3d(x,
                                               (1, 3, 3),
                                               stride=(1, 2, 2),
                                               count_include_pad=False,
                                               padding=(0, 1, 1))
        else:
            x = self.avgf(x)
            x[..., -1] = x[..., -1] * 9/6
            x[..., -1, :] = x[..., -1, :] * 9/6
        return x


class BasicBneck(nn.Module):
    def __init__(self,
                 cfg,
                 causal: bool,
                 tf_like: bool,
                 conv_type: str,
                 norm_layer: Optional[Callable[..., nn.Module]] = None,
                 activation_layer: Optional[Callable[..., nn.Module]] = None,
                 ) -> None:
        super().__init__()
        assert type(cfg.stride) is tuple
        if (not cfg.stride[0] == 1
                or not (1 <= cfg.stride[1] <= 2)
                or not (1 <= cfg.stride[2] <= 2)):
            raise ValueError('illegal stride value')
        self.res = None

        layers = []
        if cfg.expanded_channels != cfg.out_channels:
            # expand
            self.expand = ConvBlock3D(
                in_planes=cfg.input_channels,
                out_planes=cfg.expanded_channels,
                kernel_size=(1, 1, 1),
                padding=(0, 0, 0),
                causal=causal,
                conv_type=conv_type,
                tf_like=tf_like,
                norm_layer=norm_layer,
                activation_layer=activation_layer
                )
        # deepwise
        self.deep = ConvBlock3D(
            in_planes=cfg.expanded_channels,
            out_planes=cfg.expanded_channels,
            kernel_size=cfg.kernel_size,
            padding=cfg.padding,
            stride=cfg.stride,
            groups=cfg.expanded_channels,
            causal=causal,
            conv_type=conv_type,
            tf_like=tf_like,
            norm_layer=norm_layer,
            activation_layer=activation_layer
            )
        # SE
        self.se = SqueezeExcitation(cfg.expanded_channels,
                                    causal=causal,
                                    activation_1=activation_layer,
                                    activation_2=(nn.Sigmoid
                                                  if conv_type == "3d"
                                                  else Hardsigmoid),
                                    conv_type=conv_type
                                    )
        # project
        self.project = ConvBlock3D(
            cfg.expanded_channels,
            cfg.out_channels,
            kernel_size=(1, 1, 1),
            padding=(0, 0, 0),
            causal=causal,
            conv_type=conv_type,
            tf_like=tf_like,
            norm_layer=norm_layer,
            activation_layer=nn.Identity
            )

        if not (cfg.stride == (1, 1, 1)
                and cfg.input_channels == cfg.out_channels):
            if cfg.stride != (1, 1, 1):
                if tf_like:
                    layers.append(tfAvgPool3D())
                else:
                    layers.append(nn.AvgPool3d((1, 3, 3),
                                  stride=cfg.stride,
                                  padding=cfg.padding_avg))
            layers.append(ConvBlock3D(
                    in_planes=cfg.input_channels,
                    out_planes=cfg.out_channels,
                    kernel_size=(1, 1, 1),
                    padding=(0, 0, 0),
                    norm_layer=norm_layer,
                    activation_layer=nn.Identity,
                    causal=causal,
                    conv_type=conv_type,
                    tf_like=tf_like
                    ))
            self.res = nn.Sequential(*layers)
        # ReZero
        self.alpha = nn.Parameter(torch.tensor(0.0), requires_grad=True)

    def forward(self, input: Tensor) -> Tensor:
        if self.res is not None:
            residual = self.res(input)
        else:
            residual = input
        if self.expand is not None:
            x = self.expand(input)
        else:
            x = input
        x = self.deep(x)
        x = self.se(x)
        x = self.project(x)
        result = residual + self.alpha * x
        return result

@BACKBONES.register()
class MoViNet(nn.Module):
    def __init__(self,
                 cfg_name="A0",
                 causal=True,
                 pretrained=None,
                 conv_type="2plus1d",
                 tf_like=False
                 ) -> None:
        super().__init__()
        """
        causal: causal mode
        pretrained: pretrained models
        If pretrained is True:
            conv_type is set to "3d" if causal is False,
                "2plus1d" if causal is True
            tf_like is set to True
        conv_type: type of convolution either 3d or 2plus1d
        tf_like: tf_like behaviour, basically same padding for convolutions
        """
        # load config
        conv1, blocks, conv7 = get_movinet_config(name=cfg_name)

        # construct model
        if pretrained is not None:
            tf_like = True
            conv_type = "2plus1d" if causal else "3d"
        blocks_dic = OrderedDict()

        self.causal = causal
        self.pretrained = pretrained

        norm_layer = nn.BatchNorm3d if conv_type == "3d" else nn.BatchNorm2d
        activation_layer = Swish if conv_type == "3d" else nn.Hardswish

        # conv1
        self.conv1 = ConvBlock3D(
            in_planes=conv1.input_channels,
            out_planes=conv1.out_channels,
            kernel_size=conv1.kernel_size,
            stride=conv1.stride,
            padding=conv1.padding,
            causal=causal,
            conv_type=conv_type,
            tf_like=tf_like,
            norm_layer=norm_layer,
            activation_layer=activation_layer
            )
        # blocks
        for i, block in enumerate(blocks):
            for j, basicblock in enumerate(block):
                blocks_dic[f"b{i}_l{j}"] = BasicBneck(basicblock,
                                                      causal=causal,
                                                      conv_type=conv_type,
                                                      tf_like=tf_like,
                                                      norm_layer=norm_layer,
                                                      activation_layer=activation_layer
                                                      )
        self.blocks = nn.Sequential(blocks_dic)
        # conv7
        self.conv7 = ConvBlock3D(
            in_planes=conv7.input_channels,
            out_planes=conv7.out_channels,
            kernel_size=conv7.kernel_size,
            stride=conv7.stride,
            padding=conv7.padding,
            causal=causal,
            conv_type=conv_type,
            tf_like=tf_like,
            norm_layer=norm_layer,
            activation_layer=activation_layer
            )
        if causal:
            self.cgap = TemporalCGAvgPool3D()
    
    def init_weights(self, child_model=False, revise_keys=[(r'backbone.', r'')]):
        if child_model is False:
            if isinstance(self.pretrained, str):
                logger = get_logger("SVTAS")
                load_checkpoint(self, self.pretrained, strict=False, logger=logger, revise_keys=revise_keys)
            else:
                self.apply(self._weight_init)
        else:
            self.apply(self._weight_init)
    
    def _clear_memory_buffer(self):
        self.apply(self._clean_activation_buffers)

    @staticmethod
    def _weight_init(m):  # TODO check this
        if isinstance(m, nn.Conv3d):
            nn.init.kaiming_normal_(m.weight, mode='fan_out')
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, (nn.BatchNorm3d, nn.BatchNorm2d, nn.GroupNorm)):
            nn.init.ones_(m.weight)
            nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, 0, 0.01)
            nn.init.zeros_(m.bias)

    def _forward_impl(self, x: Tensor, masks: Tensor) -> Tensor:
        x = self.conv1(x)
        x = self.blocks(x)
        x = self.conv7(x) * masks

        return x

    def forward(self, x: Tensor, masks: Tensor) -> Tensor:
        return self._forward_impl(x, masks)

    @staticmethod
    def _clean_activation_buffers(m):
        if issubclass(type(m), CausalModule):
            m.reset_activation()