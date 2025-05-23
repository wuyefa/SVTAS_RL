'''
Author       : Thyssen Wen
Date         : 2023-02-22 21:25:38
LastEditors  : Thyssen Wen
LastEditTime : 2023-02-22 21:25:40
Description  : SlowOnly ref:https://github.com/open-mmlab/mmaction2/blob/master/mmaction/models/backbones/resnet3d_slowonly.py
FilePath     : /SVTAS/svtas/model/backbones/video/resnet3d_slowonly.py
'''
# Copyright (c) OpenMMLab. All rights reserved.
from ...builder import BACKBONES
from .resnet3d_slowfast import ResNet3dPathway



@BACKBONES.register()
class ResNet3dSlowOnly(ResNet3dPathway):
    """SlowOnly backbone based on ResNet3dPathway.
    Args:
        *args (arguments): Arguments same as :class:`ResNet3dPathway`.
        conv1_kernel (Sequence[int]): Kernel size of the first conv layer.
            Default: (1, 7, 7).
        conv1_stride_t (int): Temporal stride of the first conv layer.
            Default: 1.
        pool1_stride_t (int): Temporal stride of the first pooling layer.
            Default: 1.
        inflate (Sequence[int]): Inflate Dims of each block.
            Default: (0, 0, 1, 1).
        **kwargs (keyword arguments): Keywords arguments for
            :class:`ResNet3dPathway`.
    """

    def __init__(self,
                 *args,
                 lateral=False,
                 conv1_kernel=(1, 7, 7),
                 conv1_stride_t=1,
                 pool1_stride_t=1,
                 inflate=(0, 0, 1, 1),
                 with_pool2=False,
                 **kwargs):
        super().__init__(
            *args,
            lateral=lateral,
            conv1_kernel=conv1_kernel,
            conv1_stride_t=conv1_stride_t,
            pool1_stride_t=pool1_stride_t,
            inflate=inflate,
            with_pool2=with_pool2,
            **kwargs)

        assert not self.lateral