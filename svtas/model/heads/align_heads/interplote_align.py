'''
Author       : Thyssen Wen
Date         : 2022-10-28 20:05:06
LastEditors  : Thyssen Wen
LastEditTime : 2022-10-28 20:13:29
Description  : interplote align score
FilePath     : /SVTAS/svtas/model/heads/align_heads/interplote_align.py
'''
import torch
import torch.nn as nn
import torch.nn.functional as F

from ...builder import HEADS

@HEADS.register()
class InterploteAlignHead(nn.Module):
    def __init__(self):
        super(InterploteAlignHead, self).__init__()

    def init_weights(self):
        pass

    def _clear_memory_buffer(self):
        pass

    def forward(self, seg_score, labels, mask):
        # seg_score [num_stages, N, C, T]
        seg_score = F.interpolate(seg_score, size=[seg_score.shape[-2], labels.shape[-1]], mode="bilinear")
        return seg_score