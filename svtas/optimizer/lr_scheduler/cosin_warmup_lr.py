'''
Author       : Thyssen Wen
Date         : 2022-11-03 16:45:29
LastEditors  : Thyssen Wen
LastEditTime : 2022-11-03 16:46:40
Description  : ref:https://github.com/amazon-science/long-short-term-transformer
FilePath     : /SVTAS/svtas/optimizer/lr_scheduler/cosin_warmup_lr.py
'''
import math
from ..builder import LRSCHEDULER
from torch.optim.lr_scheduler import _LRScheduler
from .multistep_warmup_lr import _get_warmup_factor_at_iter

@LRSCHEDULER.register()
class WarmupCosineLR(_LRScheduler):

    def __init__(self,
                 optimizer,
                 max_iters,
                 warmup_factor=0.3,
                 warmup_iters=500,
                 warmup_method='linear',
                 last_epoch=-1):
        self.max_iters = max_iters
        self.warmup_factor = warmup_factor
        self.warmup_iters = warmup_iters
        self.warmup_method = warmup_method
        super().__init__(optimizer, last_epoch)

    def get_lr(self):
        warmup_factor = _get_warmup_factor_at_iter(
            self.warmup_method,
            self.last_epoch,
            self.warmup_iters,
            self.warmup_factor,
        )
        return [
            base_lr
            * warmup_factor
            * 0.5
            * (1.0 + math.cos(math.pi * self.last_epoch / self.max_iters))
            for base_lr in self.base_lrs
        ]

    def _compute_values(self):
        # The new interface
        return self.get_lr()