'''
Author       : Thyssen Wen
Date         : 2022-11-04 19:50:40
LastEditors  : Thyssen Wen
LastEditTime : 2023-04-26 18:22:46
Description  : file content
FilePath     : /SVTAS/config/svtas/feature/block_recurrent_transformer_rl_50salads.py
'''
_base_ = [
    '../../_base_/schedules/optimizer/adamw.py', '../../_base_/schedules/lr/cosine_50e.py',
    '../../_base_/default_runtime.py', '../../_base_/collater/stream_compose.py',
    '../../_base_/dataset/50salads/50salads_stream_feature.py'
]

split = 1
num_classes = 19
sample_rate = 8
ignore_index = -100
epochs = 80
clip_seg_num = 128
dim = 1024
batch_size = 1
sliding_window = clip_seg_num * sample_rate
model_name = "Stream_BRT_"+str(clip_seg_num)+"x"+str(sample_rate)+"_50salads_split" + str(split)

MODEL = dict(
    architecture = "FeatureSegmentation",
    backbone = None,
    neck = None,
    head = dict(
        name = "BRTSegmentationHead",
        num_head=1,
        state_len=512,
        causal=False,
        num_decoders=3,
        encoder_num_layers=8,
        decoder_num_layers=8,
        num_f_maps=128,
        dropout=0.5,
        input_dim=dim,
        num_classes=num_classes,
        channel_masking_rate=0.2,
        sample_rate=sample_rate
    ),
    loss = dict(
        name = "SegmentationLoss",
        num_classes = num_classes,
        smooth_weight=0.15,
        sample_rate = sample_rate,
        ignore_index = ignore_index
    )
)

POSTPRECESSING = dict(
    name = "StreamScorePostProcessing",
    sliding_window = sliding_window,
    ignore_index = ignore_index
)

DATASET = dict(
    temporal_clip_batch_size = 3,
    video_batch_size = batch_size,
    num_workers = 2,
    train = dict(
        file_path = "./data/50salads/splits/train.split" + str(split) + ".bundle",
        feature_path = './data/50salads/extract_features',
        sliding_window = sliding_window,
    ),
    test = dict(
        file_path = "./data/50salads/splits/test.split" + str(split) + ".bundle",
        feature_path = './data/50salads/extract_features',
        sliding_window = sliding_window,
    )
)

OPTIMIZER = dict(
    name = "AdamWOptimizer",
    learning_rate = 0.0005,
    weight_decay = 1e-4,
    betas = (0.9, 0.999),
    need_grad_accumulate = False,
    finetuning_scale_factor=0.1,
    no_decay_key = [],
    finetuning_key = [],
    freeze_key = [],
)

LRSCHEDULER = dict(
    name = "CosineAnnealingLR",
    T_max = epochs,
    eta_min = 0.00001,
)
PIPELINE = dict(
    train = dict(
        name = "BasePipline",
        decode = dict(
            name='FeatureDecoder',
            backend=dict(
                    name='NPYContainer',
                    is_transpose=False,
                    temporal_dim=-1,
                    revesive_name=[(r'(mp4|avi)', 'npy')]
                 )
        ),
        sample = dict(
            name = "FeatureStreamSampler",
            is_train = True,
            sample_rate_dict={"feature":sample_rate, "labels":sample_rate},
            clip_seg_num_dict={"feature":clip_seg_num, "labels":clip_seg_num},
            sliding_window_dict={"feature":sliding_window, "labels":sliding_window},
            sample_add_key_pair={"frames":"feature"},
            feature_dim_dict={"feature":dim},
            sample_mode = "uniform"
        ),
        transform = dict(
            name = "FeatureStreamTransform",
            transform_dict = dict(
                feature = [dict(XToTensor = None)]
            )
        )
    ),
    test = dict(
        name = "BasePipline",
        decode = dict(
            name='FeatureDecoder',
            backend=dict(
                    name='NPYContainer',
                    is_transpose=False,
                    temporal_dim=-1,
                    revesive_name=[(r'(mp4|avi)', 'npy')]
                 )
        ),
        sample = dict(
            name = "FeatureStreamSampler",
            is_train = False,
            sample_rate_dict={"feature":sample_rate, "labels":sample_rate},
            clip_seg_num_dict={"feature":clip_seg_num, "labels":clip_seg_num},
            sliding_window_dict={"feature":sliding_window, "labels":sliding_window},
            sample_add_key_pair={"frames":"feature"},
            feature_dim_dict={"feature":dim},
            sample_mode = "uniform"
        ),
        transform = dict(
            name = "FeatureStreamTransform",
            transform_dict = dict(
                feature = [dict(XToTensor = None)]
            )
        )
    )
)
