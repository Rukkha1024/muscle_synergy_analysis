# -*- coding: utf-8 -*-
"""
Created on Wed Sep 11 09:57:16 2019

@author: Cju
"""
#연구실
zEventPathName = 'F:\\OneDrive - 청주대학교\\project\\squat\\event\\'
zAnglePathName = 'F:\\OneDrive - 청주대학교\\project\\squat\\angle\\'
zEMGPathName = 'F:\\OneDrive - 청주대학교\\project\\squat\\EMG\\'
zSavePathName = 'F:\\OneDrive - 청주대학교\\project\\squat\\'
#집
zEventPathName = 'C:\\Users\\Yushin Kim\\OneDrive - 청주대학교\\project\\squat\\event\\'
zAnglePathName = 'C:\\Users\\Yushin Kim\\OneDrive - 청주대학교\\project\\squat\\angle\\'
zEMGPathName = 'C:\\Users\\Yushin Kim\\OneDrive - 청주대학교\\project\\squat\\EMG\\'
zSavePathName = 'C:\\Users\\Yushin Kim\\OneDrive - 청주대학교\\project\\squat\\'

import os
import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
import pickle
import matplotlib.pyplot as plt

from scipy.signal import butter, filtfilt
def butter_lowpass_filter(data, cutoff, fs, order):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    y = filtfilt(b, a, data)
    return y
def butter_highpass_filter(data, cutoff, fs, order):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    y = filtfilt(b, a, data)
    return y

zId = 0
zTrial = 0
zSave = False


#데이터 이벤트    
os.chdir('{0}'.format(zEventPathName))
eventRawSet = []#시작과 끝 시간
eventPhaseSet = []#구간 소요 시간
for zId in range(20):
    eventRaw = np.array([])  # Initialize eventRaw before the loop
    eventPhase = np.array([])
    for zTrial in range(2):
        tempRaw = pd.read_table('SUB{0:02d}{1:02d}N.txt'.format(zId+1, zTrial+1))
        tempRaw = tempRaw.values
        tempRaw = np.array(tempRaw[1:], dtype=np.float64)
        tempRaw = tempRaw.flatten()
        tempRaw = tempRaw*1000 #emg 시간, 1000Hz에 맞춤
        #구간 소요 시간
        tempPhase = np.diff(tempRaw)
        
        eventRaw = np.concatenate((eventRaw, tempRaw))  # Append the new data
        eventPhase = np.concatenate((eventPhase, tempPhase))
    eventRawSet.append(eventRaw)
    eventPhaseSet.append(eventPhase)

eventRawSet = np.array(eventRawSet, dtype=np.int32) #정수로 변환


#각도
os.chdir('{0}'.format(zAnglePathName))
#모션 100Hz로 시간 변환
eventRawSetAng = eventRawSet / 10

angHipXSet = []
for zId in range(20):
    tempRaw = pd.read_table('SUB{0:02d}H_X.txt'.format(zId+1))
    tempRaw = tempRaw.values
    tempRaw = np.array(tempRaw[4:,3:], dtype=np.float64)
    
    resampled_data = []  # initialize empty list to hold resampled data
    for zTrial in range(10):
        start_index = np.round(eventRawSetAng[zId,zTrial]).astype(int)
        end_index = np.round(eventRawSetAng[zId,zTrial+1]).astype(int)
        tempTrial = tempRaw[start_index:end_index, 0]
    
        # Create a new array with 100 points, and interpolate tempTrial data to this new array
        x = np.linspace(0, len(tempTrial) - 1, 100)  # The x values where interpolation should be performed
        x_data = np.arange(len(tempTrial))  # The original x values
        tempTrial_resampled = np.interp(x, x_data, tempTrial)
    
        resampled_data.append(tempTrial_resampled)  # append resampled data to the list

    for zTrial in range(10):
        start_index = np.round(eventRawSetAng[zId,zTrial+11]).astype(int)
        end_index = np.round(eventRawSetAng[zId,zTrial+12]).astype(int)
        tempTrial = tempRaw[start_index:end_index, 1]
    
        # Create a new array with 100 points, and interpolate tempTrial data to this new array
        x = np.linspace(0, len(tempTrial) - 1, 100)  # The x values where interpolation should be performed
        x_data = np.arange(len(tempTrial))  # The original x values
        tempTrial_resampled = np.interp(x, x_data, tempTrial)
    
        resampled_data.append(tempTrial_resampled)  # append resampled data to the list
        
    # convert list to a 2D numpy array
    resampled_array = np.array(resampled_data)
    angHipXSet.append(resampled_array)

angHipXSet_np = np.array(angHipXSet)  # Convert to numpy array if not already
angHipXSet_mean = angHipXSet_np.mean(axis=(0, 1))  # Compute mean across first two dimensions
angHipXSet_sd = angHipXSet_np.std(axis=(0, 1))

        
angKneeXSet = []
for zId in range(20):
    tempRaw = pd.read_table('SUB{0:02d}K_X.txt'.format(zId+1))
    tempRaw = tempRaw.values
    tempRaw = np.array(tempRaw[4:,3:], dtype=np.float64)
    
    resampled_data = []  # initialize empty list to hold resampled data
    for zTrial in range(10):
        start_index = np.round(eventRawSetAng[zId,zTrial]).astype(int)
        end_index = np.round(eventRawSetAng[zId,zTrial+1]).astype(int)
        tempTrial = tempRaw[start_index:end_index, 0]
    
        # Create a new array with 100 points, and interpolate tempTrial data to this new array
        x = np.linspace(0, len(tempTrial) - 1, 100)  # The x values where interpolation should be performed
        x_data = np.arange(len(tempTrial))  # The original x values
        tempTrial_resampled = np.interp(x, x_data, tempTrial)
    
        resampled_data.append(tempTrial_resampled)  # append resampled data to the list

    for zTrial in range(10):
        start_index = np.round(eventRawSetAng[zId,zTrial+11]).astype(int)
        end_index = np.round(eventRawSetAng[zId,zTrial+12]).astype(int)
        tempTrial = tempRaw[start_index:end_index, 1]
    
        # Create a new array with 100 points, and interpolate tempTrial data to this new array
        x = np.linspace(0, len(tempTrial) - 1, 100)  # The x values where interpolation should be performed
        x_data = np.arange(len(tempTrial))  # The original x values
        tempTrial_resampled = np.interp(x, x_data, tempTrial)
    
        resampled_data.append(tempTrial_resampled)  # append resampled data to the list
        
    # convert list to a 2D numpy array
    resampled_array = np.array(resampled_data)
    angKneeXSet.append(resampled_array)

angKneeXSet_np = np.array(angKneeXSet)  # Convert to numpy array if not already
angKneeXSet_mean = angKneeXSet_np.mean(axis=(0, 1))  # Compute mean across first two dimensions
angKneeXSet_sd = angKneeXSet_np.std(axis=(0, 1))
    
angAnkleXSet = []
for zId in range(20):
    tempRaw = pd.read_table('SUB{0:02d}A_X.txt'.format(zId+1))
    tempRaw = tempRaw.values
    tempRaw = np.array(tempRaw[4:,3:], dtype=np.float64)
    
    resampled_data = []  # initialize empty list to hold resampled data
    for zTrial in range(10):
        start_index = np.round(eventRawSetAng[zId,zTrial]).astype(int)
        end_index = np.round(eventRawSetAng[zId,zTrial+1]).astype(int)
        tempTrial = tempRaw[start_index:end_index, 0]
    
        # Create a new array with 100 points, and interpolate tempTrial data to this new array
        x = np.linspace(0, len(tempTrial) - 1, 100)  # The x values where interpolation should be performed
        x_data = np.arange(len(tempTrial))  # The original x values
        tempTrial_resampled = np.interp(x, x_data, tempTrial)
    
        resampled_data.append(tempTrial_resampled)  # append resampled data to the list

    for zTrial in range(10):
        start_index = np.round(eventRawSetAng[zId,zTrial+11]).astype(int)
        end_index = np.round(eventRawSetAng[zId,zTrial+12]).astype(int)
        tempTrial = tempRaw[start_index:end_index, 1]
    
        # Create a new array with 100 points, and interpolate tempTrial data to this new array
        x = np.linspace(0, len(tempTrial) - 1, 100)  # The x values where interpolation should be performed
        x_data = np.arange(len(tempTrial))  # The original x values
        tempTrial_resampled = np.interp(x, x_data, tempTrial)
    
        resampled_data.append(tempTrial_resampled)  # append resampled data to the list
        
    # convert list to a 2D numpy array
    resampled_array = np.array(resampled_data)
    angAnkleXSet.append(resampled_array)

angAnkleXSet_np = np.array(angAnkleXSet)  # Convert to numpy array if not already
angAnkleXSet_mean = angAnkleXSet_np.mean(axis=(0, 1))  # Compute mean across first two dimensions
angAnkleXSet_sd = angAnkleXSet_np.std(axis=(0, 1))

angTrunkXSet = []
for zId in range(20):
    tempRaw = pd.read_table('SUB{0:02d}T_X.txt'.format(zId+1))
    tempRaw = tempRaw.values
    tempRaw = np.array(tempRaw[4:,3:], dtype=np.float64)
    
    resampled_data = []  # initialize empty list to hold resampled data
    for zTrial in range(10):
        start_index = np.round(eventRawSetAng[zId,zTrial]).astype(int)
        end_index = np.round(eventRawSetAng[zId,zTrial+1]).astype(int)
        tempTrial = tempRaw[start_index:end_index, 0]
    
        # Create a new array with 100 points, and interpolate tempTrial data to this new array
        x = np.linspace(0, len(tempTrial) - 1, 100)  # The x values where interpolation should be performed
        x_data = np.arange(len(tempTrial))  # The original x values
        tempTrial_resampled = np.interp(x, x_data, tempTrial)
    
        resampled_data.append(tempTrial_resampled)  # append resampled data to the list

    for zTrial in range(10):
        start_index = np.round(eventRawSetAng[zId,zTrial+11]).astype(int)
        end_index = np.round(eventRawSetAng[zId,zTrial+12]).astype(int)
        tempTrial = tempRaw[start_index:end_index, 1]
    
        # Create a new array with 100 points, and interpolate tempTrial data to this new array
        x = np.linspace(0, len(tempTrial) - 1, 100)  # The x values where interpolation should be performed
        x_data = np.arange(len(tempTrial))  # The original x values
        tempTrial_resampled = np.interp(x, x_data, tempTrial)
    
        resampled_data.append(tempTrial_resampled)  # append resampled data to the list
        
    # convert list to a 2D numpy array
    resampled_array = np.array(resampled_data)
    angTrunkXSet.append(resampled_array)

angTrunkXSet_np = np.array(angTrunkXSet)  # Convert to numpy array if not already
angTrunkXSet_mean = angTrunkXSet_np.mean(axis=(0, 1))  # Compute mean across first two dimensions
angTrunkXSet_sd = angTrunkXSet_np.std(axis=(0, 1))


#%%
# 이벤트 구간으로 잘라서 각 100프레임으로
######################## <<<<EMG>>>> ##########################
os.chdir('{0}'.format(zEMGPathName))
emgProceedSet = []
num_subjects = 20
for zId in range(num_subjects):
    emgProceedSet_zID = []

    for file_num in ['01', '02']:
        # Load data and apply highpass filter
        tempRaw = pd.read_csv('{0:02d}{1}.csv'.format(zId+1, file_num), skiprows=14, usecols=list(range(3,19)))
        tempRaw = tempRaw.values
        tempRaw = np.array(tempRaw, dtype=np.float64)

        # Generate 1000 zero frames
        zero_front = np.zeros((1000, tempRaw.shape[1]))
        zero_back = np.zeros((1000, tempRaw.shape[1]))
        
        # Add 1000 random frames at the front and back
        tempRaw = np.concatenate([zero_front, tempRaw, zero_back])

        emgHiFilt=np.zeros(tempRaw.shape)
        for i in range(16):
            emgHiFilt[:,i] = butter_highpass_filter(tempRaw[:,i], 35, 1000, 3)
        
        # Apply demean
        emgDemean = emgHiFilt - emgHiFilt.mean(axis=0)
        
        # Apply rectification
        emgRec = abs(emgDemean)
        
        # Apply lowpass filter
        emgLoFilt=np.zeros(emgRec.shape)
        for i in range(16):
            emgLoFilt[:,i] = butter_lowpass_filter(emgRec[:,i], 5, 1000, 3)
        
        # Remove 1000 frames from the front and back
        emgLoFilt = emgLoFilt[1000:-1000]

        # Apply the start and end indices to cut data
        for zTrial in range(10):
            if file_num == '01':
                start_index = np.round(eventRawSet[zId,zTrial]).astype(int)
                end_index = np.round(eventRawSet[zId,zTrial+1]).astype(int)
            else:
                start_index = np.round(eventRawSet[zId,zTrial+11]).astype(int)
                end_index = np.round(eventRawSet[zId,zTrial+12]).astype(int)
            
            # 100 Resample data
            tempTrial = emgLoFilt[start_index:end_index, :]
            resampled_data = np.zeros((100, tempTrial.shape[1]))
            for i in range(tempTrial.shape[1]):
                x = np.linspace(0, len(tempTrial[:, i]) - 1, 100)
                x_data = np.arange(len(tempTrial[:, i]))
                resampled_data[:, i] = np.interp(x, x_data, tempTrial[:, i])
            
            # Normalize the resampled data
            resampled_data = np.where(resampled_data<0, 0, resampled_data)
            tmpMin = resampled_data.min(axis = 0)
            tmpMinNorm = resampled_data - tmpMin
            tmpMax = tmpMinNorm.max(axis = 0)
            resampled_data = tmpMinNorm / tmpMax
            
            emgProceedSet_zID.append(resampled_data)

    emgProceedSet.append(emgProceedSet_zID)
#%% 사용
#6, 9번 대상자 삭제 - 시너지 수가 5개 6개
#1, 10번 대상자 삭제 - 클러스터링 결과(6개)에서 시기가 비슷한 5-6번째 클러스터 모두 할당되여 해석 이상함.
# 파이썬 인덱싱은 0부터 시작하므로 9번째 요소의 인덱스는 8이 됩니다.
indices_to_delete = [0, 5, 8, 9]
for index in sorted(indices_to_delete, reverse=True):
    del emgProceedSet[index]

#%% emg 점검 ICC 분석
num_subjects = 20
num_trials = 20
num_frames = 100
num_channels = 16


emgProceedSet_icc = [[[[] for _ in range(num_trials)] for _ in range(num_channels)] for _ in range(num_subjects)]

for subject in range(num_subjects):
    for trial in range(num_trials):
        for channel in range(num_channels):
            # 해당 trial의 특정 채널 데이터 추출
            channel_data = [emgProceedSet[subject][trial][frame][channel] for frame in range(num_frames)]
            emgProceedSet_icc[subject][channel][trial] = channel_data

import rpy2.robjects as ro
from rpy2.robjects.conversion import localconverter
from rpy2.robjects import pandas2ri
pandas2ri.activate()
from rpy2.robjects.packages import importr
ICC = importr("irr")

icc_results=[]
for subject in range(num_subjects):
    clStrIcc=[]
    for channel in range(num_channels):
        tmp = np.vstack(emgProceedSet_icc[subject][channel])
        tmpVals = pd.DataFrame(tmp)
        with localconverter(ro.default_converter + pandas2ri.converter):
            tmpVals1 = ro.conversion.py2rpy(tmpVals.T)
    
        tmpIcc = ICC.icc(tmpVals1, model="twoway", type="consistency", unit = "single", r0 = 0)
        clStrIcc.extend(tmpIcc[6])
    icc_results.append(clStrIcc)
iccEmg = np.vstack(icc_results)
#%% 테스트
import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# 폴더 생성
if not os.path.exists('plots'):
    os.makedirs('plots')

zMuscleName = ['GM', 'Gm', 'AD', 'RF', 'VL', 'VM', 'BF', 'ST', 'MG', 'LG', 'TA', 'PL', 'SO', 'ES', 'MF', 'IO']

# 전체 그림의 크기 설정 (가로 크기를 조절)
fig, axs = plt.subplots(len(zMuscleName), len(emgProceedSet), figsize=(3*len(emgProceedSet), 15))

# 각 열 위에 subject ID 추가
for i, ax in enumerate(axs[0, :]):
    ax.set_title(f"Subject {i+1}")

# 개인별 데이터 그리기
for zId in range(len(emgProceedSet)):
    for i, ax in enumerate(axs[:, zId]):
        
        # plot all the trials data with increased transparency
        for trial in emgProceedSet[zId]:
            ax.plot(trial[:, i], alpha=0.1, color='blue')
        
        # plot the mean of all trials with no transparency
        mean_trial = np.mean([t[:, i] for t in emgProceedSet[zId]], axis=0)
        ax.plot(mean_trial, label='Mean', color='red')
        
        # y축 범위 설정
        ax.set_ylim([0,1])
        
        # x축 범위 설정
        ax.set_xlim([0,100])

        # ICC 값을 subplot에 추가
        ax.annotate(f"{zMuscleName[i]} ICC: {iccEmg[zId, i]:.2f}", xy=(0.1, 0.9), xycoords="axes fraction")
        
        # 눈금과 라벨 제거
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xticklabels([])
        ax.set_yticklabels([])

        # 위쪽과 오른쪽의 선 제거
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)

# 레이아웃 조절
plt.tight_layout()
plt.subplots_adjust(top=0.95, hspace=0.4, wspace=0.3)

# Save the plot as a png file
plt.savefig(zSavePathName + "/EMG_overview.png")  # 여기서 "saved_figure.png"는 원하는 파일 이름을 의미합니다.
plt.close(fig)  # Close the plot to free up memory



#%% 그래프: 개인별 근전도 
import os
import numpy as np
import matplotlib.pyplot as plt

# 폴더 생성
if not os.path.exists('plots'):
    os.makedirs('plots')

# zMuscleName = ['GM', 'RF', 'VL', 'VM', 'BF', 'MG', 'TA', 'PL', 'SO', 'ES']
zMuscleName = ['GM', 'Gm', 'AD', 'RF', 'VL', 'VM', 'BF', 'ST', 'MG', 'LG', 'TA', 'PL', 'SO', 'ES', 'MF', 'IO']


# 전체 그림의 크기 설정 (가로 크기를 조절)
fig, axs = plt.subplots(len(zMuscleName), len(emgProceedSet), figsize=(3*len(emgProceedSet), 15))  # 10개의 근육 데이터, 개인별로 그래프 생성

# 개인별 데이터 그리기
for zId in range(len(emgProceedSet)):
    for i, ax in enumerate(axs[:, zId]):  # 세로 방향으로 근육 데이터 시각화
        # 각 근육에 해당하는 이름으로 첫 번째 열의 서브플롯에만 타이틀 설정
        if zId == 0:
            ax.set_title(zMuscleName[i])
        
        # plot all the trials data with increased transparency
        for trial in emgProceedSet[zId]:
            ax.plot(trial[:, i], alpha=0.1, color='blue')
        
        # plot the mean of all trials with no transparency
        mean_trial = np.mean([t[:, i] for t in emgProceedSet[zId]], axis=0)
        ax.plot(mean_trial, label='Mean', color='red')
        
        ax.set_ylim([0,1])  # Setting y-axis limits

        # Only the last row will have x-axis labels
        if i < len(zMuscleName) - 1:
            ax.set_xticks([])

# 레이아웃 조절
plt.tight_layout()
plt.subplots_adjust(top=0.95, hspace=0.4, wspace=0.3)  # wspace 인자로 서브플롯 간의 가로 간격 조절

# Save the plot as a png file
plt.savefig('plots/EMG_Overview.png')
plt.close(fig)  # Close the plot to free up memory


#%% EMG ICC 평균 그래프
mean_icc = np.mean(iccEmg, axis=0)
std_icc = np.std(iccEmg, axis=0)

zMuscleName = ['GM', 'Gm', 'AD', 'RF', 'VL', 'VM', 'BF', 'ST', 'MG', 'LG', 'TA', 'PL', 'SO', 'ES', 'MF', 'IO']
x_values = range(1, len(zMuscleName) + 1)

# Combine muscle names and numbers
labels = [f"{name}({num})" for name, num in zip(zMuscleName, x_values)]

plt.figure(figsize=(12, 6))

# Plotting the bar graph
plt.bar(x_values, mean_icc[:len(zMuscleName)], yerr=std_icc[:len(zMuscleName)], color='skyblue', capsize=7, label='ICC Mean & STD')

plt.xlabel('Muscles')
plt.ylabel('ICC Value')
plt.title('Mean & STD of ICC by Muscle')

# Set x-axis ticks and labels
plt.xticks(x_values, labels=labels)

plt.legend()
plt.grid(axis='y')

plt.tight_layout()
plt.show()
#%% 낮은 신뢰도 채널 삭제
# emgProceedSet에서 2, 3, 8, 10, 15, 16 번째 채널 데이터를 삭제
# 인덱스는 1, 2, 7, 9, 14, 15
channels_to_remove = [1, 2, 7, 9, 14, 15]

# For each subject and trial, remove the undesired channels
for subject in emgProceedSet:
    for trial_idx in range(len(subject)):
        subject[trial_idx] = np.delete(subject[trial_idx], channels_to_remove, axis=1)  # Assuming 2D matrix for each trial
#%% EMG 데이터 그래프 저장
import os
import numpy as np
import matplotlib.pyplot as plt

# 폴더 생성
if not os.path.exists('plots'):
    os.makedirs('plots')

zMuscleName = ['GM', 'RF', 'VL', 'VM', 'BF', 'MG', 'TA', 'PL', 'SO', 'ES']
zMuscleName = ['GM', 'Gm', 'AD', 'RF', 'VL', 'VM', 'BF', 'ST', 'MG', 'LG', 'TA', 'PL', 'SO', 'ES', 'MF', 'IO']

for zId in range(len(emgProceedSet)):
    fig, axs = plt.subplots(2, 5, figsize=(15, 5))  # 2x5 subplot layout로 변경
    fig.suptitle('EMG Data for Individual {}'.format(zId+1))

    for i, ax in enumerate(axs.flatten()):
        # 각 근육에 해당하는 이름으로 서브플롯 타이틀 설정
        ax.set_title(zMuscleName[i])
        
        # plot all the trials data with increased transparency
        for trial in emgProceedSet[zId]:
            ax.plot(trial[:, i], alpha=0.1, color='blue')
        
        # plot the mean of all trials with no transparency
        mean_trial = np.mean([t[:, i] for t in emgProceedSet[zId]], axis=0)
        ax.plot(mean_trial, label='Mean', color='red')
        
        ax.legend()
        ax.set_ylim([0,1]) # Setting y-axis limits

    plt.tight_layout()
    plt.subplots_adjust(top=0.9)  # 조금 더 위쪽으로 조절하여 서브플롯 타이틀과 충돌을 피합니다.
    
    # Save the plot as a png file
    plt.savefig('plots/Individual_{}.png'.format(zId+1))

    plt.close(fig)  # Close the plot to free up memory


#%% emg 데이터 그림 파일 한개씩 보기
for zId in range(len(emgProceedSet)):
    for trial_idx, trial in enumerate(emgProceedSet[zId]):
        fig, axs = plt.subplots(4, 4, figsize=(15, 10))
        fig.suptitle('EMG Data for Individual {} Trial {}'.format(zId+1, trial_idx+1))

        for i, ax in enumerate(axs.flatten()):
            # plot all the trials data with increased transparency
            for t in emgProceedSet[zId]:
                ax.plot(t[:, i], alpha=0.1)

            # plot the current trial data with no transparency
            ax.plot(trial[:, i], label='Trial {}'.format(trial_idx+1), color='red')

            ax.legend()

        plt.tight_layout()
        plt.subplots_adjust(top=0.95)
        plt.show()

        input("Press enter to continue to the next trial...")

#%% EMG 데이터 개별 그래프 저장
import os
import matplotlib.pyplot as plt
# Create a directory for the plots if it doesn't exist
if not os.path.exists('plots'):
    os.makedirs('plots')

for zId in range(len(emgProceedSet)):
    for trial_idx, trial in enumerate(emgProceedSet[zId]):
        fig, axs = plt.subplots(4, 4, figsize=(15, 10))
        fig.suptitle('EMG Data for Individual {} Trial {}'.format(zId+1, trial_idx+1))

        for i, ax in enumerate(axs.flatten()):
            # plot all the trials data with increased transparency
            for t in emgProceedSet[zId]:
                ax.plot(t[:, i], alpha=0.1, color='blue')

            # plot the current trial data with no transparency
            ax.plot(trial[:, i], label='Trial {}'.format(trial_idx+1), color='red')

            ax.legend()
            ax.set_ylim([0,1]) # Setting y-axis limits

        plt.tight_layout()
        plt.subplots_adjust(top=0.95)
        
        # Save the plot as a png file
        plt.savefig('plots/Individual_{}_Trial_{}.png'.format(zId+1, trial_idx+1))

        plt.close(fig)  # Close the plot to free up memory


#%% 근육 시너지 추출하기
# 각 대상자와 각 시도에 대한 synergy activation 값과 synergy structure 값을 저장할 빈 리스트 생성
synergy_activations = []
synergy_structures = []
nmf_vafs = []  # 각 시도의 VAF 값을 저장할 빈 리스트 생성
nmf_nums = []  # 90% VAF를 넘기는 최소의 벡터 수를 저장할 빈 리스트 생성

# emgProceedSet의 각 대상자에 대하여
for zID in range(len(emgProceedSet)):
    synergy_activations_individual = []
    synergy_structures_individual = []
    nmf_vafs_individual = []
    nmf_nums_individual = []
    
    # 각 대상자의 각 시도에 대하여
    for zTrial in range(len(emgProceedSet[zID])):
        nmf_vafs_trial = []  # 현재 trial의 VAF 값을 저장할 리스트
        activation_trial = []
        structure_trial = []
        vaf_reached_90 = False
        
        iMode = 0  # 벡터 수 초기화
        while iMode < emgProceedSet[0][0].shape[1]:  # 벡터 수가 16개일 때까지 반복
            iMode += 1  # 벡터 수 증가
            nmf = NMF(n_components=iMode, init='random', random_state=0)  # NMF 모델 초기화
            W = nmf.fit_transform(emgProceedSet[zID][zTrial])  # synergy activations
            H = nmf.components_  # synergy structures

            # VAF 계산
            recon = nmf.inverse_transform(W)  # 데이터 재구성
            vaf = 1 - np.sum((emgProceedSet[zID][zTrial] - recon) ** 2) / np.sum(emgProceedSet[zID][zTrial] ** 2)
            nmf_vafs_trial.append(vaf)  # 해당 벡터 수에서의 VAF 값 저장

            if vaf > 0.9 and not vaf_reached_90:  # VAF가 90%를 넘었을 때
                vaf_reached_90 = True
                nmf_nums_individual.append(iMode)  # 현재 벡터 수 저장
                activation_trial = W
                structure_trial = H

        nmf_vafs_individual.append(nmf_vafs_trial)
        if vaf_reached_90:
            synergy_activations_individual.append(activation_trial)
            synergy_structures_individual.append(structure_trial)

    synergy_activations.append(synergy_activations_individual)
    synergy_structures.append(synergy_structures_individual)
    nmf_vafs.append(nmf_vafs_individual)
    nmf_nums.append(nmf_nums_individual)
#%%
##<clustering>
from sklearn.cluster import KMeans
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis
import find_multiple_value as fmv

# ###학교###
# os.environ['R_HOME'] = 'C://Program Files//R//R-4.1.2'
# os.environ['R_USER']= 'C://Users//Cju//anaconda3//Lib//site-packages//rpy2'

#####집######
os.environ['R_HOME'] = 'C:\\Program Files\\R\\R-4.1.2'
os.environ['R_USER']= 'C:\\Anaconda3\\Lib\\site-packages\\rpy2'

from rpy2.robjects.packages import importr
ICC = importr("irr")
boxMtest = importr("MVTests")
discriminant = importr("MASS")
statsR = importr("stats")
lawstat = importr("lawstat")
#bartlett = importr("bartlett")
from rpy2.robjects import pandas2ri
pandas2ri.activate()

nmfStrSet = [structure.flatten() for sublist in synergy_structures for item in sublist for structure in item]
nmfStrSet1 = np.vstack(nmfStrSet)
nmfNumSet = [value for sublist in nmf_nums for value in sublist]
nmfNumSet1 = np.vstack(nmf_nums)
nmfNumSet2 = np.cumsum(nmfNumSet)

clusterNumSet = []
clusterClIdSet = []
clusterNum = []
clId = []
subList = list(range(10))
for k in range(10):
    for i in range(3, 100): #set maximum number of cluster
        print('{}번 반복 중 {}개 클러스터'.format(k, i))  
        clusterId = KMeans(n_clusters=i+1).fit(nmfStrSet1)
        clId = clusterId.labels_
        error = 0
        ##################### 판별분석 ##########################        
        try:
            tmp = boxMtest.BoxM(nmfStrSet1, clId) #Box의 M 등분산 검정
            print(tmp[2])
            if np.asarray(tmp[2]) >= 0.05:
                ldaModel = LinearDiscriminantAnalysis().fit(nmfStrSet1, clId)
                clId = ldaModel.predict(nmfStrSet1)
                print('LDA')
            elif np.asarray(tmp[2]) < 0.05:
                qdaModel = QuadraticDiscriminantAnalysis().fit(nmfStrSet1, clId)
                clId = qdaModel.predict(nmfStrSet1)
                print('QDA')
        except:
            error = 1
            print('error')
        ############################################################
        if error == 0:
            clIdInd = []
            for j in range(len(nmfNumSet)):
                tmpPoint1 = sum(nmfNumSet[:j+1])-nmfNumSet[j]
                tmpPoint2 = sum(nmfNumSet[:j+1])
                tmpPoint3 = clId[tmpPoint1:tmpPoint2]
                tmpPoint4 = fmv.find_multiple_value(tmpPoint3) # np.unique 사용 고려...                
                if tmpPoint4 != []: #클러스터에 중복이 발생하면 멈춤
                    for n in range(len(subList)):
                        if j < nmfNumSet2[n]:
                            print(subList[n])
                            break
                        
                    print('    {}째가 문제-->{}'.format(j, tmpPoint3))
                    break
                else:
                    clIdInd.append(tmpPoint3)
            if tmpPoint4 == []:
                clusterNum = i
                print('                중복 안된 클러스터 수: {}'.format(i))
                clusterNumSet.append(clusterNum)
                clusterClIdSet.append(clId)
                with open('{}ClustDisc.p'.format(zSavePathName), 'wb') as file:
                    pickle.dump(clusterNumSet, file)
                    pickle.dump(clusterClIdSet, file)
                break
            


# #%%
# # 1. k 값을 점차 늘려가며 클러스터링을 반복한다.
# # 2. k 시작 값은 전체 대상자 중 최소 벡터 숫자로 정한다.
# # 3. 만일 한 대상자 내 한 trial에 포함된 시너지 구조가 동일 클러스터에 포함될 경우 k값을 올려 클러스터링을 다시 한다.
# # 4. 각 참가자 내 각 trial의 시너지 구조가 모두 다른 클러스터에 포함된 것을 확인하면 해당 k 값에서 클러스터링 결과를 정리한다.

# from sklearn.cluster import KMeans
# from collections import defaultdict

# # 시작점으로, 가장 작은 벡터 개수를 선택합니다.
# k = min([len(item) for sublist in synergy_structures for item in sublist])

# # 모든 참가자와 모든 시도에 대한 시너지 구조 정보를 하나의 리스트로 합치기
# structures_list = [structure.flatten() for sublist in synergy_structures for item in sublist for structure in item]

# max_k = len(structures_list)

# clusters = []
# cluster_dict = defaultdict(list)
# while k <= max_k:
#     kmeans = KMeans(n_clusters=k)
#     labels = kmeans.fit_predict(structures_list)
    
#     # 각 참가자별 시도별로 시너지 구조들이 속한 클러스터 확인
#     for idx, sublist in enumerate(synergy_structures):
#         for jdx, trial in enumerate(sublist):
#             trial_labels = labels[idx*len(sublist)+jdx : idx*len(sublist)+jdx+len(trial)]
            
#             # 만일 한 참가자의 한 시도 내 시너지 구조들이 동일한 클러스터에 속하면, 클러스터링이 유효하지 않음
#             if len(set(trial_labels)) != len(trial_labels):
#                 break
#         else:
#             continue
#         break
#     else:
#         # 모든 참가자의 모든 시도에 대해 시너지 구조들이 다른 클러스터에 속함을 확인하면, 클러스터링 결과를 저장하고 반복 종료
#         clusters = labels
#         break
    
#     # 클러스터링이 유효하지 않으면 k 값을 증가시키고 다시 시도
#     k += 1

# # 각 시너지 구조에 대한 클러스터 번호를 저장
# synergy_clusters = clusters



#%% 2000 프레임으로 emg 데이터셋 만들기
os.chdir('{0}'.format(zEMGPathName))
emgProceedSet = []

for zId in range(20):

    for file_num in ['01', '02']:
        # Load data and apply highpass filter
        tempRaw = pd.read_csv('{0:02d}{1}.csv'.format(zId+1, file_num), skiprows=14, usecols=list(range(3,19)))
        tempRaw = tempRaw.values
        tempRaw = np.array(tempRaw, dtype=np.float64)
        
        # Generate 1000 zero frames
        zero_front = np.zeros((1000, tempRaw.shape[1]))
        zero_back = np.zeros((1000, tempRaw.shape[1]))
        
        # Add 1000 random frames at the front and back
        tempRaw = np.concatenate([zero_front, tempRaw, zero_back])
        
        emgHiFilt=np.zeros(tempRaw.shape)
        for i in range(16):
            emgHiFilt[:,i] = butter_highpass_filter(tempRaw[:,i], 35, 1000, 3)
        
        # Apply demean
        emgDemean = emgHiFilt - emgHiFilt.mean(axis=0)
        
        # Apply rectification
        emgRec = abs(emgDemean)
        
        # Apply lowpass filter
        emgLoFilt=np.zeros(emgRec.shape)
        for i in range(16):
            emgLoFilt[:,i] = butter_lowpass_filter(emgRec[:,i], 3, 1000, 3)
        
        # Remove 1000 frames from the front and back
        emgLoFilt = emgLoFilt[1001:-1001]

        # Normalize
        emgLoFilt = np.where(emgLoFilt<0, 0, emgLoFilt)
        tmpMin = emgLoFilt.min(axis = 0)
        tmpMinNorm = emgLoFilt - tmpMin
        tmpMax = tmpMinNorm.max(axis = 0)
        tmpMaxNorm = tmpMinNorm / tmpMax

        # Concatenate data from '01' and '02' files
        if file_num == '01':
            concatenated_data = tmpMaxNorm
        else:
            concatenated_data = np.concatenate((concatenated_data, tmpMaxNorm), axis=0)

    # 2000 Resample data
    resampled_data = np.zeros((2000, concatenated_data.shape[1]))
    for i in range(concatenated_data.shape[1]):
        x = np.linspace(0, len(concatenated_data[:, i]) - 1, 2000)
        x_data = np.arange(len(concatenated_data[:, i]))
        resampled_data[:, i] = np.interp(x, x_data, concatenated_data[:, i])

    emgProceedSet.append(resampled_data)
#%% 사용
#6, 9번 대상자 삭제 - 시너지 수가 5개 6개
#1, 10번 대상자 삭제 - 클러스터링 결과(6개)에서 시기가 비슷한 5-6번째 클러스터 모두 할당되여 해석 이상함.
# 파이썬 인덱싱은 0부터 시작하므로 9번째 요소의 인덱스는 8이 됩니다.
indices_to_delete = [0, 5, 8, 9]
for index in sorted(indices_to_delete, reverse=True):
    del emgProceedSet[index]
    del eventPhaseSet[index]
    del angTrunkXSet[index]
    del angHipXSet[index]
    del angKneeXSet[index]
    del angAnkleXSet[index]
    
#%% 미사용
#1 2 3 4 7 9 10 11 12 15번 대상자 삭제
# 파이썬 인덱싱은 0부터 시작하므로 9번째 요소의 인덱스는 8이 됩니다.
indices_to_delete = [0, 1, 2, 3, 6, 8, 9, 10, 11, 14]
for index in sorted(indices_to_delete, reverse=True):
    del emgProceedSet[index]    
#%% 미사용 - 낮은 신뢰도 채널 삭제
# emgProceedSet에서 2, 3, 8, 10, 15, 16 번째 채널 데이터를 삭제
# 인덱스는 1, 2, 7, 9, 14, 15
# 삭제하고자 하는 채널 인덱스
channels_to_remove = [1, 2, 7, 9, 14, 15]

# 대상자별로 데이터에서 해당 채널 제거
for i in range(len(emgProceedSet)):
    emgProceedSet[i] = np.delete(emgProceedSet[i], channels_to_remove, axis=1)

#%% 2000 프레임 데이터셋에서 시너지 추출하기
from sklearn.decomposition import NMF

# 각 대상자에 대한 weight vector 값과 coefficient 값을 저장할 빈 리스트 생성
synergy_activations = []
synergy_structures = []
nmf_vafs = []  # 각 대상자의 VAF 값을 저장할 빈 리스트 생성
nmf_nums = []  # 90% VAF를 넘기는 최소의 벡터 수를 저장할 빈 리스트 생성

# emgProceedSet의 각 대상자에 대하여
for zID in range(len(emgProceedSet)):
    nmf_vafs_individual = []  # 현재 대상자의 VAF 값을 저장할 리스트
    activations_individual = []
    structures_individual = []
    vaf_reached_90 = False

    iMode = 0  # 벡터 수 초기화
    while iMode < emgProceedSet[0].shape[1]:  # 벡터 수가 16개일 때까지 반복
        iMode += 1  # 벡터 수 증가
        nmf = NMF(n_components=iMode, init='random', random_state=0)  # NMF 모델 초기화
        W = nmf.fit_transform(emgProceedSet[zID])  # weight vectors
        H = nmf.components_  # coefficients

        # VAF 계산
        recon = nmf.inverse_transform(W)  # 데이터 재구성
        vaf = 1 - np.sum((emgProceedSet[zID] - recon) ** 2) / np.sum(emgProceedSet[zID] ** 2)
        nmf_vafs_individual.append(vaf)  # 해당 벡터 수에서의 VAF 값 저장

        if vaf > 0.9 and not vaf_reached_90:  # VAF가 90%를 넘었을 때
            vaf_reached_90 = True
            nmf_nums.append(iMode)  # 현재 벡터 수 저장
            activations_individual = W
            structures_individual = H

    nmf_vafs.append(nmf_vafs_individual)
    if vaf_reached_90:
        synergy_activations.append(activations_individual)
        synergy_structures.append(structures_individual)

#%%
import matplotlib.pyplot as plt
import numpy as np
# emgProceedSet에서 2, 3, 8, 10, 15, 16 번째 채널 데이터를 삭제
zMuscleName={'GM' 'VL' 'VM' 'BF' 'MG' 'TA' 'PL' 'SL' 'ES'}
# 모든 채널
zMuscleName = ['GM', 'Gm', 'AD', 'RF', 'VL', 'VM', 'BF', 'ST', 'MG', 'LG', 'TA', 'PL', 'SO', 'ES', 'MF', 'IO']

n_subjects = len(synergy_structures) # number of subjects
n_muscles = synergy_structures[0].shape[1] # number of muscles

# get maximum number of synergies across all subjects
n_synergies_max = max([structures.shape[0] for structures in synergy_structures])

# Create figure with enough subplots
fig, axes = plt.subplots(n_synergies_max, n_subjects, figsize=(5*n_subjects, 5*n_synergies_max))

for i in range(n_synergies_max):
    for j in range(n_subjects):
        if i < synergy_structures[j].shape[0]:  # if the current subject has this many synergies
            ax = axes[i][j] if n_subjects > 1 else axes[i]
            ax.bar(range(n_muscles), synergy_structures[j][i, :])
            
            # Remove grid from subplot
            ax.grid(False)
            
            # Set title for the first row subplots only
            if i == 0:
                ax.set_title(f"Subject {j+1}", fontsize=60)
            
            ax.set_xticks([])  # This line removes the xticks
            ax.set_yticks([])  # This line removes the yticks
        else:  # if the current subject doesn't have this many synergies, hide the axes
            axes[i][j].axis('off')

# Improve layout
plt.tight_layout()
# Save the figure to the specified path
plt.savefig(zSavePathName + "/synergy_overview.png", dpi=300)  # 여기서 "saved_figure.png"는 원하는 파일 이름을 의미합니다.

plt.show()
   
        
#%% 클러스터링 하기
##<clustering>
from sklearn.cluster import KMeans
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis
import find_multiple_value as fmv

# ###학교###
# os.environ['R_HOME'] = 'C://Program Files//R//R-4.1.2'
# os.environ['R_USER']= 'C://Users//Cju//anaconda3//Lib//site-packages//rpy2'

#####집######
os.environ['R_HOME'] = 'C:\\Program Files\\R\\R-4.1.2'
os.environ['R_USER']= 'C:\\Anaconda3\\Lib\\site-packages\\rpy2'

from rpy2.robjects.packages import importr
ICC = importr("irr")
boxMtest = importr("MVTests")
discriminant = importr("MASS")
statsR = importr("stats")
lawstat = importr("lawstat")
#bartlett = importr("bartlett")
from rpy2.robjects import pandas2ri
pandas2ri.activate()

nmfStrSet1 = np.vstack(synergy_structures)
nmfActSet = np.hstack(synergy_activations)
nmfActSet1 = nmfActSet.T
nmfNumSet = np.hstack(nmf_nums)
nmfNumSet1 = np.vstack(nmf_nums)
nmfNumSet2 = np.cumsum(nmfNumSet)

clusterNumSet = []
clusterClIdSet = []
clusterNum = []
clId = []
for k in range(100):
    for i in range(3, 25): #set maximum number of cluster
        print('{}번 반복 중 {}개 클러스터'.format(k, i))  
        clusterId = KMeans(n_clusters=i+1).fit(nmfStrSet1)
        clId = clusterId.labels_
        error = 0
        ##################### 판별분석 ##########################        
        try:
            tmp = boxMtest.BoxM(nmfStrSet1, clId) #Box의 M 등분산 검정
            print(tmp[2])
            if np.asarray(tmp[2]) >= 0.05:
                ldaModel = LinearDiscriminantAnalysis().fit(nmfStrSet1, clId)
                clId = ldaModel.predict(nmfStrSet1)
                print('LDA')
            elif np.asarray(tmp[2]) < 0.05:
                qdaModel = QuadraticDiscriminantAnalysis().fit(nmfStrSet1, clId)
                clId = qdaModel.predict(nmfStrSet1)
                print('QDA')
        except:
            error = 1
            print('error')
        ############################################################
        if error == 0:
            clIdInd = []
            for j in range(len(nmfNumSet)):
                tmpPoint1 = sum(nmfNumSet[:j+1])-nmfNumSet[j]
                tmpPoint2 = sum(nmfNumSet[:j+1])
                tmpPoint3 = clId[tmpPoint1:tmpPoint2]
                tmpPoint4 = fmv.find_multiple_value(tmpPoint3) # np.unique 사용 고려...                
                if tmpPoint4 != []: #클러스터에 중복이 발생하면 멈춤
                    print('    {}째가 문제-->{}'.format(j, tmpPoint3))
                    break
                else:
                    clIdInd.append(tmpPoint3)
            if tmpPoint4 == []:
                clusterNum = i
                print('                중복 안된 클러스터 수: {}'.format(i))
                clusterNumSet.append(clusterNum)
                clusterClIdSet.append(clId)
                
                with open('{}SquetClustDisc.p'.format(zSavePathName), 'wb') as file:
                    pickle.dump(clusterNumSet, file)
                    pickle.dump(clusterClIdSet, file)
                break


#%%
################################################################################
# 0누락된 것 보정
import mode
tmp = []
for i in range(len(clusterClIdSet)):
    tmp.append(np.array(clusterClIdSet[i],dtype=np.int64) - np.min(np.array(clusterClIdSet[i],dtype=np.int64)))
clusterClIdSet = tmp
tmp = []
for i in range(len(clusterClIdSet)):
    tmp.append(np.max(clusterClIdSet[i]))
clusterNumSet = tmp
#############최다 클러스터 선택
clusterNumFreq = mode.mode(clusterNumSet) #0부터 시작 주의

clustIdSet = []
for i in range(len(clusterNumSet)):
    if clusterNumSet[i] == clusterNumFreq:
        clustIdSet.append(clusterClIdSet[i])
############ICC 분석
import rpy2.robjects as ro
from rpy2.robjects.conversion import localconverter
clStrIccSet = []
for i in range(len(clustIdSet)):
    clId = clustIdSet[i]
    tmpStr = []
    clStr = []
    clStrIcc = []
    for j in range(clusterNumFreq+1):
        tmpStr = nmfStrSet1[np.where(clId == j)]
        clStr.append(tmpStr)
        
        tmpVals = pd.DataFrame(tmpStr)
        # tmpVals1 = pandas2ri.py2ri(tmpVals.T)
        with localconverter(ro.default_converter + pandas2ri.converter):
            tmpVals1 = ro.conversion.py2rpy(tmpVals.T)
        
        tmp = ICC.icc(tmpVals1, model="twoway", type="consistency", unit = "single", r0 = 0)
        clStrIcc.extend(tmp[6])
    clStrIccSet.append(clStrIcc)
tmp = np.mean(clStrIccSet, axis = 1)
#tmp0 = np.min(clStrIccSet, axis = 1)
tmp1 = np.argmax(tmp)
clId = clustIdSet[tmp1]
clStrIcc = clStrIccSet[tmp1]

tmpStr=[]
nmfStrClust = []
tmpAct = []
nmfActClust = []
for j in range(clusterNumFreq+1):
    tmpStr = nmfStrSet1[np.where(clId == j)]
    nmfStrClust.append(tmpStr)
    tmpAct = nmfActSet1[np.where(clId == j)]
    nmfActClust.append(tmpAct)  
    
import numpy as np
import matplotlib.pyplot as plt

# 시너지 구조의 평균과 표준오차 계산
nmfStrClust_means = [np.mean(cluster, axis=0) for cluster in nmfStrClust]
nmfStrClust_errors = [np.std(cluster, axis=0)/np.sqrt(cluster.shape[0]) for cluster in nmfStrClust]

# 시너지 활성의 평균과 표준오차 계산
# 먼저 2000 프레임을 20 trials의 100개 프레임으로 분할
nmfActClust_reshaped = [cluster.reshape(-1, 20, 100) for cluster in nmfActClust]
# 전체 평균 및 표준오차 계산
nmfActClust_mean_overall = [np.mean(reshaped_cluster, axis=(0, 1)) for reshaped_cluster in nmfActClust_reshaped]
nmfActClust_error_overall = [np.std(reshaped_cluster, axis=(0, 1))/np.sqrt(reshaped_cluster.shape[1]*reshaped_cluster.shape[0]) for reshaped_cluster in nmfActClust_reshaped]

# 시너지 활성의 피크 위치에 따라 클러스터 순서를 정렬
peak_positions = [np.argmax(mean) for mean in nmfActClust_mean_overall]
sorted_indices = np.argsort(peak_positions)

# 활성 순서 기준 클러스터 ICC값
clStrIcc_sorted = [clStrIcc[i] for i in sorted_indices]

# 대상자 클러스터 할당 상태
clIdInd = [] #대상자 별 클러스터 ID
for i in range(len(nmfNumSet1)):
    tmpPoint1 = sum(nmfNumSet1[:i+1])-nmfNumSet1[i]
    tmpPoint2 = sum(nmfNumSet1[:i+1])
    tmpPoint3 = clId[tmpPoint1[0]:tmpPoint2[0]]
    clIdInd.append(tmpPoint3)

#클러스터 활성 피크 위치에 따른 ID 변경
clIdInd_sorted = []
for cluster_ids in clIdInd:
    clIdInd_sorted.append([np.where(sorted_indices == id)[0][0] for id in cluster_ids])
#%%
# 클러스터의 총 수 계산
max_cluster_id = max([max(lst) if lst else 0 for lst in clIdInd_sorted])

# 대상자 수 x 클러스터 수 행렬 초기화 (0으로)
data_matrix = np.zeros((len(clIdInd_sorted), max_cluster_id + 1))

# 각 대상자의 클러스터 할당에 따라 해당 위치의 값을 1로 설정
for i, clusters in enumerate(clIdInd_sorted):
    for cluster in clusters:
        data_matrix[i][cluster] = 1

# 데이터프레임으로 변환 (인덱스와 컬럼 이름을 1부터 시작하도록 조정)
df = pd.DataFrame(data_matrix, dtype=int, index=range(1, len(clIdInd_sorted) + 1), columns=range(1, max_cluster_id + 2))

import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.patches as patches

plt.figure(figsize=(3, 8))
sns.set(font_scale=1.2)
ax = sns.heatmap(df, cmap='Blues', cbar=False, linewidths=0.5, linecolor='gray')

# Adjust the position of tick labels
ax.tick_params(axis="y", pad=-5)  # 'pad' 값을 조절하여 y축 tick 라벨의 위치를 변경합니다.
ax.tick_params(axis="x", pad=-5)  # 'pad' 값을 조절하여 x축 tick 라벨의 위치를 변경합니다.

plt.xlabel('Cluster ID')
plt.ylabel('Subject ID')
plt.yticks(rotation=0)

# 히트맵 주위에 테두리 추가
current_axis = plt.gca()
current_axis.add_patch(patches.Rectangle((0, 0), df.shape[1], df.shape[0], fill=False, edgecolor='black', lw=2))

# Save the plot as a png file
plt.savefig(zSavePathName + "/cluster_assign_with_border.png", bbox_inches='tight', dpi=300)
plt.show()

#%%
# 근육 이름 설정
zMuscleName = ['GM', 'RF', 'VL', 'VM', 'BF', 'MG', 'TA', 'PL', 'SO', 'ES']
# 모든 채널
zMuscleName = ['GM', 'Gm', 'AD', 'RF', 'VL', 'VM', 'BF', 'ST', 'MG', 'LG', 'TA', 'PL', 'SO', 'ES', 'MF', 'IO']

total_subjects = len(emgProceedSet)

import seaborn as sns
import pandas as pd

# Seaborn 스타일 설정
sns.set_style("whitegrid")

# 그래프의 배치 변경 (len(nmfStrClust)행 2열)
fig, axes = plt.subplots(len(nmfStrClust), 2, figsize=(16, 18))

for j, i in enumerate(sorted_indices):
    # 시너지 활성 그래프 그리기 (왼쪽에 위치)
    sns.lineplot(x=range(100), y=nmfActClust_mean_overall[i], ax=axes[j, 0], color='blue')
    axes[j, 0].fill_between(range(100), nmfActClust_mean_overall[i] - nmfActClust_error_overall[i], nmfActClust_mean_overall[i] + nmfActClust_error_overall[i], color='blue', alpha=0.2)

    # 클러스터 이름과 참여 인원 %로 표기
    cluster_participation = round((nmfStrClust[i].shape[0] / total_subjects) * 100)
    title = f'Cluster {j+1} ({cluster_participation:.0f}%)'
    axes[j, 0].set_title(title, fontsize=24)
    axes[j, 0].title.set_position([1, 1.05])
    # Adjust the position of tick labels
    axes[j, 0].tick_params(axis="x", pad=2)  # 'pad' 값을 조절하여 x축 tick 라벨의 위치를 변경합니다.
    
    # x축 및 y축 라벨 제거
    axes[j, 0].set_xlabel('Squat cycle (%)')
    
    # y 값을 숨김
    axes[j, 0].set_yticks([])
    
    # Set xticklabels with desired font size
    xticks = axes[j, 0].get_xticks()
    axes[j, 0].set_xticklabels([int(x) for x in xticks], fontsize=16)
    
    # 시너지 구조 바 그래프 그리기 (오른쪽에 위치)
    df_for_bar = pd.DataFrame({
        'Muscles': range(len(nmfStrClust_means[i])),
        'Means': nmfStrClust_means[i]
    })
    sns.barplot(x='Muscles', y='Means', data=df_for_bar, ax=axes[j, 1], palette="viridis", ci=None)
    
    # Add error bars using Matplotlib
    axes[j, 1].errorbar(x=range(len(nmfStrClust_means[i])), y=nmfStrClust_means[i], yerr=nmfStrClust_errors[i], fmt='none', c='black', capsize=5)

    axes[j, 1].set_xticks(range(len(zMuscleName)))
    axes[j, 1].set_xticklabels(zMuscleName, fontsize=16)
    # Adjust the position of tick labels
    axes[j, 1].tick_params(axis="x", pad=2)  # 'pad' 값을 조절하여 x축 tick 라벨의 위치를 변경합니다.
    # x축 및 y축 라벨 제거
    axes[j, 1].set_ylabel('')
    
    # y 값을 숨김
    axes[j, 1].set_yticks([])

plt.tight_layout(pad=1.0)
# Save the plot as a png file
plt.savefig(zSavePathName + "/cluster_synergy_seaborn_vertical.png", dpi=300)
plt.show()



#%%
# # 그래프 그리기
# fig, axes = plt.subplots(2, len(nmfStrClust), figsize=(25, 12))

# for j, i in enumerate(sorted_indices):
#     # 시너지 활성 그래프 그리기 (위에 위치)
#     axes[0, j].plot(nmfActClust_mean_overall[i])
#     axes[0, j].fill_between(range(100), nmfActClust_mean_overall[i] - nmfActClust_error_overall[i], nmfActClust_mean_overall[i] + nmfActClust_error_overall[i], alpha=0.2)
    
#     axes[0, j].set_xticks([0, 20, 40, 60, 80, 100])  # 원하는 눈금으로 설정
#     axes[0, j].set_xticklabels([0, 20, 40, 60, 80, 100], fontsize=16)

#     # 클러스터 이름과 참여 인원 %로 표기
#     cluster_participation = (nmfStrClust[i].shape[0] / total_subjects) * 100
#     axes[0, j].set_title(f'Cluster {j+1} ({cluster_participation:.1f}%)', fontsize=24)

#     # y 값을 숨김
#     axes[0, j].set_yticks([])
#     axes[0, j].set_facecolor('white')  # 배경색을 흰색으로 설정

#     # 시너지 구조 바 그래프 그리기 (아래에 위치)
#     bars = axes[1, j].bar(range(len(nmfStrClust_means[i])), nmfStrClust_means[i], yerr=nmfStrClust_errors[i], capsize=5)
#     axes[1, j].set_xticks(range(len(zMuscleName)))
#     axes[1, j].set_xticklabels(zMuscleName, fontsize=10)

#     # y 값을 숨김
#     axes[1, j].set_yticks([])
#     axes[1, j].set_facecolor('white')  # 배경색을 흰색으로 설정

# plt.tight_layout(pad=3.0)
# # Save the plot as a png file
# plt.savefig(zSavePathName + "/cluster_synergy.png", dpi=300)  # "saved_figure.png"로 저장
# plt.show()



#%% 모션 데이터 계산
#스쿼트 동작 구간 평균 편차 분석
eventTriAve = np.mean(eventPhaseSet, axis=0)
eventTriSd = np.std(eventPhaseSet, axis=0)
eventSubAve = np.mean(eventPhaseSet, axis=1)
eventSubSd = np.std(eventPhaseSet, axis=1)\

#각도 평균 편차 분석
angTrunkXSet_np = np.array(angTrunkXSet)  # Convert to numpy array if not already
angTrunkXSet_mean = angTrunkXSet_np.mean(axis=(0, 1))  # Compute mean across first two dimensions
angTrunkXSet_sd = angTrunkXSet_np.std(axis=(0, 1))
angTrunkXSet_se = angTrunkXSet_sd/np.sqrt(len(angTrunkXSet))

angHipXSet_np = np.array(angHipXSet)  # Convert to numpy array if not already
angHipXSet_mean = angHipXSet_np.mean(axis=(0, 1))  # Compute mean across first two dimensions
angHipXSet_sd = angHipXSet_np.std(axis=(0, 1))
angHipXSet_se = angHipXSet_sd/np.sqrt(len(angTrunkXSet))

angKneeXSet_np = np.array(angKneeXSet)  # Convert to numpy array if not already
angKneeXSet_mean = angKneeXSet_np.mean(axis=(0, 1))  # Compute mean across first two dimensions
angKneeXSet_sd = angKneeXSet_np.std(axis=(0, 1))
angKneeXSet_se = angKneeXSet_sd/np.sqrt(len(angTrunkXSet))

angAnkleXSet_np = np.array(angAnkleXSet)  # Convert to numpy array if not already
angAnkleXSet_np = angAnkleXSet_np+15
angAnkleXSet_mean = angAnkleXSet_np.mean(axis=(0, 1))  # Compute mean across first two dimensions
angAnkleXSet_sd = angAnkleXSet_np.std(axis=(0, 1))
angAnkleXSet_se = angAnkleXSet_sd/np.sqrt(len(angTrunkXSet))

nmf_vafs_np = np.array(nmf_vafs)
nmf_vafs_mean = np.mean(nmf_vafs_np, axis=0)
nmf_vafs_sd = np.std(nmf_vafs_np, axis=0)
nmf_vafs_se = nmf_vafs_sd/np.sqrt(len(nmf_vafs_sd))
#%% 모션 그래프
import matplotlib.pyplot as plt
import seaborn as sns

# 설정: Seaborn 스타일로 그래프를 세련되게 만듭니다.
sns.set_style("whitegrid")

fig, axes = plt.subplots(4, 1, figsize=(10, 20))  # 4개의 서브플롯 생성

data_sets = [
    (angTrunkXSet_mean, angTrunkXSet_se, "Trunk"),
    (angHipXSet_mean, angHipXSet_se, "Hip"),
    (angKneeXSet_mean, angKneeXSet_se, "Knee"),
    (angAnkleXSet_mean, angAnkleXSet_se, "Ankle")
]

for ax, (mean, sd, title) in zip(axes, data_sets):
    ax.plot(mean, color='dodgerblue')
    ax.fill_between(range(len(mean)), 
                    mean - sd, 
                    mean + sd, 
                    color='skyblue', alpha=0.4)
    
    ax.set_title(f'{title}', fontsize=24)
    ax.set_xlabel('Squat cycle (%)', fontsize=20)
    ax.set_ylabel('Angle(Degree)', fontsize=20)
    ax.tick_params(axis='both', which='major', labelsize=20)
    # ax.legend(['Mean', 'SD'], loc='upper right')

plt.tight_layout()
plt.savefig(zSavePathName + "/motion.png", dpi=300) 
plt.show()
#%% VAF 그래프
import matplotlib.pyplot as plt
import numpy as np

# Seaborn 스타일 설정
plt.style.use('seaborn-whitegrid')  # 'whitegrid' ensures no inner fill color

# 그래프 생성
plt.figure(figsize=(10, 6))

# X축 값을 1부터 시작하도록 조정
x_values = np.arange(1, len(nmf_vafs_mean)+1)

# 평균 지점의 원 사이를 선으로 연결
plt.plot(x_values, nmf_vafs_mean, '-o', color='dodgerblue', markerfacecolor='dimgray')

# 오차막대 형태로 표준편차 표시
plt.errorbar(x_values, nmf_vafs_mean, yerr=nmf_vafs_sd, 
             fmt='o', color='coral', ecolor='darkgray', elinewidth=2, capsize=5, markerfacecolor='dimgray')

# 레이블 및 제목 설정
plt.xlabel('Muscle Synergy Number', fontsize=20)
plt.ylabel('Variance accounted for', fontsize=20)
plt.tick_params(axis='x', labelsize=20)  # X축 눈금 라벨의 글자 크기를 16으로 조정
plt.tick_params(axis='y', labelsize=20)  # Y축 눈금 라벨의 글자 크기를 16으로 조정

plt.legend()

# 그래프 표시
plt.tight_layout()
plt.savefig(zSavePathName + "/vaf_plot.png", bbox_inches='tight', facecolor='white', dpi=300)  # Save with a white background
plt.show()
#%% trunk 편차가 높은 이유 - 스쿼트 시 대상자마다 체간 각도가 다르다.
import matplotlib.pyplot as plt

# Seaborn 스타일 설정
plt.style.use('seaborn-whitegrid')

# 그래프 생성
plt.figure(figsize=(10, 6))

# 평균 지점을 선으로 연결
plt.plot(angTrunkXSet_mean, color='dodgerblue', linewidth=2)

# 각 개별 데이터를 투명하게 그림
for participant_data in angTrunkXSet_np:
    for trial_data in participant_data:
        plt.plot(trial_data, color='coral', alpha=0.1)  # alpha 값을 조절하여 투명도를 조정합니다.

# 레이블 및 제목 설정
plt.xlabel('Frame (out of 100)', fontsize=20)
plt.ylabel('Angle', fontsize=20)
plt.title('Trunk X Angle with Individual Data Overlay', fontsize=24)

# 그래프 표시
plt.tight_layout()
plt.show()
#%% 이차 분석 - 클러스터 2 vs 3
# 클러스터 2와 3의 대상자 그룹
cluster2_indices = [5, 10, 15]
cluster3_indices = [0, 1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13]

# 데이터 추출 함수
def extract_data_from_indices(data, indices):
    return data[indices, :, :]

# 각 클러스터의 평균과 표준편차 계산
def compute_cluster_mean_sd(data, indices):
    cluster_data = extract_data_from_indices(data, indices)
    cluster_mean = cluster_data.mean(axis=(0, 1))
    cluster_sd = cluster_data.std(axis=(0, 1))
    return cluster_mean, cluster_sd

# 데이터 설정
data_sources = [angTrunkXSet_np, angHipXSet_np, angKneeXSet_np, angAnkleXSet_np]
titles = ["Trunk", "Hip", "Knee", "Ankle"]

# 그래프 생성
fig, axes = plt.subplots(4, 1, figsize=(10, 20))  # 4개의 서브플롯 생성

# 데이터 그리기
for ax, (data, title) in zip(axes, zip(data_sources, titles)):
    # 클러스터 2
    mean2, sd2 = compute_cluster_mean_sd(data, cluster2_indices)
    ax.plot(mean2, color='dodgerblue', label="Cluster 2")
    ax.fill_between(range(len(mean2)), mean2 - sd2, mean2 + sd2, color='skyblue', alpha=0.4)

    # 클러스터 3
    mean3, sd3 = compute_cluster_mean_sd(data, cluster3_indices)
    ax.plot(mean3, color='coral', label="Cluster 3")
    ax.fill_between(range(len(mean3)), mean3 - sd3, mean3 + sd3, color='mistyrose', alpha=0.4)
    
    ax.set_title(f'{title}', fontsize=24)
    ax.set_ylabel('Angle(Degree)', fontsize=20)
    ax.tick_params(axis='both', which='major', labelsize=20)
    ax.legend(loc='upper right', fontsize=20)

axes[-1].set_xlabel('Squat cycle (%)', fontsize=20)
plt.tight_layout()
plt.savefig(zSavePathName + "/motion_overlay23.png", dpi=300) 
plt.show()
#%% 이차 분석 - 클러스터 5 vs 6
# 클러스터 5와 6의 대상자 그룹
# 클러스터 5: 3 6 11 12 13 14 15
# 클러스터 6: 1 2 4 5 7 8 9 10 16
cluster5_indices = [2, 5, 10, 11, 12, 13, 14]
cluster6_indices = [0, 1, 2, 3, 4, 6, 7, 8, 9, 15]

# 데이터 추출 함수
def extract_data_from_indices(data, indices):
    return data[indices, :, :]

# 각 클러스터의 평균과 표준편차 계산
def compute_cluster_mean_sd(data, indices):
    cluster_data = extract_data_from_indices(data, indices)
    cluster_mean = cluster_data.mean(axis=(0, 1))
    cluster_sd = cluster_data.std(axis=(0, 1))
    return cluster_mean, cluster_sd

# 데이터 설정
data_sources = [angTrunkXSet_np, angHipXSet_np, angKneeXSet_np, angAnkleXSet_np]
titles = ["Trunk", "Hip", "Knee", "Ankle"]

# 그래프 생성
fig, axes = plt.subplots(4, 1, figsize=(10, 20))  # 4개의 서브플롯 생성

# 데이터 그리기
for ax, (data, title) in zip(axes, zip(data_sources, titles)):
    # 클러스터 5
    mean5, sd5 = compute_cluster_mean_sd(data, cluster5_indices)
    ax.plot(mean5, color='dodgerblue', label="Cluster 5")
    ax.fill_between(range(len(mean5)), mean5 - sd5, mean5 + sd5, color='skyblue', alpha=0.4)

    # 클러스터 6
    mean6, sd6 = compute_cluster_mean_sd(data, cluster6_indices)
    ax.plot(mean6, color='coral', label="Cluster 6")
    ax.fill_between(range(len(mean6)), mean6 - sd6, mean6 + sd6, color='mistyrose', alpha=0.4)
    
    ax.set_title(f'{title}', fontsize=24)
    ax.set_ylabel('Angle(Degree)', fontsize=20)
    ax.tick_params(axis='both', which='major', labelsize=20)
    ax.legend(loc='upper right', fontsize=20)

axes[-1].set_xlabel('Squat cycle (%)', fontsize=20)
plt.tight_layout()
plt.savefig(zSavePathName + "/motion_overlay56.png", dpi=300) 
plt.show()
#%% 이차 분석 - 클러스터 1 vs 나머지
# 클러스터 1: 3 12 13 14 15
# 클러스터 : 1 2 4 5 6 7 8 9 10 11 16
cluster1_indices = [2, 11, 12, 13, 14]
cluster0_indices = [0, 1, 2, 3, 4, 6, 7, 8, 9, 15]

# 데이터 추출 함수
def extract_data_from_indices(data, indices):
    return data[indices, :, :]

# 각 클러스터의 평균과 표준편차 계산
def compute_cluster_mean_sd(data, indices):
    cluster_data = extract_data_from_indices(data, indices)
    cluster_mean = cluster_data.mean(axis=(0, 1))
    cluster_sd = cluster_data.std(axis=(0, 1))
    return cluster_mean, cluster_sd

# 데이터 설정
data_sources = [angTrunkXSet_np, angHipXSet_np, angKneeXSet_np, angAnkleXSet_np]
titles = ["Trunk", "Hip", "Knee", "Ankle"]

# 그래프 생성
fig, axes = plt.subplots(4, 1, figsize=(10, 20))  # 4개의 서브플롯 생성

# 데이터 그리기
for ax, (data, title) in zip(axes, zip(data_sources, titles)):
    # 클러스터 5
    mean5, sd5 = compute_cluster_mean_sd(data, cluster1_indices)
    ax.plot(mean5, color='dodgerblue', label="Cluster 1")
    ax.fill_between(range(len(mean5)), mean5 - sd5, mean5 + sd5, color='skyblue', alpha=0.4)

    # 클러스터 6
    mean6, sd6 = compute_cluster_mean_sd(data, cluster0_indices)
    ax.plot(mean6, color='coral', label="rest")
    ax.fill_between(range(len(mean6)), mean6 - sd6, mean6 + sd6, color='mistyrose', alpha=0.4)
    
    ax.set_title(f'{title}', fontsize=24)
    ax.set_ylabel('Angle(Degree)', fontsize=20)
    ax.tick_params(axis='both', which='major', labelsize=20)
    ax.legend(loc='upper right', fontsize=20)

axes[-1].set_xlabel('Squat cycle (%)', fontsize=20)
plt.tight_layout()
plt.savefig(zSavePathName + "/motion_overlay1rest.png", dpi=300) 
plt.show()
#%% 데이터 저장
with open('{}Squat0815.p'.format(zSavePathName), 'wb') as file:
    pickle.dump(emgProceedSet, file)
    pickle.dump(nmf_nums, file)
    pickle.dump(nmf_vafs, file)
    pickle.dump(synergy_activations, file)
    pickle.dump(synergy_structures, file)
    pickle.dump(clusterNumSet, file)
    pickle.dump(clusterClIdSet, file)
    pickle.dump(nmfStrClust, file)
    pickle.dump(nmfActClust, file)
    pickle.dump(clStrIcc, file)
#%%
######저장된 데이터 불러오기
with open('{}Squat0815.p'.format(zSavePathName), 'rb') as file:
    emgProceedSet = pickle.load(file)
    nmf_nums = pickle.load(file)    
    nmf_vafs = pickle.load(file)    
    synergy_activations = pickle.load(file)    
    synergy_structures = pickle.load(file)    
    clusterNumSet = pickle.load(file)    
    clusterClIdSet = pickle.load(file)    
    nmfStrClust = pickle.load(file)    
    nmfActClust = pickle.load(file)    
    clStrIcc = pickle.load(file)    
nmfStrClust_means = [np.mean(cluster, axis=0) for cluster in nmfStrClust]
# 시너지 활성의 평균과 표준오차 계산
# 먼저 2000 프레임을 20 trials의 100개 프레임으로 분할
nmfActClust_reshaped = [cluster.reshape(-1, 20, 100) for cluster in nmfActClust]
# 전체 평균 및 표준오차 계산
nmfActClust_mean_overall = [np.mean(reshaped_cluster, axis=(0, 1)) for reshaped_cluster in nmfActClust_reshaped]
nmfActClust_error_overall = [np.std(reshaped_cluster, axis=(0, 1))/np.sqrt(reshaped_cluster.shape[1]*reshaped_cluster.shape[0]) for reshaped_cluster in nmfActClust_reshaped]

# 시너지 활성의 피크 위치에 따라 클러스터 순서를 정렬
peak_positions = [np.argmax(mean) for mean in nmfActClust_mean_overall]
sorted_indices = np.argsort(peak_positions)

# 활성 순서 기준 클러스터 ICC값
clStrIcc_sorted = [clStrIcc[i] for i in sorted_indices]

nmfStrClust_means_sorted = [nmfStrClust_means[i] for i in sorted_indices]
nmfStrClust_means_sorted = np.vstack(nmfStrClust_means_sorted)
    
