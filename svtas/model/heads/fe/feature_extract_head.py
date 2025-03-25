'''
Author       : Thyssen Wen
Date         : 2022-05-17 19:20:01
LastEditors  : Thyssen Wen
LastEditTime : 2023-02-18 19:45:01
Description  : Feature Extract Head
FilePath     : /SVTAS/svtas/model/heads/fe/feature_extract_head.py
'''
import torch
import torch.nn as nn
import torch.nn.functional as F

from ...builder import HEADS

@HEADS.register()
class FeatureExtractHead(nn.Module):
    def __init__(self,
                 in_channels=2048,
                 input_seg_num=8,
                 output_seg_num=32,
                 sample_rate=1,
                 pool_space=True,
                 in_format="N,C,T,H,W",
                 out_format="NCT"):
        super().__init__()
        assert out_format in ["NCT", "NTC", "NCTHW"], "Unsupport output format!"
        assert in_format in ["N,C,T,H,W", "N*T,C,H,W", "N*T,C", "N,T,C", "N,C,T", "N*T,C,L"], "Unsupport input format!"
        self.output_seg_num = output_seg_num
        self.input_seg_num = input_seg_num
        self.in_channels = in_channels
        self.out_format = out_format
        self.sample_rate = sample_rate
        self.pool_space = pool_space
        self.in_format = in_format
        
        if self.pool_space:
            self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
        else:
            self.avg_pool = None

    def init_weights(self):
        pass

    def _clear_memory_buffer(self):
        pass

    def forward(self, x, masks):
        feature = x

        if self.in_format in ["N,C,T,H,W"]:
            # [N, in_channels, input_seg_num, 7, 7] -> [N * input_seg_num, in_channels, 7, 7]
            feature = torch.reshape(feature.transpose(1, 2), [-1, self.in_channels] + list(feature.shape[-2:]))
        elif self.in_format in ["N*T,C"]:
            # [N * input_seg_num, in_channels] -> [N * input_seg_num, in_channels, 1, 1]
            feature = feature.unsqueeze(-1).unsqueeze(-1)
        elif self.in_format in ["N,T,C"]:
            feature = torch.reshape(feature, [-1, feature.shape[-1]]).unsqueeze(-1).unsqueeze(-1)
        elif self.in_format in ["N,C,T"]:
            feature = torch.reshape(feature.permute([0, 2, 1]), [-1, feature.shape[1]]).unsqueeze(-1).unsqueeze(-1)
        elif self.in_format in ["N*T,C,L"]:
            # [N * input_seg_num, in_channels, L] -> [N * input_seg_num, in_channels, L, 1]
            feature = feature.unsqueeze(-1)

        # feature.shape = [N * input_seg_num, in_channels, 1, 1]
        if self.avg_pool is not None:
            feature = self.avg_pool(feature)
            
        if self.pool_space is False:
            # [N*T C H W]
            feature = torch.reshape(feature, shape=[-1, self.input_seg_num] + list(feature.shape[1:]))
            feature = feature.transpose(1, 2).contiguous()
            # [stage_num, N, C, T, H, W]
            feature = feature
            masks = F.adaptive_max_pool2d(masks[:, 0:1, ::self.sample_rate], [1, self.output_seg_num]).unsqueeze(-1).unsqueeze(-1)
            feature = F.adaptive_avg_pool3d(
                feature, [self.output_seg_num, feature.shape[-2], feature.shape[-1]]) * masks
            if self.out_format in ["NCTHW"]:
                return feature.unsqueeze(0)
            else:
                raise NotImplementedError
        # [N * num_segs, in_channels]
        feature = feature.squeeze(-1).squeeze(-1)
        # [N, in_channels, num_segs]
        feature = torch.reshape(feature, shape=[-1, self.input_seg_num, feature.shape[-1]]).transpose(1, 2)

        # [stage_num, N, C, T]
        feature = feature.unsqueeze(0)
        feature = F.adaptive_avg_pool3d(
            feature, [feature.shape[1], self.in_channels, self.output_seg_num]) * F.adaptive_max_pool2d(
                masks[:, 0:1, ::self.sample_rate], [1, self.output_seg_num]).unsqueeze(0)
            
        if self.out_format in ["NTC"]:
            feature = torch.permute(feature, dims=[0, 1, 3, 2])

        return feature