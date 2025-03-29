from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from typing import Any, Optional


class GoogleDocsService:
    def __init__(self) -> None:
        # Google Docs API와 Drive API 모두에 대한 스코프 설정
        SCOPES = [
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/spreadsheets",
        ]

        self.credentials = Credentials.from_service_account_file(
            "service-account.json", scopes=SCOPES
        )
        self.docs_service = build("docs", "v1", credentials=self.credentials)
        self.drive_service = build("drive", "v3", credentials=self.credentials)

    def get_document(self, document_id: str) -> dict:
        """
        Google Docs 문서의 내용을 가져옵니다.

        Args:
            document_id (str): Google Docs 문서 ID

        Returns:
            dict: 문서의 내용을 포함하는 딕셔너리
        """
        try:
            return self.docs_service.documents().get(documentId=document_id).execute()
        except Exception as e:
            print(f"문서 접근 중 오류 발생: {str(e)}")
            raise

    # 중복된 메서드 제거
    def get_document_content(self, document_id: str):
        """
        Google Docs 문서의 내용을 가져오고 필요한 형식으로 처리합니다.

        Args:
            document_id (str): Google Docs 문서 ID

        Returns:
            dict: 처리된 문서 내용
        """
        doc = self.get_document(document_id)
        # 여기에 문서 내용 처리 로직 추가
        return doc

    def create_document(
        self, title: str, parent_folder_id: str = None, content: dict = None
    ) -> dict:
        """
        Google Docs에 새 문서를 생성하고 지정된 폴더로 이동합니다.

        Args:
            title (str): 생성할 문서의 제목
            parent_folder_id (str): 문서를 생성할 Google Drive 폴더 ID
            content (dict, optional): 문서에 추가할 초기 내용

        Returns:
            dict: 생성된 문서의 정보
        """
        try:
            # 1. 기본 문서 생성
            document = {"title": title}

            # 2. Docs API로 문서 생성
            doc = self.docs_service.documents().create(body=document).execute()
            doc_id = doc.get("documentId")
            print(f"생성된 문서 ID: {doc_id}")

            # 3. 특정 폴더로 이동 (Drive API 사용)
            if parent_folder_id:
                # 현재 부모 폴더 가져오기
                file = (
                    self.drive_service.files()
                    .get(fileId=doc_id, fields="parents")
                    .execute()
                )

                # 이전 부모 폴더에서 제거하고 새 폴더로 이동
                previous_parents = ",".join(file.get("parents", []))

                # 파일 이동 (addParents와 removeParents 사용)
                self.drive_service.files().update(
                    fileId=doc_id,
                    addParents=parent_folder_id,
                    removeParents=previous_parents,
                    fields="id, parents",
                ).execute()
                print(f"문서가 폴더 {parent_folder_id}로 이동되었습니다.")

            # 4. 초기 내용이 있는 경우 내용 추가
            if content:
                requests = [
                    {
                        "insertText": {
                            "location": {"index": 1},
                            "text": content.get("text", ""),
                        }
                    }
                ]

                self.docs_service.documents().batchUpdate(
                    documentId=doc_id, body={"requests": requests}
                ).execute()

            return doc

        except Exception as e:
            print(f"문서 생성 중 오류 발생: {str(e)}")
            raise

    def edit_document(
        self, document_id: str, title: str = None, content: dict = None
    ) -> dict:
        """
        Google Docs 문서의 내용을 수정합니다.

        Args:
            document_id (str): Google Docs 문서 ID
            title (str, optional): 수정할 제목
            content (dict, optional): 수정할 내용 {'text': '내용', 'index': 시작위치}

        Returns:
            dict: 수정된 문서의 정보
        """
        try:
            # 1. 문서 존재 여부 확인
            doc = self.docs_service.documents().get(documentId=document_id).execute()

            if not doc:
                raise Exception(f"문서 ID {document_id}가 존재하지 않습니다.")

            # 2. 제목 수정 (Drive API 사용)
            if title:
                self.drive_service.files().update(
                    fileId=document_id, body={"name": title}, fields="id, name"
                ).execute()
                print(f'문서 제목이 "{title}"로 수정되었습니다.')

            # 3. 내용 수정
            if content:
                # 3.1 기존 내용 삭제 (선택적)
                if content.get("clear_existing", False):
                    # 문서 전체 내용 가져오기
                    doc_content = (
                        self.docs_service.documents()
                        .get(documentId=document_id)
                        .execute()
                    )

                    # 문서 끝 위치 확인
                    end_index = (
                        doc_content.get("body", {})
                        .get("content", [{}])[-1]
                        .get("endIndex", 1)
                    )

                    # 전체 내용 삭제 요청
                    clear_request = {
                        "deleteContentRange": {
                            "range": {"startIndex": 1, "endIndex": end_index - 1}
                        }
                    }

                    self.docs_service.documents().batchUpdate(
                        documentId=document_id, body={"requests": [clear_request]}
                    ).execute()

                # 3.2 새 내용 추가
                insert_index = content.get("index", 1)  # 기본값 1 (문서 시작)
                requests = [
                    {
                        "insertText": {
                            "location": {"index": insert_index},
                            "text": content.get("text", ""),
                        }
                    }
                ]

                # 3.3 텍스트 스타일 지정 (옵션)
                if content.get("style"):
                    style = content["style"]
                    requests.append(
                        {
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": insert_index,
                                    "endIndex": insert_index
                                    + len(content.get("text", "")),
                                },
                                "textStyle": style,
                                "fields": "bold,italic,fontSize,foregroundColor",
                            }
                        }
                    )

                # 요청 실행
                result = (
                    self.docs_service.documents()
                    .batchUpdate(documentId=document_id, body={"requests": requests})
                    .execute()
                )

                if result:
                    print("문서 내용이 수정되었습니다.")

            # 4. 수정된 문서 정보 반환
            return self.get_document(document_id)

        except Exception as e:
            print(f"문서 수정 중 오류 발생: {str(e)}")
            raise

    def create_spreadsheet(
        self, title: str, parent_folder_id: str = None, content: dict = None
    ) -> dict:
        """
        Google Sheets에 새 스프레드시트를 생성하고 지정된 폴더로 이동합니다.

        Args:
            title (str): 생성할 스프레드시트의 제목
            parent_folder_id (str, optional): 스프레드시트를 생성할 Google Drive 폴더 ID
            content (dict, optional): 스프레드시트에 추가할 초기 내용
                {
                    'values': [['A1', 'B1'], ['A2', 'B2']],  # 2D 배열 형태의 데이터
                    'range': 'Sheet1!A1:B2'  # 데이터를 입력할 범위
                }

        Returns:
            dict: 생성된 스프레드시트의 정보
        """
        try:
            # 1. Sheets 서비스 생성
            sheets_service = build("sheets", "v4", credentials=self.credentials)

            # 2. 새 스프레드시트 생성
            spreadsheet_body = {"properties": {"title": title}}

            spreadsheet = (
                sheets_service.spreadsheets()
                .create(body=spreadsheet_body, fields="spreadsheetId")
                .execute()
            )

            spreadsheet_id = spreadsheet.get("spreadsheetId")
            print(f"생성된 스프레드시트 ID: {spreadsheet_id}")

            # 3. 특정 폴더로 이동 (Drive API 사용)
            if parent_folder_id:
                # 현재 부모 폴더 가져오기
                file = (
                    self.drive_service.files()
                    .get(fileId=spreadsheet_id, fields="parents")
                    .execute()
                )

                # 이전 부모 폴더에서 제거하고 새 폴더로 이동
                previous_parents = ",".join(file.get("parents", []))

                # 파일 이동
                self.drive_service.files().update(
                    fileId=spreadsheet_id,
                    addParents=parent_folder_id,
                    removeParents=previous_parents,
                    fields="id, parents",
                ).execute()
                print(f"스프레드시트가 폴더 {parent_folder_id}로 이동되었습니다.")

            # 4. 초기 내용이 있는 경우 내용 추가
            if content and "values" in content:
                range_name = content.get("range", "Sheet1!A1")
                value_input_option = "USER_ENTERED"

                value_range_body = {"values": content["values"]}

                sheets_service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption=value_input_option,
                    body=value_range_body,
                ).execute()
                print("스프레드시트에 내용이 추가되었습니다.")

            # 5. 생성된 스프레드시트 정보 반환
            return {
                "spreadsheetId": spreadsheet_id,
                "title": title,
                "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
            }

        except Exception as e:
            print(f"스프레드시트 생성 중 오류 발생: {str(e)}")
            raise

    def edit_spreadsheet(
        self, spreadsheet_id: str, title: str = None, content: dict = None
    ) -> dict:
        """
        Google Sheets 스프레드시트의 내용을 수정합니다.

        Args:
            spreadsheet_id (str): Google Sheets 스프레드시트 ID
            title (str, optional): 수정할 제목
            content (dict, optional): 수정할 내용
                {
                    'values': [['A1', 'B1'], ['A2', 'B2']],  # 2D 배열 형태의 데이터
                    'range': 'Sheet1!A1:B2',  # 데이터를 입력할 범위
                    'clear_range': 'Sheet1!A1:Z100',  # 지울 범위 (선택사항)
                }

        Returns:
            dict: 수정된 스프레드시트의 정보
        """
        try:
            # 1. Sheets 서비스 생성
            sheets_service = build("sheets", "v4", credentials=self.credentials)

            # 2. 제목 수정 (Drive API 사용)
            if title:
                self.drive_service.files().update(
                    fileId=spreadsheet_id, body={"name": title}, fields="id, name"
                ).execute()
                print(f'스프레드시트 제목이 "{title}"로 수정되었습니다.')

            # 3. 내용 수정
            if content:
                # 3.1 특정 범위 지우기 (선택적)
                if content.get("clear_range"):
                    sheets_service.spreadsheets().values().clear(
                        spreadsheetId=spreadsheet_id, range=content["clear_range"]
                    ).execute()
                    print(f"범위 {content['clear_range']}의 내용이 삭제되었습니다.")

                # 3.2 새 내용 추가
                if "values" in content:
                    range_name = content.get("range", "Sheet1!A1")
                    value_input_option = "USER_ENTERED"

                    value_range_body = {"values": content["values"]}

                    sheets_service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range=range_name,
                        valueInputOption=value_input_option,
                        body=value_range_body,
                    ).execute()
                    print(f"범위 {range_name}에 새 내용이 추가되었습니다.")

            # 4. 수정된 스프레드시트 정보 반환
            return {
                "spreadsheetId": spreadsheet_id,
                "title": title if title else "제목 없음",
                "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
            }

        except Exception as e:
            print(f"스프레드시트 수정 중 오류 발생: {str(e)}")
            raise


if __name__ == "__main__":
    try:
        docs_service = GoogleDocsService()

        # 1. 스프레드시트 생성
        folder_id = "1q8bVYMPZPfGXVCikhHnK-guGe649_nq4"
        new_sheet = docs_service.create_spreadsheet(
            title="테스트 스프레드시트",
            parent_folder_id=folder_id,
            content={
                "values": [
                    ["이름", "나이", "직업"],
                    ["홍길동", "30", "개발자"],
                    ["김철수", "25", "디자이너"],
                ],
                "range": "Sheet1!A1:C3",
            },
        )
        print("\n생성된 스프레드시트 정보:", new_sheet)

        # 2. 스프레드시트 수정
        spreadsheet_id = new_sheet["spreadsheetId"]
        edited_sheet = docs_service.edit_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            title="수정된 스프레드시트",
            content={
                # 'clear_range': 'Sheet1!A1:C3',  # 기존 내용 삭제
                "values": [
                    ["부서", "인원", "예산"],
                    ["개발팀", "10", "1000만원"],
                    ["디자인팀", "5"],
                ],
                "range": "Sheet1!A1:C3",
            },
        )
        print("\n수정된 스프레드시트 정보:", edited_sheet)

    except Exception as e:
        print(f"오류 발생: {str(e)}")
