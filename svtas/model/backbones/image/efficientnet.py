'''
Author       : Thyssen Wen
Date         : 2022-11-21 16:12:36
LastEditors  : Thyssen Wen
LastEditTime : 2022-11-21 20:12:02
Description  : ref:https://github.com/open-mmlab/mmclassification/blob/master/mmcls/models/backbones/efficientnet.py
FilePath     : /SVTAS/svtas/model/backbones/image/efficientnet.py
'''
import mmcv
import copy
import math
from functools import partial

import torch
import torch.nn as nn

from mmcv.cnn.bricks import ConvModule, DropPath
from mmcv.runner import Sequential

from ....utils.logger import get_logger
from mmcv.runner import load_checkpoint

from .mobilenet_v2 import make_divisible
from ...builder import BACKBONES
from .efficientformer import BaseBackbone
from ..utils import InvertedResidual, EdgeResidual

def model_scaling(layer_setting, arch_setting):
    """Scaling operation to the layer's parameters according to the
    arch_setting."""
    # scale width
    new_layer_setting = copy.deepcopy(layer_setting)
    for layer_cfg in new_layer_setting:
        for block_cfg in layer_cfg:
            block_cfg[1] = make_divisible(block_cfg[1] * arch_setting[0], 8)

    # scale depth
    split_layer_setting = [new_layer_setting[0]]
    for layer_cfg in new_layer_setting[1:-1]:
        tmp_index = [0]
        for i in range(len(layer_cfg) - 1):
            if layer_cfg[i + 1][1] != layer_cfg[i][1]:
                tmp_index.append(i + 1)
        tmp_index.append(len(layer_cfg))
        for i in range(len(tmp_index) - 1):
            split_layer_setting.append(layer_cfg[tmp_index[i]:tmp_index[i +
                                                                        1]])
    split_layer_setting.append(new_layer_setting[-1])

    num_of_layers = [len(layer_cfg) for layer_cfg in split_layer_setting[1:-1]]
    new_layers = [
        int(math.ceil(arch_setting[1] * num)) for num in num_of_layers
    ]

    merge_layer_setting = [split_layer_setting[0]]
    for i, layer_cfg in enumerate(split_layer_setting[1:-1]):
        if new_layers[i] <= num_of_layers[i]:
            tmp_layer_cfg = layer_cfg[:new_layers[i]]
        else:
            tmp_layer_cfg = copy.deepcopy(layer_cfg) + [layer_cfg[-1]] * (
                new_layers[i] - num_of_layers[i])
        if tmp_layer_cfg[0][3] == 1 and i != 0:
            merge_layer_setting[-1] += tmp_layer_cfg.copy()
        else:
            merge_layer_setting.append(tmp_layer_cfg.copy())
    merge_layer_setting.append(split_layer_setting[-1])

    return merge_layer_setting


@BACKBONES.register()
class EfficientNet(BaseBackbone):
    """EfficientNet backbone.
    Args:
        arch (str): Architecture of efficientnet. Defaults to b0.
        out_indices (Sequence[int]): Output from which stages.
            Defaults to (6, ).
        frozen_stages (int): Stages to be frozen (all param fixed).
            Defaults to 0, which means not freezing any parameters.
        conv_cfg (dict): Config dict for convolution layer.
            Defaults to None, which means using conv2d.
        norm_cfg (dict): Config dict for normalization layer.
            Defaults to dict(type='BN').
        act_cfg (dict): Config dict for activation layer.
            Defaults to dict(type='Swish').
        norm_eval (bool): Whether to set norm layers to eval mode, namely,
            freeze running stats (mean and var). Note: Effect on Batch Norm
            and its variants only. Defaults to False.
        with_cp (bool): Use checkpoint or not. Using checkpoint will save some
            memory while slowing down the training speed. Defaults to False.
    """

    # Parameters to build layers.
    # 'b' represents the architecture of normal EfficientNet family includes
    # 'b0', 'b1', 'b2', 'b3', 'b4', 'b5', 'b6', 'b7', 'b8'.
    # 'e' represents the architecture of EfficientNet-EdgeTPU including 'es',
    # 'em', 'el'.
    # 6 parameters are needed to construct a layer, From left to right:
    # - kernel_size: The kernel size of the block
    # - out_channel: The number of out_channels of the block
    # - se_ratio: The sequeeze ratio of SELayer.
    # - stride: The stride of the block
    # - expand_ratio: The expand_ratio of the mid_channels
    # - block_type: -1: Not a block, 0: InvertedResidual, 1: EdgeResidual
    layer_settings = {
        'b': [[[3, 32, 0, 2, 0, -1]],
              [[3, 16, 4, 1, 1, 0]],
              [[3, 24, 4, 2, 6, 0],
               [3, 24, 4, 1, 6, 0]],
              [[5, 40, 4, 2, 6, 0],
               [5, 40, 4, 1, 6, 0]],
              [[3, 80, 4, 2, 6, 0],
               [3, 80, 4, 1, 6, 0],
               [3, 80, 4, 1, 6, 0],
               [5, 112, 4, 1, 6, 0],
               [5, 112, 4, 1, 6, 0],
               [5, 112, 4, 1, 6, 0]],
              [[5, 192, 4, 2, 6, 0],
               [5, 192, 4, 1, 6, 0],
               [5, 192, 4, 1, 6, 0],
               [5, 192, 4, 1, 6, 0],
               [3, 320, 4, 1, 6, 0]],
              [[1, 1280, 0, 1, 0, -1]]
              ],
        'e': [[[3, 32, 0, 2, 0, -1]],
              [[3, 24, 0, 1, 3, 1]],
              [[3, 32, 0, 2, 8, 1],
               [3, 32, 0, 1, 8, 1]],
              [[3, 48, 0, 2, 8, 1],
               [3, 48, 0, 1, 8, 1],
               [3, 48, 0, 1, 8, 1],
               [3, 48, 0, 1, 8, 1]],
              [[5, 96, 0, 2, 8, 0],
               [5, 96, 0, 1, 8, 0],
               [5, 96, 0, 1, 8, 0],
               [5, 96, 0, 1, 8, 0],
               [5, 96, 0, 1, 8, 0],
               [5, 144, 0, 1, 8, 0],
               [5, 144, 0, 1, 8, 0],
               [5, 144, 0, 1, 8, 0],
               [5, 144, 0, 1, 8, 0]],
              [[5, 192, 0, 2, 8, 0],
               [5, 192, 0, 1, 8, 0]],
              [[1, 1280, 0, 1, 0, -1]]
              ]
    }  # yapf: disable

    # Parameters to build different kinds of architecture.
    # From left to right: scaling factor for width, scaling factor for depth,
    # resolution.
    arch_settings = {
        'b0': (1.0, 1.0, 224),
        'b1': (1.0, 1.1, 240),
        'b2': (1.1, 1.2, 260),
        'b3': (1.2, 1.4, 300),
        'b4': (1.4, 1.8, 380),
        'b5': (1.6, 2.2, 456),
        'b6': (1.8, 2.6, 528),
        'b7': (2.0, 3.1, 600),
        'b8': (2.2, 3.6, 672),
        'es': (1.0, 1.0, 224),
        'em': (1.0, 1.1, 240),
        'el': (1.2, 1.4, 300)
    }

    def __init__(self,
                 pretrained=None,
                 arch='b0',
                 drop_path_rate=0.,
                 out_indices=(6, ),
                 frozen_stages=0,
                 conv_cfg=dict(type='Conv2dAdaptivePadding'),
                 norm_cfg=dict(type='BN', eps=1e-3),
                 act_cfg=dict(type='Swish'),
                 norm_eval=False,
                 with_cp=False,
                 init_cfg=[
                     dict(type='Kaiming', layer='Conv2d'),
                     dict(
                         type='Constant',
                         layer=['_BatchNorm', 'GroupNorm'],
                         val=1)
                 ]):
        super(EfficientNet, self).__init__(init_cfg)
        self.pretrained = pretrained
        assert arch in self.arch_settings, \
            f'"{arch}" is not one of the arch_settings ' \
            f'({", ".join(self.arch_settings.keys())})'
        self.arch_setting = self.arch_settings[arch]
        self.layer_setting = self.layer_settings[arch[:1]]
        for index in out_indices:
            if index not in range(0, len(self.layer_setting)):
                raise ValueError('the item in out_indices must in '
                                 f'range(0, {len(self.layer_setting)}). '
                                 f'But received {index}')

        if frozen_stages not in range(len(self.layer_setting) + 1):
            raise ValueError('frozen_stages must be in range(0, '
                             f'{len(self.layer_setting) + 1}). '
                             f'But received {frozen_stages}')
        self.drop_path_rate = drop_path_rate
        self.out_indices = out_indices
        self.frozen_stages = frozen_stages
        self.conv_cfg = conv_cfg
        self.norm_cfg = norm_cfg
        self.act_cfg = act_cfg
        self.norm_eval = norm_eval
        self.with_cp = with_cp

        self.layer_setting = model_scaling(self.layer_setting,
                                           self.arch_setting)
        block_cfg_0 = self.layer_setting[0][0]
        block_cfg_last = self.layer_setting[-1][0]
        self.in_channels = make_divisible(block_cfg_0[1], 8)
        self.out_channels = block_cfg_last[1]
        self.layers = nn.ModuleList()
        self.layers.append(
            ConvModule(
                in_channels=3,
                out_channels=self.in_channels,
                kernel_size=block_cfg_0[0],
                stride=block_cfg_0[3],
                padding=block_cfg_0[0] // 2,
                conv_cfg=self.conv_cfg,
                norm_cfg=self.norm_cfg,
                act_cfg=self.act_cfg))
        self.make_layer()
        self.layers.append(
            ConvModule(
                in_channels=self.in_channels,
                out_channels=self.out_channels,
                kernel_size=block_cfg_last[0],
                stride=block_cfg_last[3],
                padding=block_cfg_last[0] // 2,
                conv_cfg=self.conv_cfg,
                norm_cfg=self.norm_cfg,
                act_cfg=self.act_cfg))

    def make_layer(self):
        # Without the first and the final conv block.
        layer_setting = self.layer_setting[1:-1]

        total_num_blocks = sum([len(x) for x in layer_setting])
        block_idx = 0
        dpr = [
            x.item()
            for x in torch.linspace(0, self.drop_path_rate, total_num_blocks)
        ]  # stochastic depth decay rule

        for layer_cfg in layer_setting:
            layer = []
            for i, block_cfg in enumerate(layer_cfg):
                (kernel_size, out_channels, se_ratio, stride, expand_ratio,
                 block_type) = block_cfg

                mid_channels = int(self.in_channels * expand_ratio)
                out_channels = make_divisible(out_channels, 8)
                if se_ratio <= 0:
                    se_cfg = None
                else:
                    se_cfg = dict(
                        channels=mid_channels,
                        ratio=expand_ratio * se_ratio,
                        divisor=1,
                        act_cfg=(self.act_cfg, dict(type='Sigmoid')))
                if block_type == 1:  # edge tpu
                    if i > 0 and expand_ratio == 3:
                        with_residual = False
                        expand_ratio = 4
                    else:
                        with_residual = True
                    mid_channels = int(self.in_channels * expand_ratio)
                    if se_cfg is not None:
                        se_cfg = dict(
                            channels=mid_channels,
                            ratio=se_ratio * expand_ratio,
                            divisor=1,
                            act_cfg=(self.act_cfg, dict(type='Sigmoid')))
                    block = partial(EdgeResidual, with_residual=with_residual)
                else:
                    block = InvertedResidual
                layer.append(
                    block(
                        in_channels=self.in_channels,
                        out_channels=out_channels,
                        mid_channels=mid_channels,
                        kernel_size=kernel_size,
                        stride=stride,
                        se_cfg=se_cfg,
                        conv_cfg=self.conv_cfg,
                        norm_cfg=self.norm_cfg,
                        act_cfg=self.act_cfg,
                        drop_path_rate=dpr[block_idx],
                        with_cp=self.with_cp))
                self.in_channels = out_channels
                block_idx += 1
            self.layers.append(Sequential(*layer))
    
    def _clear_memory_buffer(self):
        pass
    
    def init_weights(self, child_model=False, revise_keys=[(r'backbone.', r'')]):
        if child_model is False:
            if isinstance(self.pretrained, str):
                logger  = get_logger("SVTAS")
                load_checkpoint(self, self.pretrained, strict=False, logger=logger, revise_keys=revise_keys)

    def forward(self, x, masks):
        outs = []
        for i, layer in enumerate(self.layers):
            x = layer(x) * masks
            if i in self.out_indices:
                outs.append(x)

        if len(outs) == 1:
            return outs[0]
        return tuple(outs)

    def _freeze_stages(self):
        for i in range(self.frozen_stages):
            m = self.layers[i]
            m.eval()
            for param in m.parameters():
                param.requires_grad = False

    def train(self, mode=True):
        super(EfficientNet, self).train(mode)
        self._freeze_stages()
        if mode and self.norm_eval:
            for m in self.modules():
                if isinstance(m, nn.BatchNorm2d):
                    m.eval()