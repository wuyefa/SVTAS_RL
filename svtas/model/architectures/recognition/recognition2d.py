'''
Author: Thyssen Wen
Date: 2022-04-29 10:59:22
LastEditors  : Thyssen Wen
LastEditTime : 2022-11-21 20:56:08
Description: Action Recognition 2D framework
FilePath     : /SVTAS/svtas/model/architectures/recognition/recognition2d.py
'''
import torch
import torch.nn as nn
import torch.nn.functional as F
from mmcv.runner import load_checkpoint

from ....utils.logger import get_logger

from ...builder import build_backbone
from ...builder import build_neck
from ...builder import build_head

from ...builder import ARCHITECTURE

@ARCHITECTURE.register()
class Recognition2D(nn.Module):
    def __init__(self,
                 backbone=None,
                 neck=None,
                 head=None,
                 loss=None):
        super().__init__()
        if backbone is not None:
            self.backbone = build_backbone(backbone)
        else:
            self.backbone = None
            
        if neck is not None:
            self.neck = build_neck(neck)
        else:
            self.neck = None

        if head is not None:
            self.head = build_head(head)
            self.sample_rate = head.sample_rate
        else:
            self.head = None
            self.sample_rate = loss.sample_rate
    
        self.init_weights()

    def init_weights(self):
        if self.backbone is not None:
            self.backbone.init_weights(child_model=False)
        if self.neck is not None:
            self.neck.init_weights()
        if self.head is not None:
            self.head.init_weights()
    
    def _clear_memory_buffer(self):
        if self.backbone is not None:
            self.backbone._clear_memory_buffer()
        if self.neck is not None:
            self.neck._clear_memory_buffer()
        if self.head is not None:
            self.head._clear_memory_buffer()

    def forward(self, input_data):
        masks = input_data['masks']
        imgs = input_data['imgs']
        
        # masks.shape=[N,T]
        masks = masks.unsqueeze(1)

        # x.shape=[N,T,C,H,W], for most commonly case
        imgs = torch.reshape(imgs, [-1] + list(imgs.shape[2:]))
        # x [N * T, C, H, W]

        if self.backbone is not None:
             # masks.shape [N * T, 1, 1, 1]
            backbone_masks = torch.reshape(masks[:, :, ::self.sample_rate], [-1]).unsqueeze(-1).unsqueeze(-1).unsqueeze(-1)
            feature = self.backbone(imgs, backbone_masks)
        else:
            feature = imgs

        # feature [N * T , F_dim, 7, 7]
        # step 3 extract memory feature
        if self.neck is not None:
            seg_feature = self.neck(
                feature, masks[:, :, ::self.sample_rate])
            
        else:
            seg_feature = feature

        # step 5 segmentation
        # seg_feature [N, H_dim, T]
        # cls_feature [N, F_dim, T]
        if self.head is not None:
            head_score = self.head(seg_feature, masks)
        else:
            head_score = seg_feature
        return {"output":head_score}