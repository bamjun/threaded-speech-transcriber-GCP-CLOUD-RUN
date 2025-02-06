from fastapi import HTTPException
from google import genai



def call_ai_prompt(prompt_text: str, google_api_key: str) -> dict:
    """
    Gemini API의 generate_content 메서드를 사용하여 prompt_text에 대한 응답 결과를 반환합니다.
    """
    try:

        client = genai.Client(api_key=google_api_key)  # 실제 API 키로 대체하세요.
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt_text
        )

        return {"result": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
