from typing import Any, Dict, Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


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

    def get_document(
        self, document_id: str, parent_folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Google Docs 문서의 내용을 가져옵니다.

        Args:
            document_id (str): Google Docs 문서 ID
            parent_folder_id (str, optional): 문서를 조회할 Google Drive 폴더 ID

        Returns:
            Dict[str, Any]: 문서의 내용을 포함하는 딕셔너리

        Raises:
            Exception: API 호출 중 오류 발생 시
        """
        try:
            if parent_folder_id:
                # 부모 폴더 ID가 제공된 경우, Drive API를 사용하여 문서의 부모 정보 조회
                return (
                    self.drive_service.files()
                    .get(fileId=document_id, fields="parents")
                    .execute()
                )
            else:
                # 기본적으로 Docs API를 사용하여 문서 내용 조회
                return (
                    self.docs_service.documents().get(documentId=document_id).execute()
                )
        except Exception as e:
            print(f"문서 접근 중 오류 발생: {str(e)}")
            raise

    def create_document(
        self,
        title: str,
        parent_folder_id: Optional[str] = None,
        content: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Google Docs에 새 문서를 생성하고 지정된 폴더로 이동합니다.

        Args:
            title (str): 생성할 문서의 제목
            parent_folder_id (str, optional): 문서를 생성할 Google Drive 폴더 ID
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

            # 명시적으로 딕셔너리 타입으로 반환
            return {
                "documentId": doc_id,
                "title": title,
                "success": True
            }

        except Exception as e:
            return {
                "error": str(e),
                "success": False
            }

    def edit_document(
        self,
        document_id: str,
        title: Optional[str] = None,
        content: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        self,
        title: str,
        parent_folder_id: Optional[str] = None,
        content: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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

            # 명시적으로 딕셔너리 타입으로 반환
            return {
                "spreadsheetId": spreadsheet_id,
                "title": title,
                "success": True
            }

        except Exception as e:
            return {
                "error": str(e),
                "success": False
            }

    def edit_spreadsheet(
        self,
        spreadsheet_id: str,
        title: Optional[str] = None,
        content: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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

    def get_spreadsheet(
        self, spreadsheet_id: str, parent_folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Google Spreadsheet의 정보를 가져오고, 필요한 경우 폴더 정보도 확인합니다.

        Args:
            spreadsheet_id (str): 스프레드시트 ID
            parent_folder_id (Optional[str]): 부모 폴더 ID

        Returns:
            Dict[str, Any]: 스프레드시트 정보와 폴더 정보
        """
        try:
            # 1. Sheets API로 스프레드시트 정보 가져오기
            sheets_service = build("sheets", "v4", credentials=self.credentials)
            spreadsheet_info = (
                sheets_service.spreadsheets()
                .get(spreadsheetId=spreadsheet_id)
                .execute()
            )

            # 2. 폴더 ID가 지정된 경우 Drive API로 폴더 확인 및 이동
            if parent_folder_id:
                # 현재 파일의 부모 폴더 정보 가져오기
                file_info = (
                    self.drive_service.files()
                    .get(fileId=spreadsheet_id, fields="parents")
                    .execute()
                )

                # 현재 부모 폴더에서 제거하고 새 폴더로 이동
                previous_parents = ",".join(file_info.get("parents", []))

                # 파일 이동
                self.drive_service.files().update(
                    fileId=spreadsheet_id,
                    addParents=parent_folder_id,
                    removeParents=previous_parents,
                    fields="id, parents",
                ).execute()

                # 이동된 파일 정보 가져오기
                updated_file = (
                    self.drive_service.files()
                    .get(fileId=spreadsheet_id, fields="parents,name,mimeType")
                    .execute()
                )

                # 스프레드시트 정보에 폴더 정보 추가
                spreadsheet_info["driveInfo"] = {
                    "parents": updated_file.get("parents", []),
                    "name": updated_file.get("name"),
                    "sheets_data": {
                        sheet["properties"]["title"]: sheets_service.spreadsheets().values().get(
                            spreadsheetId=spreadsheet_id,
                            range=f"{sheet['properties']['title']}!A:Z"  # 각 시트별 범위 지정
                        ).execute().get("values", [])
                        for sheet in spreadsheet_info.get("sheets", [])
                    }
                }

            return spreadsheet_info

        except Exception as e:
            print(f"스프레드시트 접근 중 오류 발생: {str(e)}")
            raise


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    try:
        docs_service = GoogleDocsService()

        # 스프레드시트 정보 가져오기 및 폴더 이동
        spreadsheet_id = "13vvzjMgz3-4WYZFs6LkXDOzDuJBCIQfqo7nX1H2PzmA"
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID_FOR_DEV")

        result = docs_service.create_spreadsheet(
            title="Test Sheet",           # 생성할 시트의 제목
            parent_folder_id=folder_id,   # 시트가 저장될 구글 드라이브 폴더 ID
            content={"values": [["Header1"], ["Data1"]]}  # 시트에 들어갈 초기 데이터
        )

    except Exception as e:
        print(f"오류 발생: {str(e)}")




# if __name__ == "__main__":
#     try:
#         docs_service = GoogleDocsService()

#         # 스프레드시트 정보 가져오기 및 폴더 이동
#         spreadsheet_id = "13vvzjMgz3-4WYZFs6LkXDOzDuJBCIQfqo7nX1H2PzmA"
#         folder_id = "1q8bVYMPZPfGXVCikhHnK-guGe649_nq4"

#         result = docs_service.get_spreadsheet(
#             spreadsheet_id=spreadsheet_id, parent_folder_id=folder_id
#         )

#         # 결과 출력
#         print("\n스프레드시트 제목:", result.get("properties", {}).get("title", ""))

#         if "driveInfo" in result:
#             print("\n폴더 정보:", result["driveInfo"]["parents"])
#             print("파일 이름:", result["driveInfo"]["name"])
#             print("파일 내용:", result["driveInfo"]["sheets_data"])

#     except Exception as e:
#         print(f"오류 발생: {str(e)}")
