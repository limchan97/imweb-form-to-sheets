# 아임웹 입력폼 → 구글시트 자동 동기화

청담디어의원 아임웹 관리자 페이지의 "울써마지 대학 제휴 DB" 입력폼 신청 데이터를
3시간마다 자동으로 [구글시트](https://docs.google.com/spreadsheets/d/1-V6-SzJc3wBKnAB_elUA2wNMnK-lFTjSLmf6xza0fUs)로 옮기는 자동화입니다.

아임웹이 입력폼에 대한 공식 API/웹훅을 제공하지 않아, 관리자 페이지에 자동 로그인해
"내보내기" 엑셀을 받아온 뒤 구글시트에 없는 새 데이터만 추가하는 방식으로 동작합니다.

## 설정 순서 (직접 하셔야 하는 부분)

### 1. GitHub 저장소 준비
1. https://github.com 가입 (이미 있으면 생략)
2. 저는 이 폴더 내용을 **비공개(private) 저장소**로 올려드릴 수 있습니다 — 가입 후 알려주세요.

### 2. 아임웹 로그인 정보를 GitHub Secret으로 등록
비밀번호가 대화 기록에 남지 않도록, 아래 명령어는 **직접 터미널에 입력**해 실행해 주세요.
(저장소 생성 후 `gh` CLI 로그인이 되어 있어야 합니다: `gh auth login`)

```bash
gh secret set IMWEB_ADMIN_ID --repo <본인계정>/<저장소이름>
gh secret set IMWEB_ADMIN_PW --repo <본인계정>/<저장소이름>
```
명령어 실행 후 값을 입력하라는 프롬프트가 뜨면 아이디/비밀번호를 입력하세요.

### 3. 구글 서비스 계정 만들기 (구글시트 쓰기 권한용)
1. https://console.cloud.google.com 접속 → 새 프로젝트 생성
2. "API 및 서비스" → "라이브러리"에서 **Google Sheets API** 검색 후 사용 설정
3. "API 및 서비스" → "사용자 인증 정보" → "사용자 인증 정보 만들기" → "서비스 계정" 생성
4. 생성된 서비스 계정 → "키" 탭 → "키 추가" → "JSON" 선택해서 다운로드
5. 다운로드된 JSON 파일을 열어보면 `"client_email": "xxx@xxx.iam.gserviceaccount.com"` 같은 이메일이 있습니다.
   이 이메일을 대상 [구글시트](https://docs.google.com/spreadsheets/d/1-V6-SzJc3wBKnAB_elUA2wNMnK-lFTjSLmf6xza0fUs)에
   **편집자(Editor)** 권한으로 공유해주세요.
6. 아래 명령어로 JSON 파일 전체를 Secret으로 등록 (파일 경로만 바꿔서 실행):
```bash
gh secret set GOOGLE_SERVICE_ACCOUNT_JSON --repo <본인계정>/<저장소이름> < "다운로드한파일.json"
```

### 4. 최초 1회 동작 확인
1. GitHub 저장소 → Actions 탭 → "아임웹 입력폼 -> 구글시트 동기화" 워크플로우 →
   "Run workflow" 버튼으로 수동 실행
2. 로그를 확인해 정상적으로 로그인/다운로드/시트 반영이 되는지 확인
3. **처음 실행에서 로그인 화면 선택자(selector)가 맞지 않아 실패할 가능성이 있습니다.**
   `scripts/sync_form_to_sheet.py` 상단의 `LOGIN_ID_SELECTOR`, `LOGIN_PW_SELECTOR`,
   `LOGIN_SUBMIT_SELECTOR`, `EXPORT_BUTTON_SELECTOR` 값을 실제 페이지 구조에 맞게
   수정해야 할 수 있습니다 — 실패 로그를 저에게 알려주시면 같이 고치겠습니다.

## 이후 운영
- 등록만 해두면 3시간마다 자동으로 실행됩니다 (Actions 탭에서 실행 이력 확인 가능)
- 아임웹 관리자 페이지 UI가 바뀌면 스크립트가 실패할 수 있으니, 가끔 Actions 탭에서
  실행 실패(빨간 X) 여부를 확인해주세요
