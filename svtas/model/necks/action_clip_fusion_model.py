'''
Author       : Thyssen Wen
Date         : 2022-10-26 10:31:45
LastEditors  : Thyssen Wen
LastEditTime : 2022-10-31 14:09:32
Description  : ImageCLIP ref:https://github.com/sallymmx/ActionCLIP/blob/master/modules/Visual_Prompt.py
FilePath     : /SVTAS/svtas/model/necks/action_clip_fusion_model.py
'''
# Code for "ActionCLIP: ActionCLIP: A New Paradigm for Action Recognition"
# arXiv:
# Mengmeng Wang, Jiazheng Xing, Yong Liu

import torch
from torch import nn
from collections import OrderedDict

from ...utils.logger import get_logger
from mmcv.runner import load_checkpoint
from ..builder import NECKS


class LayerNorm(nn.Module):
    def __init__(self, hidden_size, eps=1e-12):
        """Construct a layernorm module in the TF style (epsilon inside the square root).
        """
        super(LayerNorm, self).__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.bias = nn.Parameter(torch.zeros(hidden_size))
        self.variance_epsilon = eps

    def forward(self, x):
        u = x.mean(-1, keepdim=True)
        s = (x - u).pow(2).mean(-1, keepdim=True)
        x = (x - u) / torch.sqrt(s + self.variance_epsilon)
        return self.weight * x + self.bias

class QuickGELU(nn.Module):
    def forward(self, x: torch.Tensor):
        return x * torch.sigmoid(1.702 * x)


class ResidualAttentionBlock(nn.Module):
    def __init__(self, d_model: int, n_head: int, attn_mask: torch.Tensor = None):
        super().__init__()

        self.attn = nn.MultiheadAttention(d_model, n_head)
        self.ln_1 = LayerNorm(d_model)
        self.mlp = nn.Sequential(OrderedDict([
            ("c_fc", nn.Linear(d_model, d_model * 4)),
            ("gelu", QuickGELU()),
            ("c_proj", nn.Linear(d_model * 4, d_model))
        ]))
        self.ln_2 = LayerNorm(d_model)
        self.attn_mask = attn_mask

    def attention(self, x: torch.Tensor):
        self.attn_mask = self.attn_mask.to(dtype=x.dtype, device=x.device) if self.attn_mask is not None else None
        return self.attn(x, x, x, need_weights=False, attn_mask=self.attn_mask)[0]

    def forward(self, x: torch.Tensor):
        x = x + self.attention(self.ln_1(x))
        x = x + self.mlp(self.ln_2(x))
        return x


def trunc_normal_(x, mean=0., std=1.):
    # From https://discuss.pytorch.org/t/implementing-truncated-normal-initializer/4778/12
    return x.normal_().fmod_(2).mul_(std).add_(mean)


class TAggregate(nn.Module):
    def __init__(self, clip_length=None, embed_dim=2048, n_layers=6):
        super(TAggregate, self).__init__()
        self.clip_length = clip_length
        drop_rate = 0.
        enc_layer = nn.TransformerEncoderLayer(d_model=embed_dim, nhead=8)
        self.transformer_enc = nn.TransformerEncoder(enc_layer, num_layers=n_layers, norm=nn.LayerNorm(
            embed_dim))

        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, clip_length + 1, embed_dim))
        self.pos_drop = nn.Dropout(p=drop_rate)

        with torch.no_grad():
            trunc_normal_(self.pos_embed, std=.02)
            trunc_normal_(self.cls_token, std=.02)
        self.apply(self._init_weights)

    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            with torch.no_grad():
                trunc_normal_(m.weight, std=.02)
        if isinstance(m, nn.Linear) and m.bias is not None:
            nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.LayerNorm):
            nn.init.constant_(m.bias, 0)
            nn.init.constant_(m.weight, 1.0)

    def forward(self, x):
        nvids = x.shape[0]

        cls_tokens = self.cls_token.expand(nvids, -1, -1)
        x = torch.cat((cls_tokens, x), dim=1)
        x = x + self.pos_embed
        x.transpose_(1, 0)
        o = self.transformer_enc(x)

        return o[0]


class TemporalTransformer(nn.Module):
    def __init__(self, width: int, layers: int, heads: int, attn_mask: torch.Tensor = None):
        super().__init__()
        self.width = width
        self.layers = layers
        self.resblocks = nn.Sequential(*[ResidualAttentionBlock(width, heads, attn_mask) for _ in range(layers)])

    def forward(self, x: torch.Tensor):
        return self.resblocks((x))

@NECKS.register()
class ActionCLIPFusionNeck(nn.Module):
    def __init__(self,
                 sim_head,
                 embed_dim_cfg,
                 context_length_cfg,
                 transformer_width_cfg,
                 clip_seg_num,
                 TemporalTransformer_layer_num=6,
                 pretrained=None):
        super().__init__()
        self.sim_header = sim_head
        self.pretrained = pretrained
        self.T = clip_seg_num
        assert sim_head in ["meanP", "LSTM", "Transf", "Conv_1D", "Transf_cls"]

        if self.sim_header == "LSTM" or self.sim_header == "Transf" or self.sim_header == "Transf_cls" or self.sim_header == "Conv_1D" :
            embed_dim = embed_dim_cfg

            context_length = context_length_cfg
            transformer_width = transformer_width_cfg
            transformer_heads = transformer_width // 64

            self.frame_position_embeddings = nn.Embedding(context_length, embed_dim)
        if self.sim_header == "Transf" :
            self.transformer = TemporalTransformer(width=embed_dim, layers=TemporalTransformer_layer_num, heads=transformer_heads)
        if self.sim_header == "LSTM":
            self.lstm_visual = nn.LSTM(input_size=embed_dim, hidden_size=embed_dim,
                                       batch_first=True, bidirectional=False, num_layers=1)

        if self.sim_header == "Transf_cls":
            self.transformer = TAggregate(clip_length=self.T, embed_dim=embed_dim, n_layers=6)

        if self.sim_header == 'Conv_1D' :
            self.shift = nn.Conv1d(embed_dim, embed_dim, 3, padding=1, groups=embed_dim, bias=False)
            weight = torch.zeros(embed_dim, 1, 3)
            weight[:embed_dim // 4, 0, 0] = 1.0
            weight[embed_dim // 4:embed_dim // 4 + embed_dim // 2, 0, 1] = 1.0
            weight[-embed_dim // 4:, 0, 2] = 1.0
            self.shift.weight = nn.Parameter(weight)
    
    def _clear_memory_buffer(self):
        pass
    
    def init_weights(self, child_model=False, revise_keys=[(r'backbone.', r'')]):
        if child_model is False:
            if isinstance(self.pretrained, str):
                logger  = get_logger("SVTAS")
                load_checkpoint(self, self.pretrained, strict=False, logger=logger, revise_keys=revise_keys)
            else:
                self.apply(self._init_weights)
        else:
            self.apply(self._init_weights)

    def _init_weights(self, module):
        """ Initialize the weights.
        """
        if isinstance(module, (nn.Linear, nn.Embedding)):
            # Slightly different from the TF version which uses truncated_normal for initialization
            # cf https://github.com/pytorch/pytorch/pull/5617
            module.weight.data.normal_(mean=0.0, std=0.02)
        elif isinstance(module, LayerNorm):
            if 'beta' in dir(module) and 'gamma' in dir(module):
                module.beta.data.zero_()
                module.gamma.data.fill_(1.0)
            else:
                module.bias.data.zero_()
                module.weight.data.fill_(1.0)
        if isinstance(module, nn.Linear) and module.bias is not None:
            module.bias.data.zero_()

    def forward(self, x, text_embedding, masks):
        b, t, c = x.size()
        x = x.contiguous()
        if self.sim_header == "meanP":
            pass
        elif self.sim_header == 'Conv_1D':
            x_original = x
            x = x.view(-1, c, t)
            x = self.shift(x.float())
            x = x.permute(0, 2, 1)
            x = x.type(x_original.dtype) + x_original

        elif self.sim_header == "Transf":
            x_original = x
            seq_length = t
            position_ids = torch.arange(seq_length, dtype=torch.long, device=x.device)
            position_ids = position_ids.unsqueeze(0).expand(x.size(0), -1)
            frame_position_embeddings = self.frame_position_embeddings(position_ids)
            x = x + frame_position_embeddings

            x = x.permute(1, 0, 2)  # NLD -> LND
            x = self.transformer(x)
            x = x.permute(1, 0, 2)  # LND -> NLD
            x = x.type(x_original.dtype) + x_original

        elif self.sim_header == "LSTM":
            x_original = x
            x, _ = self.lstm_visual(x.float())
            self.lstm_visual.flatten_parameters()
            x = torch.cat((x, x_original[:, x.size(1):, ...].contiguous()), dim=1)
            x = x.type(x_original.dtype) + x_original
        elif self.sim_header == "Transf_cls":
            x_original = x
            return self.transformer(x).type(x_original.dtype)

        else:
            raise ValueError('Unknown optimizer: {}'.format(self.sim_header))
        
        x = x.permute([0, 2, 1]) * masks[: ,0:1, :]
        return text_embedding, x