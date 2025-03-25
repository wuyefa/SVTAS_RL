'''
Author       : Thyssen Wen
Date         : 2022-06-14 15:27:18
LastEditors  : Thyssen Wen
LastEditTime : 2022-12-22 15:55:15
Description  : Bridge-Prompt: Towards Ordinal Action Understanding in Instructional Videos ref:https://github.com/ttlmh/Bridge-Prompt
FilePath     : /SVTAS/svtas/model/backbones/language/bridge_prompt.py
'''
import torch
import torch.nn as nn
from torch.nn import functional as F
import numpy as np
from mmcv.runner import load_checkpoint
from ....utils.logger import get_logger
from ...builder import BACKBONES
# from clip import clip
from ..utils.clip import LayerNorm
from ..utils.clip import SimpleTokenizer as _Tokenizer
from ..utils.clip import Transformer

@BACKBONES.register()
class BridgePromptTextEncoder(nn.Module):
    def __init__(self,
                 clip_model,
                 actions_map_file_path,
                 cnt_max=7,
                 sample_rate=4,
                 max_len=77,
                 dataset_type="gtea",
                 ignore_index=-100):
        super().__init__()
        self.clip_model = clip_model
        file_ptr = open(actions_map_file_path, 'r')
        actions = file_ptr.read().split('\n')[:-1]
        file_ptr.close()
        id2classes = {int(a.split()[0]): a.split()[1] for a in actions}

        self.prompt = BridgePrompt(dataset_type=dataset_type, cnt_max=cnt_max, sample_rate=sample_rate, max_len=max_len,
                                   labels_id2classesname=id2classes, ignore_index=ignore_index)

    def _clear_memory_buffer(self):
        pass
    
    def init_weights(self, child_model=False, revise_keys=[(r'backbone.', r'')]):
        pass

    def forward(self, labels, masks):
        b, _, temporal_len = masks.shape
        prompts = self.prompt(labels, b, temporal_len, masks.device)

        outputs = []
        # res_token_cnt [B 1 max_len]
        # res_token_acts [B cnt_max max_len]
        # res_token_all [B 1 max_len]
        # text_dict_pos [B pos_cnt max_len]
        for prompt in prompts:
            prompt = prompt.to(masks.device)
            # [B NUM max_len] -> [B*NUM max_len]
            prompt = torch.reshape(prompt, [-1, prompt.shape[-1]])
            x = self.clip_model.encode_text(prompt)
            outputs.append(x)
        # text_cnt_embedding [B D]
        # text_acts_embedding [B cnt_max D]
        # text_all_embedding [B D]
        # text_pos_embedding [B pos_cnt D]
        text_cnt_embedding, text_acts_embedding, text_all_embedding, text_pos_embedding = outputs
        text_acts_embedding = text_acts_embedding.view(b, -1, text_acts_embedding.shape[-1])
        text_pos_embedding = text_pos_embedding.view(b, -1, text_pos_embedding.shape[-1])
        return text_all_embedding, text_cnt_embedding, text_acts_embedding, text_pos_embedding

class BridgePrompt(nn.Module):
    def __init__(self,
                 dataset_type="gtea",
                 cnt_max=7,
                 sample_rate=4,
                 max_len=77,
                 labels_id2classesname=None,
                 ignore_index=-100):
        super().__init__()
        self._tokenizer = _Tokenizer(max_len)
        self.sample_rate = sample_rate
        self.ignore_index = ignore_index
        self.id2classes = labels_id2classesname
        self.dataset_type = dataset_type
        self.cnt_max = cnt_max
        self.max_len = max_len
        
        text_aug_cnts = [f"This clip contains no actions.",
                        f"This clip contains only one action,", f"This clip contains two actions,",
                        f"This clip contains three actions,", f"This clip contains four actions,",
                        f"This clip contains five actions,", f"This clip contains six actions,",
                        f"This clip contains seven actions,", f"This clip contains eight actions,",
                        f"This clip contains nine actions,", f"This clip contains ten actions,",
                        f"This clip contains eleven actions,", f"This clip contains twelve actions,",
                        f"This clip contains thirteen actions,", f"This clip contains fourteen actions,",
                        f"This clip contains fifteen actions,", f"This clip contains sixteen actions,",
                        f"This clip contains seventeen actions,", f"This clip contains eighteen actions,",
                        f"This clip contains nineteen actions,", f"This clip contains twenty actions,",
                        f"This clip contains twenty-one actions,", f"This clip contains twenty-two actions,",
                        f"This clip contains twenty-three actions,", f"This clip contains twenty-four actions,",
                        f"This clip contains twenty-five actions,", f"This clip contains twenty-six actions,",
                        f"This clip contains twenty-seven actions,", f"This clip contains twenty-eight actions,",
                        f"This clip contains twenty-nine actions,", f"This clip contains thirty actions,",
                        f"This clip contains thirty-one actions,", f"This clip contains thirty-two actions,"]
        text_aug_acts = [f"Firstly, ", f"Secondly, ", f"Thirdly, ", f"Fourthly, ",
                        f"Fifthly, ", f"Sixthly, ", f"Seventhly, ", f"Eighthly, ",
                        f"Ninthly", f"Tenthly", f"Eleventhly", f"Twelfthly"
                        f"Thirteenthly, ", f"Fourteenthly, ", f"Fifteenthly, ", f"Sixteenthly, ",
                        f"Seventeenthly, ", f"Eighteenthly, ", f"Nineteenthly, ", f"Twentiethly, ",
                        f"Twenty-firstly, ", f"Twenty-secondly, ", f"Twenty-thirdly, ", f"Twenty-fourthly, ",
                        f"Twenty-fifthly", f"Twenty-sixthly", f"Twenty-seventhly", f"Twenty-eighthly",
                        f"Twenty-ninthly", f"Thirtiethly", f"Thirty-firstly", f"Thirty-secondly",]
        self.text_aug_temp = [f"the person is {{}}.", f"the person is performing the action of {{}}.",
                        f"the character is {{}}.", f"he or she is {{}}.", f"the action {{}} is being played.",
                        f"it is the action of {{}}.", f"the human is {{}}.",
                        f"the person is working on {{}}.", f"the scene is {{}}.",
                        f"the person is focusing on {{}}.", f"the person is completing the action of {{}}.",
                        f"the step is {{}}", f"the action is {{}}.", f"the action step is {{}}."]
        self.text_long_temp = [f"the person is {{}}.", f"the character is {{}}.", f"he or she is {{}}.",
                        f"the human is {{}}.", f"the scene is {{}}.", f"{{}} is being done.",
                        f"the step is {{}}", f"the action is {{}}.", f"the action step is {{}}."]
        text_no_acts = [f"The first action does not exist.",
                        f"The second action does not exist.", f"The third action does not exist.",
                        f"The fourth action does not exist.", f"The fifth action does not exist.",
                        f"The sixth action does not exist.", f"The seventh action does not exist.",
                        f"The eighth action does not exist.", f"The nine action does not exist.",
                        f"The ten action does not exist.", f"The eleven action does not exist.",
                        f"The twelve action does not exist.", f"The thirteen action does not exist.",
                        f"The fourteen action does not exist.", f"The fifteen action does not exist.",
                        f"The sixteen action does not exist.", f"The seventeen action does not exist.",
                        f"The eighteen action does not exist.", f"The nineteen action does not exist.",
                        f"The twenty action does not exist.", f"The twenty-one action does not exist.",
                        f"The twenty-two action does not exist.", f"The twenty-three action does not exist.",
                        f"The twenty-four action does not exist.", f"The twenty-five action does not exist.",
                        f"The twenty-six action does not exist.", f"The twenty-seven action does not exist.",
                        f"The twenty-eight action does not exist.", f"The twenty-nine action does not exist.",
                        f"The thirty action does not exist.", f"The thirty-one action does not exist.",
                        f"The thirty-two action does not exist."]
        text_aug_acts = [f"this is the first action.", f"this is the second action.",
                        f"this is the third action.", f"this is the fourth action.",
                        f"this is the fifth action.", f"this is the sixth action.",
                        f"this is the seventh action.", f"this is the eighth action.",
                        f"this is the nine action.", f"this is the ten action.",
                        f"this is the eleven action.", f"this is the twelve action.",
                        f"this is the thirteen action.", f"this is the fourteen action.",
                        f"this is the fifteen action.", f"this is the sixteen action.",
                        f"this is the seventeen action.", f"this is the eighteen action.",
                        f"this is the nineteen action.", f"this is the twenty action.",
                        f"this is the twenty-one action.", f"this is the twenty-two action.",
                        f"this is the twenty-three action.", f"this is the twenty-four action.",
                        f"this is the twenty-five action.", f"this is the twenty-six action.",
                        f"this is the twenty-seven action.", f"this is the twenty-eight action.",
                        f"this is the twenty-nine action.", f"this is the thirty action.",
                        f"this is the thirty-one action.", f"this is the thirty-two action."]
        
        self.text_aug_cnts = text_aug_cnts[:self.cnt_max + 1]
        self.text_aug_acts = text_aug_acts[:self.cnt_max]
        self.text_no_acts = text_no_acts[:self.cnt_max]
        text_aug_acts = text_aug_acts[:self.cnt_max]

        lst = [self._tokenizer.tokenize(txt) for txt in text_aug_acts]
        self.lst = torch.cat(lst)
    
    def convert_id_to_promot(self, label_idx_tensor):
        # label_idx_tensor [T // sample_rate]
        # promot [ctx_len D]

        
        # get seg_len_prefix number
        labels_idx_order, inverse_indices, counts = torch.unique_consecutive(label_idx_tensor, return_counts=True, return_inverse=True)
        counts = list(counts.detach().cpu().numpy())
        
        num_temp = len(self.text_aug_temp)
        num_long = len(self.text_long_temp)
        text_id = np.random.randint(num_temp, size=self.cnt_max)
        text_id_long = np.random.randint(num_long, size=self.cnt_max)
        # labels_idx_order [NUM] -> [cnt_max]
        if label_idx_tensor.shape[0] >= self.cnt_max:
            label_idx_tensor = label_idx_tensor[:self.cnt_max]
        else:
            label_idx_tensor = torch.cat([label_idx_tensor,
                torch.full_like(label_idx_tensor, fill_value=self.ignore_index)[:(self.cnt_max - label_idx_tensor.shape[0])]], dim=0)
        labels_idx_order_cnt = labels_idx_order >= 0
        labels_idx_order_cnt = torch.sum(labels_idx_order_cnt)

        # [1 max_len]
        res_token_cnt = self._tokenizer.tokenize(self.text_aug_cnts[labels_idx_order_cnt.item()])

        sentences = []
        sentences_all = ''
        for idx in range(labels_idx_order.shape[0]):
            label_name = self.id2classes[labels_idx_order[idx].item()]

            # rename label name
            if self.dataset_type == 'breakfast':
                if label_name == 'SIL': label_name = 'waiting and preparing'
                if label_name == 'SIL': label_name = 'finishing and waiting'
            
            sent = self.text_aug_acts[idx] + self.text_aug_temp[text_id[idx]].format(label_name)
            sentences.append(self._tokenizer.tokenize(sent))
            sentences_all += ' ' + self.text_aug_acts[idx] + self.text_long_temp[text_id_long[idx]].format(label_name)

        for idx in range(labels_idx_order.shape[0], len(self.text_no_acts)):
            sentences.append(self._tokenizer.tokenize(self.text_no_acts[idx]))
        
        # [cnt_max max_len]
        res_token_acts = torch.cat(sentences, dim=0)

        # [1 max_len]
        sentences_all = sentences_all[1:self.max_len]
        res_token_all = self._tokenizer.tokenize(sentences_all)
        
        return res_token_cnt, res_token_acts, res_token_all
    
    def forward(self, last_clip_labels, batch_size, temporal_len, device):
        text_dict_posemb = self.lst.to(device, non_blocking=True)
        text_dict_pos = text_dict_posemb.repeat(batch_size, 1, 1)
        
        if last_clip_labels is None:
            # [pos max_len]
            start_promot = self._tokenizer.tokenize("").to(device)
            prompts = []
            # res_token_cnt [B 1 max_len]
            prompts.append(start_promot.unsqueeze(0).expand(batch_size, 1, self.max_len))
            # res_token_acts [B cnt_max max_len]
            prompts.append(start_promot.unsqueeze(0).expand(batch_size, self.cnt_max, self.max_len))
            # res_token_all [B 1 max_len]
            prompts.append(start_promot.unsqueeze(0).expand(batch_size, 1, self.max_len))
            # text_dict_pos [B pos_cnt max_len]
            prompts.append(text_dict_pos)
        else:
            res_token_cnt_list = []
            res_token_acts_list = []
            res_token_all_list = []
            for b in range(batch_size):
                if torch.any(last_clip_labels[b,:] == self.ignore_index):
                    end_promot = self._tokenizer.tokenize("").to(device)
                    res_token_cnt_list.append(end_promot.unsqueeze(0).expand(1, 1, self.max_len))
                    res_token_acts_list.append(end_promot.unsqueeze(0).expand(1, self.cnt_max, self.max_len))
                    res_token_all_list.append(end_promot.unsqueeze(0).expand(1, 1, self.max_len))
                else:
                    embedding = self.convert_id_to_promot(last_clip_labels[b, ::self.sample_rate])
                    res_token_cnt_list.append(embedding[0].unsqueeze(0).to(device))
                    res_token_acts_list.append(embedding[1].unsqueeze(0).to(device))
                    res_token_all_list.append(embedding[2].unsqueeze(0).to(device))
            
            # res_token_cnt [B 1 max_len]
            # res_token_acts [B cnt_max max_len]
            # res_token_all [B 1 max_len]
            # text_dict_pos [B pos_cnt max_len]
            prompts = [torch.cat(res_token_cnt_list, dim=0),
                       torch.cat(res_token_acts_list, dim=0).view(batch_size, -1 ,self.max_len),
                       torch.cat(res_token_all_list, dim=0),
                       text_dict_pos]
        
        return prompts