'''
Author: Thyssen Wen
Date: 2022-04-27 16:13:11
LastEditors  : Thyssen Wen
LastEditTime : 2023-04-20 10:47:43
Description: feature dataset class
FilePath     : /SVTAS/svtas/loader/dataset/stream_base_dataset/cam_feature_stream_segmentation_dataset.py
'''

import copy
import os
import os.path as osp

import numpy as np
import torch

from ...builder import DATASET
from .stream_base_dataset import StreamDataset


@DATASET.register()
class CAMFeatureStreamSegmentationDataset(StreamDataset):
    def __init__(self,
                 feature_path,
                 sliding_window=60,
                 flow_feature_path=None,
                 need_precise_grad_accumulate=True,
                 **kwargs):
        self.flow_feature_path = flow_feature_path
        self.feature_path = feature_path
        self.sliding_window = sliding_window
        self.need_precise_grad_accumulate = need_precise_grad_accumulate
        super().__init__(**kwargs)
    
    def parse_file_paths(self, input_path):
        if self.dataset_type in ['gtea', '50salads', 'breakfast', 'thumos14']:
            file_ptr = open(input_path, 'r')
            info = file_ptr.read().split('\n')[:-1]
            file_ptr.close()
        return info
    
    def load_file(self, sample_videos_list):
        """Load index file to get video feature information."""
        video_segment_lists = self.parse_file_paths(self.file_path)
        info_list = [[] for i in range(self.nprocs)]
        # sample step
        for step, sample_idx_list in sample_videos_list:
            # sample step clip
            video_sample_segment_lists = [[] for i in range(self.nprocs)]
            for sample_idx_list_idx in range(len(sample_idx_list)):
                nproces_idx = sample_idx_list_idx % self.nprocs
                sample_idx = sample_idx_list[sample_idx_list_idx]
                video_sample_segment_lists[nproces_idx].append(video_segment_lists[sample_idx])

            max_len = 0
            info_proc = [[] for i in range(self.nprocs)]
            for proces_idx in range(self.nprocs):
                # convert sample
                info = []
                for video_segment in video_sample_segment_lists[proces_idx]:
                    if self.dataset_type in ['gtea', '50salads', 'breakfast', 'thumos14']:
                        video_name = video_segment.split('.')[0]
                        label_path = os.path.join(self.gt_path, video_name + '.txt')

                        video_path = os.path.join(self.feature_path, video_name + '.npy')
                        if not osp.isfile(video_path):
                            raise NotImplementedError
                    file_ptr = open(label_path, 'r')
                    content = file_ptr.read().split('\n')[:-1]
                    classes = np.zeros(len(content), dtype='int64')
                    for i in range(len(content)):
                        classes[i] = self.actions_dict[content[i]]

                    # caculate sliding num
                    if max_len < len(content):
                        max_len = len(content)
                    if self.need_precise_grad_accumulate:
                        precise_sliding_num = len(content) // self.sliding_window
                        if len(content) % self.sliding_window != 0:
                            precise_sliding_num = precise_sliding_num + 1
                    else:
                        precise_sliding_num = 1

                    if self.flow_feature_path is not None:
                        flow_feature_path = os.path.join(self.flow_feature_path, video_name + '.npy')
                        info.append(
                            dict(filename=video_path,
                                flow_feature_name=flow_feature_path,
                                raw_labels=classes,
                                video_name=video_name,
                                precise_sliding_num=precise_sliding_num))
                    else:
                        info.append(
                            dict(filename=video_path,
                                raw_labels=classes,
                                video_name=video_name,
                                precise_sliding_num=precise_sliding_num))
                        
                info_proc[proces_idx] = info

            # construct sliding num
            sliding_num = max_len // self.sliding_window
            if max_len % self.sliding_window != 0:
                sliding_num = sliding_num + 1

            # nprocs sync
            for proces_idx in range(self.nprocs):
                info_list[proces_idx].append([step, sliding_num, info_proc[proces_idx]])
        return info_list
    
    def _get_one_videos_clip(self, idx, info):
        feature_list = []
        labels_list = []
        masks_list = []
        vid_list = []
        precise_sliding_num_list = []

        for single_info in info:
            sample_segment = single_info.copy()
            sample_segment['sample_sliding_idx'] = idx
            sample_segment = self.pipeline(sample_segment)
            # imgs: tensor labels: ndarray mask: ndarray vid_list : str list
            feature_list.append(copy.deepcopy(sample_segment['feature'].unsqueeze(0)))
            labels_list.append(np.expand_dims(sample_segment['labels'], axis=0).copy())
            masks_list.append(np.expand_dims(sample_segment['masks'], axis=0).copy())
            vid_list.append(copy.deepcopy(sample_segment['video_name']))
            precise_sliding_num_list.append(np.expand_dims(sample_segment['precise_sliding_num'], axis=0).copy())

        feature = copy.deepcopy(torch.concat(feature_list, dim=0))
        labels = copy.deepcopy(np.concatenate(labels_list, axis=0).astype(np.int64))
        masks = copy.deepcopy(np.concatenate(masks_list, axis=0).astype(np.float32))
        precise_sliding_num = copy.deepcopy(np.concatenate(precise_sliding_num_list, axis=0).astype(np.float32))

        # compose result
        data_dict = {}
        data_dict['feature'] = feature
        data_dict['raw_feature'] = copy.deepcopy(feature)
        data_dict['labels'] = labels
        data_dict['masks'] = masks
        data_dict['precise_sliding_num'] = precise_sliding_num
        data_dict['vid_list'] = vid_list
        return data_dict
    
    def _get_end_videos_clip(self):
        # compose result
        data_dict = {}
        data_dict['feature'] = 0
        data_dict['raw_feature'] = 0
        data_dict['labels'] = 0
        data_dict['masks'] = 0
        data_dict['vid_list'] = []
        data_dict['sliding_num'] = 0
        data_dict['precise_sliding_num'] = 0
        data_dict['step'] = self.step_num
        data_dict['current_sliding_cnt'] = -1
        return data_dict
