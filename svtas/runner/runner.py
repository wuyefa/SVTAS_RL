'''
Author: Thyssen Wen
Date: 2022-03-21 15:22:51
LastEditors  : Thyssen Wen
LastEditTime : 2023-04-25 11:19:56
Description: runner script
FilePath     : /SVTAS/svtas/runner/runner.py
'''
import torch
import time
from ..utils.logger import log_batch, AverageMeter, get_logger
import torch.distributed as dist

try:
    from apex import amp
except:
    pass

def reduce_mean(tensor, nprocs):
    rt = tensor.clone()
    dist.all_reduce(rt, op=dist.ReduceOp.SUM) # sum-up as the all-reduce operation
    rt /= nprocs # NOTE this is necessary, since all_reduce here do not perform average 
    return rt

class Runner():
    def __init__(self,
                 logger,
                 video_batch_size,
                 Metric,
                 cfg,
                 model,
                 post_processing,
                 record_dict=None,
                 criterion=None,
                 optimizer=None,
                 grad_clip=None,
                 use_amp=False,
                 nprocs=1,
                 local_rank=-1,
                 runner_mode='train',
                 need_grad_accumulate=True):
        self.optimizer = optimizer
        self.grad_clip = grad_clip
        self.logger = logger
        self.video_batch_size = video_batch_size
        self.Metric = Metric
        self.record_dict = record_dict
        self.cfg = cfg
        self.model = model
        self.criterion = criterion
        self.post_processing = post_processing
        self.nprocs = nprocs
        self.local_rank = local_rank
        self.use_amp = use_amp
        self.need_grad_accumulate = need_grad_accumulate

        assert runner_mode in ['train', 'validation', 'test'], "Not support this runner mode: " + runner_mode
        self.runner_mode = runner_mode
    
    def _init_loss_dict(self):
        self.loss_dict = {}
        if self.record_dict is not None:
            for key, value in self.record_dict.items():
                if key.endswith("loss"):
                    if not self.need_grad_accumulate:
                        setattr(value, "output_mean", True)
                        self.loss_dict[key] = value
                    else:
                        self.loss_dict[key] = 0.
    
    def _update_loss_dict(self, input_loss_dict):
        for key, value in self.loss_dict.items():
            if not isinstance(value, AverageMeter):
                self.loss_dict[key] = self.loss_dict[key] + input_loss_dict[key].detach().clone()
            else:
                self.loss_dict[key].update(input_loss_dict[key].detach().clone())
    
    def _distribute_sync_loss_dict(self):
        for key, value in self.loss_dict.items():
            if key != "loss":
                if not isinstance(value, AverageMeter):
                    self.loss_dict[key] = reduce_mean(value, self.nprocs)
                else:
                    self.loss_dict[key].update(reduce_mean(value, self.nprocs))

    def _log_loss_dict(self):
        for key, value in self.loss_dict.items():
                if not isinstance(value, AverageMeter):
                    self.record_dict[key].update(value.item(), self.video_batch_size)

    def epoch_init(self):
        # batch videos sampler
        self._init_loss_dict()
        self.seg_acc = 0.
        self.post_processing.init_flag = False
        self.current_step = 0
        self.current_step_vid_list = None

        if self.runner_mode in ['train']:
            self.model.train()
            self.b_tic = time.time()
            # reset recoder
            for _, recod in self.record_dict.items():
                recod.reset()

        elif self.runner_mode in ['validation', 'test']:
            self.model.eval()
            self.b_tic = time.time()
            # reset recoder
            for _, recod in self.record_dict.items():
                recod.reset()
        
        
    def batch_end_step(self, sliding_num, vid_list, step, epoch):
        if self.runner_mode in ['train']:
            if self.need_grad_accumulate:
                self.optimizer.step()
            self.optimizer.zero_grad()

        # clear memory buffer
        if self.nprocs > 1:
            self.model.module._clear_memory_buffer()
        else:
            self.model._clear_memory_buffer()

        # get pred result
        pred_score_list, pred_cls_list, ground_truth_list = self.post_processing.output()
        outputs = dict(predict=pred_cls_list,
                        output_np=pred_score_list)
        vid = self.current_step_vid_list

        if self.runner_mode in ['validation', 'test']:
            # distribution                
            if self.nprocs > 1:
                collect_dict = dict(
                    predict=pred_cls_list,
                    output_np=pred_score_list,
                    ground_truth=ground_truth_list,
                    vid=self.current_step_vid_list
                )
                gather_objects = [collect_dict for _ in range(self.nprocs)] # any picklable object
                output_list = [None for _ in range(self.nprocs)]
                dist.all_gather_object(output_list, gather_objects[dist.get_rank()])
                # collect
                pred_cls_list_i = []
                pred_score_list_i = []
                ground_truth_list_i = []
                vid_i = []
                for output_dict in output_list:
                    pred_cls_list_i = pred_cls_list_i + output_dict["predict"]
                    pred_score_list_i = pred_score_list_i + output_dict["output_np"]
                    ground_truth_list_i = ground_truth_list_i + output_dict["ground_truth"]
                    vid_i = vid_i + output_dict["vid"]
                outputs = dict(predict=pred_cls_list_i,
                                output_np=pred_score_list_i)
                ground_truth_list = ground_truth_list_i
                vid = vid_i
        
        for k, v in self.Metric.items():
            acc = v.update(vid, ground_truth_list, outputs)

        self.current_step_vid_list = vid_list
        if len(self.current_step_vid_list) > 0:
            self.post_processing.init_scores(sliding_num, len(vid_list))
        

        if self.nprocs > 1:
            torch.distributed.barrier()
            self._distribute_sync_loss_dict()

        # logger
        if self.runner_mode in ['train']:
            self.record_dict['lr'].update(self.optimizer.state_dict()['param_groups'][0]['lr'], self.video_batch_size)
        
        self._log_loss_dict()
        self.record_dict['batch_time'].update(time.time() - self.b_tic)
        self.record_dict['Acc'].update(acc, self.video_batch_size)
        self.record_dict['Seg_Acc'].update(self.seg_acc, self.video_batch_size)

        self._init_loss_dict()
        self.seg_acc = 0.

        if self.current_step % self.cfg.get("log_interval", 10) == 0:
            ips = "ips: {:.5f} instance/sec.".format(
                self.video_batch_size / self.record_dict["batch_time"].val)
            if self.runner_mode in ['train']:
                log_batch(self.record_dict, self.current_step, epoch + 1, self.cfg.epochs, "train", ips, self.logger)
            elif self.runner_mode in ['validation']:
                log_batch(self.record_dict, self.current_step, epoch + 1, self.cfg.epochs, "validation", ips, self.logger)
            elif self.runner_mode in ['test']:
                log_batch(self.record_dict, self.current_step, 1, 1, "test", ips, self.logger)

        self.b_tic = time.time()

        self.current_step = step
    
    def _model_forward(self, data_dict):
        # move data
        input_data = {}
        for key, value in data_dict.items():
            if torch.is_tensor(value):
                if torch.cuda.is_available():
                    input_data[key] = value.cuda()
                else:
                    input_data[key] = value
        if not self.need_grad_accumulate:
            input_data['precise_sliding_num'] = torch.ones_like(input_data['precise_sliding_num'])

        outputs = self.model(input_data)
        loss_dict = self.criterion(outputs, input_data)

        loss = loss_dict["loss"]
        if self.runner_mode in ['train']:
            if self.use_amp is True:
                with amp.scale_loss(loss, self.optimizer) as scaled_loss:
                    scaled_loss.backward()
            else:
                loss.backward()
                if self.grad_clip is not None:
                    for param_group in self.optimizer.param_groups:
                        self.grad_clip(param_group['params'])

            if not self.need_grad_accumulate:
                self.optimizer.step()
                self.optimizer.zero_grad()

        score = outputs['output']
        return score, loss_dict

    def run_one_clip(self, data_dict):
        vid_list = data_dict['vid_list']
        sliding_num = data_dict['sliding_num']
        idx = data_dict['current_sliding_cnt']
        labels = data_dict['labels']
        # train segment
        if self.nprocs > 1 and idx < sliding_num - 1 and self.use_amp is False:
            with self.model.no_sync():
                # multi-gpus
                score, loss_dict = self._model_forward(data_dict)
        else:
            # single gpu
            score, loss_dict = self._model_forward(data_dict)
            
        with torch.no_grad():
            if self.post_processing.init_flag is not True:
                self.post_processing.init_scores(sliding_num, len(vid_list))
                self.current_step_vid_list = vid_list
            self.seg_acc += self.post_processing.update(score, labels, idx) / sliding_num

            # logger loss
            self._update_loss_dict(loss_dict)

    def run_one_iter(self, data, r_tic=None, epoch=None):
        # videos sliding stream train
        self.record_dict['reader_time'].update(time.time() - r_tic)

        for sliding_seg in data:
            step = sliding_seg['step']
            vid_list = sliding_seg['vid_list']
            sliding_num = sliding_seg['sliding_num']
            idx = sliding_seg['current_sliding_cnt']
            # wheather next step
            if self.current_step != step or (len(vid_list) <= 0 and step == 1):
                self.batch_end_step(sliding_num=sliding_num, vid_list=vid_list, step=step, epoch=epoch)

            if idx >= 0: 
                self.run_one_clip(sliding_seg)
    
    def run_one_batch(self, data, r_tic=None, epoch=None):
        # videos batch train
        self.record_dict['reader_time'].update(time.time() - r_tic)

        for sliding_seg in data:
            step = self.current_step
            vid_list = sliding_seg['vid_list']
            sliding_num = sliding_seg['sliding_num']
            idx = sliding_seg['current_sliding_cnt']

            # run one batch
            self.run_one_clip(sliding_seg)
            self.batch_end_step(sliding_num=sliding_num, vid_list=vid_list, step=step, epoch=epoch)
            self.current_step = self.current_step + 1
            self.post_processing.init_flag = False
