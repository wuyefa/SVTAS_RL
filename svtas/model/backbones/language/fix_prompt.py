'''
Author       : Thyssen Wen
Date         : 2022-06-03 10:42:44
LastEditors  : Thyssen Wen
LastEditTime : 2022-10-27 21:07:01
Description  : Prompt Module ref:https://github.com/KaiyangZhou/CoOp/blob/main/trainers/coop.py
FilePath     : /SVTAS/svtas/model/backbones/language/fix_prompt.py
'''
import torch
import torch.nn as nn
import random
from mmcv.runner import load_checkpoint
from torch.nn import functional as F
from ....utils.logger import get_logger
from torch.nn.utils.rnn import pad_sequence
from num2words import num2words

from ...builder import BACKBONES
# from clip import clip
from ..utils.clip import LayerNorm
from ..utils.clip import SimpleTokenizer as _Tokenizer
from ..utils.clip import Transformer
from ..utils.transducer import get_attn_pad_mask


@BACKBONES.register()
class FixPromptTextEncoder(nn.Module):
    def __init__(self,
                 actions_map_file_path,
                 embedding_dim,
                 encoder_layers_num,
                 encoder_heads_num,
                 text_embed_dim,
                 vocab_size=49408,
                 sample_rate=4,
                 clip_seg_num=32,
                 max_len=40,
                 n_ctx=8,
                 class_token_position="end",
                 ignore_index=-100,
                 pretrained=None,
                 token_embedding_pretrained=None):
        super().__init__()
        attn_mask = None
        file_ptr = open(actions_map_file_path, 'r')
        actions = file_ptr.read().split('\n')[:-1]
        file_ptr.close()
        classnames = [a.split()[1] for a in actions]
        id2classes = {int(a.split()[0]): a.split()[1] for a in actions}

        self.pretrained = pretrained
        self.token_embedding_pretrained = token_embedding_pretrained
        self.sample_rate = sample_rate

        self.prompt = Prompt(classnames=classnames, embedding_dim=embedding_dim, vocab_size=vocab_size, n_ctx=n_ctx,
            class_token_position=class_token_position, labels_id2classesname=id2classes, ignore_index=ignore_index,
            max_len=max_len, sample_rate=sample_rate)
        self.transformer = Transformer(width=embedding_dim, layers=encoder_layers_num, heads=encoder_heads_num, attn_mask=attn_mask)
        self.positional_embedding = nn.Parameter(torch.empty(clip_seg_num, max_len, embedding_dim))
        self.ln_final = LayerNorm(embedding_dim)
        self.text_projection = nn.Linear(embedding_dim, text_embed_dim)
        self.squeeze_sentence = nn.Linear(max_len * text_embed_dim, text_embed_dim)

    def _clear_memory_buffer(self):
        pass
    
    def init_weights(self, child_model=False, revise_keys=[(r'backbone.', r'')]):
        if child_model is False:
            if isinstance(self.pretrained, str):
                logger = get_logger("SVTAS")
                load_checkpoint(self, self.pretrained, strict=False, logger=logger, revise_keys=revise_keys)
            else:
                nn.init.normal_(self.positional_embedding, std=0.01)
                nn.init.normal_(self.prompt.token_embedding.weight, std=0.02)
        else:
            nn.init.normal_(self.positional_embedding, std=0.01)
            nn.init.normal_(self.prompt.token_embedding.weight, std=0.02)
        
        if isinstance(self.token_embedding_pretrained, str):
            logger = get_logger("SVTAS")
            load_checkpoint(self, self.token_embedding_pretrained, strict=False, logger=logger, revise_keys=[(r'token_embedding', r'prompt.token_embedding')])

    def forward(self, labels, masks):
        b, temporal_len = masks.shape
        prompts, pad_masks = self.prompt(labels, b, temporal_len, masks.device)
        # [N T U D]
        prompts = prompts.to(masks.device)
        # [N T U 1] -> [N*T U 1]
        pad_masks = pad_masks.reshape([-1] + list(pad_masks.shape[2:])).to(masks.device)

        x = prompts + self.positional_embedding
        # [N T U D] -> [N*T U D]
        x = torch.reshape(x, [-1] + list(prompts.shape[2:]))
        x = x.permute(1, 0, 2)  # NLD -> LND
        x = self.transformer(x)
        x = x.permute(1, 0, 2)  # LND -> NLD
        x = self.ln_final(x)

        # x.shape = [batch_size, n_ctx, transformer.width]
        x = self.text_projection(x)
        # [N*T U D] -> [N T U D]
        x = torch.reshape(x, [-1, temporal_len // self.sample_rate] + list(x.shape[1:]))
        # [N T U D] -> [N T U*D] -> [N T D] -> [N D T]
        x = torch.reshape(x, list(x.shape[:2]) + [-1])
        x = self.squeeze_sentence(x)
        x = torch.permute(x, [0, 2, 1])
        return x


class Prompt(nn.Module):
    def __init__(self,
                 classnames,
                 embedding_dim,
                 vocab_size=49408,
                 max_len=40,
                 sample_rate=4,
                 n_ctx=8,
                 class_token_position="end",
                 labels_id2classesname=None,
                 ignore_index=-100):
        super().__init__()
        self._tokenizer = _Tokenizer(max_len)
        self.max_len = max_len
        self.sample_rate = sample_rate
        n_cls = len(classnames)
        self.id2classes = labels_id2classesname
        self.ignore_index = ignore_index
        self.token_embedding = nn.Embedding(vocab_size, embedding_dim)

        # use given words to initialize context vectors

        self.prompt_prefix = [f"the person is {{}}.", f"the person is performing the action of {{}}.",
                     f"the character is {{}}.", f"he or she is {{}}.", f"the action {{}} is being played.",
                     f"it is the action of {{}}.", f"the human is {{}}.",
                     f"the person is working on {{}}.", f"the scene is {{}}.",
                     f"the person is focusing on {{}}.", f"the person is completing the action of {{}}.",
                     f"the step is {{}}", f"the action is {{}}.", f"the action step is {{}}."]

        self.ordinal_prefix = {
            1 : "Firstly, ", 2 : "Secondly, ", 3 : "Thirdly, ", 4 : "Fourthly, ", 5 : "Fifthly, ",
            6 : "Sixthly, ", 7 : "Seventhly, ", 8 : "Eighthly, ", 9 : "Ninthly, ", 10 : "Tenthly, ",
            11 : "Eleventhly, ", 12 : "Twelfthly, ", 13 : "Thirteenthly, ", 14 : "Fourteenthly, ", 15 : "Fifteenthly, ",
            16 : "Sixteenth, ", 17 : "Seventeenth, ", 18 : "Eighteenth, ", 19 : "Nineteenth, ", 20 : "Twentieth, ", 
            21 : "Twenty-firstly, ", 22 : "Twenty-secondly, ", 23 : "Twenty-thirdly, ", 24 : "Twenty-fourthly, ", 25 : "Twenty-fifthly, ", 
            26 : "Twenty-sixthly, ", 27 : "Twenty-seventhly, ", 28 : "Twenty-eighthly, ", 29 : "Twenty-ninthly, ", 30 : "Thirtiethly, ",
            31 : "Thirty-firstly, ", 32 : "Thirty-secondly, ", 33 : "Thirty-thirdly, ", 34 : "Thirty-fourthly, ", 35 : "Thirty-fifthly, ",
        }
        self.seg_len_prefix = f"This action lasted {{}} frames in current windows, "
        self.frames_position_prefix = f"This is frame {{}} of the action, "


        self.n_cls = n_cls
        self.n_ctx = n_ctx
        self.max_len = max_len
        self.class_token_position = class_token_position
    
    def convert_id_to_promot(self, label_idx_tensor):
        # label_idx_tensor [T // sample_rate]
        # promot [ctx_len D]

        # get seg_len_prefix number
        labels_idx_order, inverse_indices, counts = torch.unique_consecutive(label_idx_tensor, return_counts=True, return_inverse=True)
        labels_idx_order = list(labels_idx_order.detach().cpu().numpy())
        counts = list(counts.detach().cpu().numpy())

        promot_embedding = []
        for frame_idx in range(label_idx_tensor.shape[0]):
            order_idx = inverse_indices[frame_idx]
            label_idx = labels_idx_order[order_idx]
            label_name = self.id2classes[label_idx]
            promot_prefix_str = self.ordinal_prefix[int(order_idx) + 1] + self.seg_len_prefix.format(num2words(counts[int(order_idx)])) + \
                                self.frames_position_prefix.format(num2words(frame_idx + 1))
            
            token_promot_prefix_len = len(self._tokenizer.encode(promot_prefix_str))
            promot_prefix = self._tokenizer.tokenize(promot_prefix_str).to(label_idx_tensor.device)
            promot_prefix_embedding_sos_eos = self.token_embedding(promot_prefix)
            # [N token_promot_prefix_len D]
            promot_prefix_embedding = promot_prefix_embedding_sos_eos[:, 1:(1 + token_promot_prefix_len)]
            token_prefix = promot_prefix_embedding_sos_eos[:, :1]
            token_suffix = promot_prefix_embedding_sos_eos[:, (1 + token_promot_prefix_len):(2 + token_promot_prefix_len)]  
            
            token_labels_promot = random.choice(self.prompt_prefix).format(label_name)
            token_labels_len = len(self._tokenizer.encode(token_labels_promot))
            # [N (token_labels_len + 1) D]
            label_promot = self._tokenizer.tokenize(token_labels_promot)[:, 1:(2 + token_labels_len)].to(label_idx_tensor.device)
            label_promot_embedding = self.token_embedding(label_promot)

            if self.class_token_position == "end":
                token_embedding = torch.cat([
                    token_prefix,
                    promot_prefix_embedding,
                    label_promot_embedding,
                    token_suffix], dim=1)
            elif self.class_token_position == "middle":
                dot_vector = label_promot_embedding[:, -1:]
                token_embedding = torch.cat([
                    token_prefix,
                    promot_prefix_embedding,
                    label_promot_embedding[:, :-1],
                    dot_vector,
                    token_suffix], dim=1)
            elif self.class_token_position == "front":
                dot_vector = label_promot_embedding[:, -1:]
                token_embedding = torch.cat([
                    token_prefix,
                    label_promot_embedding[:, :-1],
                    promot_prefix_embedding,
                    dot_vector,
                    token_suffix], dim=1)
            else:
                raise ValueError
            if token_embedding.shape[-2] < self.max_len:
                token_embedding = F.pad(token_embedding, pad=[0, 0, 0, self.max_len - token_embedding.shape[-2], 0, 0], mode='constant', value=0.0)
            else:
                token_embedding = token_embedding[:, :self.max_len, :]
            promot_embedding.append(token_embedding)
        
        promot_embedding = torch.cat(promot_embedding, dim=0)
        return promot_embedding

    def forward(self, last_clip_labels, batch_size, temporal_len, device):
        if last_clip_labels is None:
            start_promot = self._tokenizer.tokenize("").to(device)
            start_promot_embedding = self.token_embedding(start_promot)
            prompts = start_promot_embedding[:, :1].expand(batch_size, temporal_len // self.sample_rate, self.max_len, -1)
        else:
            text_list = []
            for b in range(batch_size):
                if torch.any(last_clip_labels[b,:] == self.ignore_index):
                    end_promot = self._tokenizer.tokenize("").to(device)
                    end_promot_embedding = self.token_embedding(end_promot)
                    embedding = end_promot_embedding[:, 1:2].expand(1, temporal_len // self.sample_rate, self.max_len, -1)
                    text_list.append(embedding)
                else:
                    embedding = self.convert_id_to_promot(last_clip_labels[b, ::self.sample_rate])
                    text_list.append(embedding.unsqueeze(0))
            
            # [N T U D]
            prompts = torch.cat(text_list, dim=0)
        pad_masks = torch.where(prompts != 0., torch.ones_like(prompts), torch.zeros_like(prompts))[:, :, :, 0:1]
        return prompts, pad_masks
