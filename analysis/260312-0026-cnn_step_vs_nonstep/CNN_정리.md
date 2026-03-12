# 현재까지 유저가 이해한 것 
1. convolution: signal의 특징을 추출. 
	1. input data(e.g., image)는 3D Tensor(width * height * 3). 
	2. weight는 랜덤이지만, 학습을 통해서 algorithm이 자동적으로 조절.
	3. **Channel**: kernel을 통해서 3D로 feature 추출.
	4. **Padding**: kernel이 데이터를 explore 시, edge는 적게 연산되기 때문에 zero-padding 사용. 
	5. **stride**: kernel이 한번에 이동하는 범위. stride가 증가하면 ouput size는 감소하지만, 세밀한 정보를 놓칠 수 있음. 
2. **Normalization**: ReLU apply 전/후 데이터 정규화. 
3. **ReLU** activation function: convolution 결과에서 feature만 남기고 모두 0으로 변환. 
	1. apply ReLU activation function(f(x) = max(0, x)) to keep only the relevant features(positive values). 
	2. zero out the rest. 
4. **Normalization**: ReLU apply 전/후 데이터 정규화. 
5. pooling: 
	1. Translation Invariance: 위치가 바뀌어도 인식하도록, 
	2. Overfitting 방지: 핵심만 남기고 노이즈를 제거해 data 압축.
6. Dropout: 학습 시 뉴런을 무작위로 off 해서 특정 뉴런에만 의존하는 것을 막는다. overfitting 방지. 
7. flattening: 2 dimension을 1 dimension으로 convert.  
	1. 최근에는 파라미터를 더 줄이기 위해 Global Average Pooling(GAP) 방식을 사용한다. GAP는 각 채널의 평균값만 FC layer와 연결해 채널의 전체 matrix와 연결하는 flattening과 달리, parameter의 수를 크게 감소시킨다. 
8. fully connected layer(FC layer)
	1. nerual layer에서의 final layer. 
9. softmax: classification 모델의 가장 마지막에 붙는 함수. FC layer에서 나온 score들을 총합이 1.0이 되는 probability value로 변환. 