# 이슈 002: Git ignore 규칙 정리 및 생성된 EMG 산출물 추적 해제

**상태**: 완료
**생성일**: 2026-03-06

## 배경

저장소에는 생성된 fixture 파일, baseline reference 출력, 런타임 출력,
캐시 디렉터리가 섞여 있어 로컬에는 남겨두되 `git status`를 어지럽히지 않도록
부모 저장소의 추적 대상에서는 제외할 필요가 있습니다.

## 완료 기준

- [ ] `.gitignore`가 이 저장소의 생성 런타임 출력과 캐시 산출물을 무시한다.
- [ ] 선택한 fixture 및 reference 출력 파일이 Git 인덱스에서만 제거되고 디스크에는 유지된다.
- [ ] `git status`에서 해당 ignore 대상이 untracked 또는 modified tracked 파일로 더 이상 보이지 않는다.
- [ ] `.agents`가 tracked submodule/gitlink라서 별도 처리 대상이라는 점이 명확히 기록된다.

## 작업 목록

- [x] 1. 현재 ignore 규칙과 tracked 산출물 범위를 점검한다.
- [x] 2. 저장소 전용 생성 산출물 경로를 `.gitignore`에 반영한다.
- [x] 3. 생성된 fixture 및 baseline 출력 파일을 Git 인덱스에서만 제거한다.
- [x] 4. `git status`를 다시 확인해 정리 결과를 검증한다.
- [x] 5. 한국어 커밋 메시지로 정리 작업을 남긴다.

## 참고 사항

이 작업은 로컬 파일은 유지한 채 ignore 규칙과 Git 인덱스만 조정하는 것을 목표로 합니다.
`.agents` 항목은 submodule/gitlink이므로 `.gitignore`만으로 숨길 수 없습니다. 검증 결과 생성 파일은 디스크에 그대로 남아 있고, 인덱스 해제 후에는 ignore 대상으로 처리됩니다.
