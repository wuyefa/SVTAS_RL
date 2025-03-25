'''
Author       : Thyssen Wen
Date         : 2022-10-28 16:14:14
LastEditors  : Thyssen Wen
LastEditTime : 2022-10-28 16:17:35
Description  : file content
FilePath     : /SVTAS/svtas/optimizer/cosine_annealing_lr.py
'''
from ..builder import LRSCHEDULER
import torch

@LRSCHEDULER.register()
class CosineAnnealingLR(torch.optim.lr_scheduler.CosineAnnealingLR):
    def __init__(self,
                 optimizer,
                 T_max,
                 eta_min=0,
                 last_epoch=- 1,
                 verbose=False) -> None:
        super().__init__(optimizer=optimizer, T_max=T_max, eta_min=eta_min, last_epoch=last_epoch, verbose=verbose)