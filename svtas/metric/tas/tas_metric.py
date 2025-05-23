'''
Author: Thyssen Wen
Date: 2022-03-21 11:12:50
LastEditors  : Thyssen Wen
LastEditTime : 2022-12-12 20:12:57
Description: metric class
FilePath     : /SVTAS/svtas/metric/temporal_action_segmentation/temporal_action_segmentation_metric.py
'''
import numpy as np
import os
from .tas_base_class import BaseTASegmentationMetric
from ..builder import METRIC

@METRIC.register()
class TASegmentationMetric(BaseTASegmentationMetric):
    """
    Test for Video Segmentation based model.
    """

    def __init__(self,
                 overlap,
                 actions_map_file_path,
                 train_mode=False,
                 file_output=False,
                 score_output=False,
                 gt_file_need=True,
                 output_format="txt",
                 output_dir="output/results/pred_gt_list/",
                 score_output_dir="output/results/analysis/"):
        """prepare for metrics
        """
        super().__init__(overlap, actions_map_file_path, train_mode,
                         file_output, score_output, gt_file_need, output_format, output_dir, score_output_dir)
    
    def update(self, vid, ground_truth_batch, outputs):
        """update metrics during each iter
        """
        # list [N, T]
        predicted_batch = outputs['predict']
        # list [N, C, T]
        output_np_batch = outputs['output_np']

        single_batch_f1 = 0.
        single_batch_acc = 0.

        if len(vid) != len(predicted_batch):
            repet_rate = len(predicted_batch) // len(vid)
            vid = [val for val in vid for i in range(repet_rate)]
        for bs in range(len(predicted_batch)):
            predicted = predicted_batch[bs]
            output_np = output_np_batch[bs]
            groundTruth = ground_truth_batch[bs]

            if type(predicted) is not np.ndarray:
                outputs_np = predicted.numpy()
                outputs_arr = output_np.numpy()
                gt_np = groundTruth.numpy()
            else:
                outputs_np = predicted
                outputs_arr = output_np
                gt_np = groundTruth
            
            if self.score_output is True and self.train_mode is False:
                score_output_path = os.path.join(self.score_output_dir, vid[bs] + ".npy")
                np.save(score_output_path, output_np)

            result = self._transform_model_result(vid[bs], outputs_np, gt_np, outputs_arr)
            recog_content, gt_content, pred_detection, gt_detection = result
            single_f1, acc = self._update_score(recog_content, gt_content)
            single_batch_f1 += single_f1
            single_batch_acc += acc
        return single_batch_acc / len(predicted_batch)

    def accumulate(self):
        """accumulate metrics when finished all iters.
        """
        metric_dict = self._compute_metrics()
        self._log_metrics(metric_dict)
        self._clear_for_next_epoch()

        return metric_dict
