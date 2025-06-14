import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Force CPU mode

import numpy as np
import argparse
import torch
import copy
import cv2
import os
import moviepy.video.io.ImageSequenceClip

from pose.script.dwpose import DWposeDetector, draw_pose
from pose.script.util import size_calculate, warpAffine_kps



'''
    Detect dwpose from img, then align it by scale parameters
    img: frame from the pose video
    detector: DWpose
    scales: scale parameters
'''
def align_img(img, pose_ori, scales, detect_resolution, image_resolution):

    body_pose = copy.deepcopy(pose_ori['bodies']['candidate'])
    hands = copy.deepcopy(pose_ori['hands'])
    faces = copy.deepcopy(pose_ori['faces'])

    '''
    计算逻辑:
    0. 该函数内进行绝对变换，始终保持人体中心点 body_pose[1] 不变
    1. 先把 ref 和 pose 的高 resize 到一样，且都保持原来的长宽比。
    2. 用点在图中的实际坐标来计算。
    3. 实际计算中，把h的坐标归一化到 [0, 1],  w为[0, W/H]
    4. 由于 dwpose 的输出本来就是归一化的坐标，所以h不需要变，w要乘W/H
    注意：dwpose 输出是 (w, h)
    '''

    # h不变，w缩放到原比例
    H_in, W_in, C_in = img.shape 
    video_ratio = W_in / H_in
    body_pose[:, 0]  = body_pose[:, 0] * video_ratio
    hands[:, :, 0] = hands[:, :, 0] * video_ratio
    faces[:, :, 0] = faces[:, :, 0] * video_ratio

    # scales of 10 body parts 
    scale_neck      = scales["scale_neck"] 
    scale_face      = scales["scale_face"]
    scale_shoulder  = scales["scale_shoulder"]
    scale_arm_upper = scales["scale_arm_upper"]
    scale_arm_lower = scales["scale_arm_lower"]
    scale_hand      = scales["scale_hand"]
    scale_body_len  = scales["scale_body_len"]
    scale_leg_upper = scales["scale_leg_upper"]
    scale_leg_lower = scales["scale_leg_lower"]

    scale_sum = 0
    count = 0
    scale_list = [scale_neck, scale_face, scale_shoulder, scale_arm_upper, scale_arm_lower, scale_hand, scale_body_len, scale_leg_upper, scale_leg_lower]
    for i in range(len(scale_list)):
        if not np.isinf(scale_list[i]):
            scale_sum = scale_sum + scale_list[i]
            count = count + 1
    for i in range(len(scale_list)):
        if np.isinf(scale_list[i]):   
            scale_list[i] = scale_sum/count



    # offsets of each part 
    offset = dict()
    offset["14_15_16_17_to_0"] = body_pose[[14,15,16,17], :] - body_pose[[0], :] 
    offset["3_to_2"] = body_pose[[3], :] - body_pose[[2], :] 
    offset["4_to_3"] = body_pose[[4], :] - body_pose[[3], :] 
    offset["6_to_5"] = body_pose[[6], :] - body_pose[[5], :] 
    offset["7_to_6"] = body_pose[[7], :] - body_pose[[6], :] 
    offset["9_to_8"] = body_pose[[9], :] - body_pose[[8], :] 
    offset["10_to_9"] = body_pose[[10], :] - body_pose[[9], :] 
    offset["12_to_11"] = body_pose[[12], :] - body_pose[[11], :] 
    offset["13_to_12"] = body_pose[[13], :] - body_pose[[12], :] 
    offset["hand_left_to_4"] = hands[1, :, :] - body_pose[[4], :]
    offset["hand_right_to_7"] = hands[0, :, :] - body_pose[[7], :]

    # neck
    c_ = body_pose[1]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_neck)

    neck = body_pose[[0], :] 
    neck = warpAffine_kps(neck, M)
    body_pose[[0], :] = neck

    # body_pose_up_shoulder
    c_ = body_pose[0]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_face)

    body_pose_up_shoulder = offset["14_15_16_17_to_0"] + body_pose[[0], :]
    body_pose_up_shoulder = warpAffine_kps(body_pose_up_shoulder, M)
    body_pose[[14,15,16,17], :] = body_pose_up_shoulder

    # shoulder 
    c_ = body_pose[1]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_shoulder)

    body_pose_shoulder = body_pose[[2,5], :] 
    body_pose_shoulder = warpAffine_kps(body_pose_shoulder, M) 
    body_pose[[2,5], :] = body_pose_shoulder

    # arm upper left
    c_ = body_pose[2]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_arm_upper)
 
    elbow = offset["3_to_2"] + body_pose[[2], :]
    elbow = warpAffine_kps(elbow, M)
    body_pose[[3], :] = elbow

    # arm lower left
    c_ = body_pose[3]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_arm_lower)
 
    wrist = offset["4_to_3"] + body_pose[[3], :]
    wrist = warpAffine_kps(wrist, M)
    body_pose[[4], :] = wrist

    # hand left
    c_ = body_pose[4]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_hand)
 
    hand = offset["hand_left_to_4"] + body_pose[[4], :]
    hand = warpAffine_kps(hand, M)
    hands[1, :, :] = hand

    # arm upper right
    c_ = body_pose[5]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_arm_upper)
 
    elbow = offset["6_to_5"] + body_pose[[5], :]
    elbow = warpAffine_kps(elbow, M)
    body_pose[[6], :] = elbow

    # arm lower right
    c_ = body_pose[6]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_arm_lower)
 
    wrist = offset["7_to_6"] + body_pose[[6], :]
    wrist = warpAffine_kps(wrist, M)
    body_pose[[7], :] = wrist

    # hand right
    c_ = body_pose[7]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_hand)
 
    hand = offset["hand_right_to_7"] + body_pose[[7], :]
    hand = warpAffine_kps(hand, M)
    hands[0, :, :] = hand

    # body len
    c_ = body_pose[1]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_body_len)

    body_len = body_pose[[8,11], :] 
    body_len = warpAffine_kps(body_len, M)
    body_pose[[8,11], :] = body_len

    # leg upper left
    c_ = body_pose[8]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_leg_upper)
 
    knee = offset["9_to_8"] + body_pose[[8], :]
    knee = warpAffine_kps(knee, M)
    body_pose[[9], :] = knee

    # leg lower left
    c_ = body_pose[9]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_leg_lower)
 
    ankle = offset["10_to_9"] + body_pose[[9], :]
    ankle = warpAffine_kps(ankle, M)
    body_pose[[10], :] = ankle

    # leg upper right
    c_ = body_pose[11]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_leg_upper)
 
    knee = offset["12_to_11"] + body_pose[[11], :]
    knee = warpAffine_kps(knee, M)
    body_pose[[12], :] = knee

    # leg lower right
    c_ = body_pose[12]
    cx = c_[0]
    cy = c_[1]
    M = cv2.getRotationMatrix2D((cx,cy), 0, scale_leg_lower)
 
    ankle = offset["13_to_12"] + body_pose[[12], :]
    ankle = warpAffine_kps(ankle, M)
    body_pose[[13], :] = ankle

    # none part
    body_pose_none = pose_ori['bodies']['candidate'] == -1.
    hands_none = pose_ori['hands'] == -1.
    faces_none = pose_ori['faces'] == -1.

    body_pose[body_pose_none] = -1.
    hands[hands_none] = -1. 
    nan = float('nan')
    if len(hands[np.isnan(hands)]) > 0:
        print('nan')
    faces[faces_none] = -1.

    # last check nan -> -1.
    body_pose = np.nan_to_num(body_pose, nan=-1.)
    hands = np.nan_to_num(hands, nan=-1.)
    faces = np.nan_to_num(faces, nan=-1.)

    # return
    pose_align = copy.deepcopy(pose_ori)
    pose_align['bodies']['candidate'] = body_pose
    pose_align['hands'] = hands
    pose_align['faces'] = faces

    return pose_align



def run_align_video_with_filterPose_translate_smooth(args):

    vidfn=args.vidfn
    imgfn_refer=args.imgfn_refer
    outfn=args.outfn
    
    video = cv2.VideoCapture(vidfn)
    width= video.get(cv2.CAP_PROP_FRAME_WIDTH)
    height= video.get(cv2.CAP_PROP_FRAME_HEIGHT)
 
    total_frame= video.get(cv2.CAP_PROP_FRAME_COUNT)
    fps= video.get(cv2.CAP_PROP_FPS)

    print("height:", height)
    print("width:", width)
    print("fps:", fps)

    H_in, W_in  = height, width
    H_out, W_out = size_calculate(H_in,W_in,args.detect_resolution) 
    H_out, W_out = size_calculate(H_out,W_out,args.image_resolution) 

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    detector = DWposeDetector(
        det_config = args.yolox_config, 
        det_ckpt = args.yolox_ckpt,
        pose_config = args.dwpose_config, 
        pose_ckpt = args.dwpose_ckpt, 
        keypoints_only=False
        )    
    detector = detector.to(device)

    refer_img = cv2.imread(imgfn_refer)
    output_refer, pose_refer = detector(refer_img,detect_resolution=args.detect_resolution, image_resolution=args.image_resolution, output_type='cv2',return_pose_dict=True)
    body_ref_img  = pose_refer['bodies']['candidate']
    hands_ref_img = pose_refer['hands']
    faces_ref_img = pose_refer['faces']
    output_refer = cv2.cvtColor(output_refer, cv2.COLOR_RGB2BGR)
    

    skip_frames = args.align_frame
    max_frame = args.max_frame
    pose_list, video_frame_buffer, video_pose_buffer = [], [], []


    cap = cv2.VideoCapture('2.mp4')     # 读取视频
    while cap.isOpened():               # 当视频被打开时：
        ret, frame = cap.read()         # 读取视频，读取到的某一帧存储到frame，若是读取成功，ret为True，反之为False
        if ret:                         # 若是读取成功
            cv2.imshow('frame', frame)  # 显示读取到的这一帧画面
            key = cv2.waitKey(25)       # 等待一段时间，并且检测键盘输入
            if key == ord('q'):         # 若是键盘输入'q',则退出，释放视频
                cap.release()           # 释放视频
                break
        else:
            cap.release()
    cv2.destroyAllWindows()             # 关闭所有窗口


    for i in range(max_frame):
        ret, img = video.read()
        if img is None: 
            break 
        else: 
            if i < skip_frames:
                continue           
            video_frame_buffer.append(img)


       
        # estimate scale parameters by the 1st frame in the video
        if i==skip_frames:
            output_1st_img, pose_1st_img = detector(img, args.detect_resolution, args.image_resolution, output_type='cv2', return_pose_dict=True)
            body_1st_img  = pose_1st_img['bodies']['candidate']
            hands_1st_img = pose_1st_img['hands']
            faces_1st_img = pose_1st_img['faces']

            '''
            计算逻辑:
            1. 先把 ref 和 pose 的高 resize 到一样，且都保持原来的长宽比。
            2. 用点在图中的实际坐标来计算。
            3. 实际计算中，把h的坐标归一化到 [0, 1],  w为[0, W/H]
            4. 由于 dwpose 的输出本来就是归一化的坐标，所以h不需要变，w要乘W/H
            注意：dwpose 输出是 (w, h)
            '''
            
            # h不变，w缩放到原比例
            ref_H, ref_W = refer_img.shape[0], refer_img.shape[1]
            ref_ratio = ref_W / ref_H
            body_ref_img[:, 0]  = body_ref_img[:, 0] * ref_ratio
            hands_ref_img[:, :, 0] = hands_ref_img[:, :, 0] * ref_ratio
            faces_ref_img[:, :, 0] = faces_ref_img[:, :, 0] * ref_ratio

            video_ratio = width / height
            body_1st_img[:, 0]  = body_1st_img[:, 0] * video_ratio
            hands_1st_img[:, :, 0] = hands_1st_img[:, :, 0] * video_ratio
            faces_1st_img[:, :, 0] = faces_1st_img[:, :, 0] * video_ratio

            # scale
            align_args = dict()
            
            dist_1st_img = np.linalg.norm(body_1st_img[0]-body_1st_img[1])   # 0.078   
            dist_ref_img = np.linalg.norm(body_ref_img[0]-body_ref_img[1])   # 0.106
            align_args["scale_neck"] = dist_ref_img / dist_1st_img  # align / pose = ref / 1st

            dist_1st_img = np.linalg.norm(body_1st_img[16]-body_1st_img[17])
            dist_ref_img = np.linalg.norm(body_ref_img[16]-body_ref_img[17])
            align_args["scale_face"] = dist_ref_img / dist_1st_img

            dist_1st_img = np.linalg.norm(body_1st_img[2]-body_1st_img[5])  # 0.112
            dist_ref_img = np.linalg.norm(body_ref_img[2]-body_ref_img[5])  # 0.174
            align_args["scale_shoulder"] = dist_ref_img / dist_1st_img  

            dist_1st_img = np.linalg.norm(body_1st_img[2]-body_1st_img[3])  # 0.895
            dist_ref_img = np.linalg.norm(body_ref_img[2]-body_ref_img[3])  # 0.134
            s1 = dist_ref_img / dist_1st_img
            dist_1st_img = np.linalg.norm(body_1st_img[5]-body_1st_img[6])
            dist_ref_img = np.linalg.norm(body_ref_img[5]-body_ref_img[6])
            s2 = dist_ref_img / dist_1st_img
            align_args["scale_arm_upper"] = (s1+s2)/2 # 1.548

            dist_1st_img = np.linalg.norm(body_1st_img[3]-body_1st_img[4])
            dist_ref_img = np.linalg.norm(body_ref_img[3]-body_ref_img[4])
            s1 = dist_ref_img / dist_1st_img
            dist_1st_img = np.linalg.norm(body_1st_img[6]-body_1st_img[7])
            dist_ref_img = np.linalg.norm(body_ref_img[6]-body_ref_img[7])
            s2 = dist_ref_img / dist_1st_img
            align_args["scale_arm_lower"] = (s1+s2)/2

            # hand
            dist_1st_img = np.zeros(10)
            dist_ref_img = np.zeros(10)      
             
            dist_1st_img[0] = np.linalg.norm(hands_1st_img[0,0]-hands_1st_img[0,1])
            dist_1st_img[1] = np.linalg.norm(hands_1st_img[0,0]-hands_1st_img[0,5])
            dist_1st_img[2] = np.linalg.norm(hands_1st_img[0,0]-hands_1st_img[0,9])
            dist_1st_img[3] = np.linalg.norm(hands_1st_img[0,0]-hands_1st_img[0,13])
            dist_1st_img[4] = np.linalg.norm(hands_1st_img[0,0]-hands_1st_img[0,17])
            dist_1st_img[5] = np.linalg.norm(hands_1st_img[1,0]-hands_1st_img[1,1])
            dist_1st_img[6] = np.linalg.norm(hands_1st_img[1,0]-hands_1st_img[1,5])
            dist_1st_img[7] = np.linalg.norm(hands_1st_img[1,0]-hands_1st_img[1,9])
            dist_1st_img[8] = np.linalg.norm(hands_1st_img[1,0]-hands_1st_img[1,13])
            dist_1st_img[9] = np.linalg.norm(hands_1st_img[1,0]-hands_1st_img[1,17])

            dist_ref_img[0] = np.linalg.norm(hands_ref_img[0,0]-hands_ref_img[0,1])
            dist_ref_img[1] = np.linalg.norm(hands_ref_img[0,0]-hands_ref_img[0,5])
            dist_ref_img[2] = np.linalg.norm(hands_ref_img[0,0]-hands_ref_img[0,9])
            dist_ref_img[3] = np.linalg.norm(hands_ref_img[0,0]-hands_ref_img[0,13])
            dist_ref_img[4] = np.linalg.norm(hands_ref_img[0,0]-hands_ref_img[0,17])
            dist_ref_img[5] = np.linalg.norm(hands_ref_img[1,0]-hands_ref_img[1,1])
            dist_ref_img[6] = np.linalg.norm(hands_ref_img[1,0]-hands_ref_img[1,5])
            dist_ref_img[7] = np.linalg.norm(hands_ref_img[1,0]-hands_ref_img[1,9])
            dist_ref_img[8] = np.linalg.norm(hands_ref_img[1,0]-hands_ref_img[1,13])
            dist_ref_img[9] = np.linalg.norm(hands_ref_img[1,0]-hands_ref_img[1,17])

            ratio = 0   
            count = 0
            for i in range (10): 
                if dist_1st_img[i] != 0:
                    ratio = ratio + dist_ref_img[i]/dist_1st_img[i]
                    count = count + 1
            if count!=0:
                align_args["scale_hand"] = (ratio/count+align_args["scale_arm_upper"]+align_args["scale_arm_lower"])/3
            else:
                align_args["scale_hand"] = (align_args["scale_arm_upper"]+align_args["scale_arm_lower"])/2

            # body 
            dist_1st_img = np.linalg.norm(body_1st_img[1] - (body_1st_img[8] + body_1st_img[11])/2 )
            dist_ref_img = np.linalg.norm(body_ref_img[1] - (body_ref_img[8] + body_ref_img[11])/2 )
            align_args["scale_body_len"]=dist_ref_img / dist_1st_img

            dist_1st_img = np.linalg.norm(body_1st_img[8]-body_1st_img[9])
            dist_ref_img = np.linalg.norm(body_ref_img[8]-body_ref_img[9])
            s1 = dist_ref_img / dist_1st_img
            dist_1st_img = np.linalg.norm(body_1st_img[11]-body_1st_img[12])
            dist_ref_img = np.linalg.norm(body_ref_img[11]-body_ref_img[12])
            s2 = dist_ref_img / dist_1st_img
            align_args["scale_leg_upper"] = (s1+s2)/2

            dist_1st_img = np.linalg.norm(body_1st_img[9]-body_1st_img[10])
            dist_ref_img = np.linalg.norm(body_ref_img[9]-body_ref_img[10])
            s1 = dist_ref_img / dist_1st_img
            dist_1st_img = np.linalg.norm(body_1st_img[12]-body_1st_img[13])
            dist_ref_img = np.linalg.norm(body_ref_img[12]-body_ref_img[13])
            s2 = dist_ref_img / dist_1st_img
            align_args["scale_leg_lower"] = (s1+s2)/2

            ####################
            ####################
            # need adjust nan
            for k,v in align_args.items():
                if np.isnan(v):
                    align_args[k]=1

            # centre offset (the offset of key point 1)
            offset = body_ref_img[1] - body_1st_img[1]
        
    
        # pose align
        pose_img, pose_ori = detector(img, args.detect_resolution, args.image_resolution, output_type='cv2', return_pose_dict=True)
        video_pose_buffer.append(pose_img)
        pose_align = align_img(img, pose_ori, align_args, args.detect_resolution, args.image_resolution)
        

        # add centre offset
        pose = pose_align
        pose['bodies']['candidate'] = pose['bodies']['candidate'] + offset
        pose['hands'] = pose['hands'] + offset
        pose['faces'] = pose['faces'] + offset


        # h不变，w从绝对坐标缩放回0-1 注意这里要回到ref的坐标系
        pose['bodies']['candidate'][:, 0] = pose['bodies']['candidate'][:, 0] / ref_ratio
        pose['hands'][:, :, 0] = pose['hands'][:, :, 0] / ref_ratio
        pose['faces'][:, :, 0] = pose['faces'][:, :, 0] / ref_ratio
        pose_list.append(pose)

    # stack
    body_list  = [pose['bodies']['candidate'][:18] for pose in pose_list]
    body_list_subset = [pose['bodies']['subset'][:1] for pose in pose_list]
    hands_list = [pose['hands'][:2] for pose in pose_list]
    faces_list = [pose['faces'][:1] for pose in pose_list]
   
    body_seq         = np.stack(body_list       , axis=0)
    body_seq_subset  = np.stack(body_list_subset, axis=0)
    hands_seq        = np.stack(hands_list      , axis=0)
    faces_seq        = np.stack(faces_list      , axis=0)


    # concatenate and paint results
    H = 768 # paint height
    W1 = int((H/ref_H * ref_W)//2 *2)
    W2 = int((H/height * width)//2 *2)
    result_demo = [] # = Writer(args, None, H, 3*W1+2*W2, outfn, fps)
    result_pose_only = [] # Writer(args, None, H, W1, args.outfn_align_pose_video, fps)
    for i in range(len(body_seq)):
        pose_t={}
        pose_t["bodies"]={}
        pose_t["bodies"]["candidate"]=body_seq[i]
        pose_t["bodies"]["subset"]=body_seq_subset[i]
        pose_t["hands"]=hands_seq[i]
        pose_t["faces"]=faces_seq[i]

        ref_img = cv2.cvtColor(refer_img, cv2.COLOR_RGB2BGR)
        ref_img = cv2.resize(ref_img, (W1, H))
        ref_pose= cv2.resize(output_refer, (W1, H))
        
        output_transformed = draw_pose(
            pose_t, 
            int(H_in*1024/W_in), 
            1024, 
            draw_face=False,
            )
        output_transformed = cv2.cvtColor(output_transformed, cv2.COLOR_BGR2RGB)
        output_transformed = cv2.resize(output_transformed, (W1, H))
        
        video_frame = cv2.resize(video_frame_buffer[i], (W2, H))
        video_pose  = cv2.resize(video_pose_buffer[i], (W2, H))

        res = np.concatenate([ref_img, ref_pose, output_transformed, video_frame, video_pose], axis=1)
        result_demo.append(res)
        result_pose_only.append(output_transformed)

    print(f"pose_list len: {len(pose_list)}")
    clip = moviepy.video.io.ImageSequenceClip.ImageSequenceClip(result_demo, fps=fps)
    clip.write_videofile(outfn, fps=fps)
    clip = moviepy.video.io.ImageSequenceClip.ImageSequenceClip(result_pose_only, fps=fps)
    clip.write_videofile(args.outfn_align_pose_video, fps=fps)
    print('pose align done')



def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--detect_resolution', type=int, default=512, help='detect_resolution')
    parser.add_argument('--image_resolution', type=int, default=720, help='image_resolution')

    parser.add_argument("--yolox_config",  type=str, default="./pose/config/yolox_l_8xb8-300e_coco.py")
    parser.add_argument("--dwpose_config", type=str, default="./pose/config/dwpose-l_384x288.py")
    parser.add_argument("--yolox_ckpt",  type=str, default="./pretrained_weights/dwpose/yolox_l_8x8_300e_coco.pth")
    parser.add_argument("--dwpose_ckpt", type=str, default="./pretrained_weights/dwpose/dw-ll_ucoco_384.pth")


    parser.add_argument('--align_frame', type=int, default=0, help='the frame index of the video to align')
    parser.add_argument('--max_frame', type=int, default=300, help='maximum frame number of the video to align')
    parser.add_argument('--imgfn_refer', type=str, default="./assets/images/0.jpg", help='refer image path')
    parser.add_argument('--vidfn', type=str, default="./assets/videos/0.mp4", help='Input video path')
    parser.add_argument('--outfn_align_pose_video', type=str, default=None, help='output path of the aligned video of the refer img')
    parser.add_argument('--outfn', type=str, default=None, help='Output path of the alignment visualization')
    args = parser.parse_args()
    
    if not os.path.exists("./assets/poses/align"):
        # os.makedirs("./assets/poses/")
        os.makedirs("./assets/poses/align")
        os.makedirs("./assets/poses/align_demo")
        
    img_name = os.path.basename(args.imgfn_refer).split('.')[0]
    video_name = os.path.basename(args.vidfn).split('.')[0]
    if args.outfn_align_pose_video is None:
        args.outfn_align_pose_video = "./assets/poses/align/img_{}_video_{}.mp4".format(img_name, video_name)
    if args.outfn is None:
        args.outfn = "./assets/poses/align_demo/img_{}_video_{}.mp4".format(img_name, video_name)

    run_align_video_with_filterPose_translate_smooth(args)


    
if __name__ == '__main__':
    main()
