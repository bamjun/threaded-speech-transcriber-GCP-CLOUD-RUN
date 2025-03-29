import time

import requests

from config.global_config import SPEECH_URL


def transcribe_segment(
    seg_file_name,
    seg_gs_uri,
    token,
    segment_index,
    polling_interval=10,
    max_attempts=1000,
):
    """
    분할된 오디오 파일에 대해 Speech-to-Text API 요청을 보내고, 폴링하여 전사 결과를 반환하는 함수.
    최대 polling 횟수를 60회로 설정하여, 최대 10분 동안 작업이 완료되길 기다립니다.
    """
    headers = {"Authorization": f"Bearer {token}"}
    seg_speech_request = {
        "config": {
            "encoding": "FLAC",
            "languageCode": "ko-KR",
            "useEnhanced": True,
            "audioChannelCount": 2,
            "enableSpeakerDiarization": True,
            "diarizationSpeakerCount": 2,
            "enableWordTimeOffsets": True,
        },
        "audio": {"uri": seg_gs_uri},
    }
    print(f"[세그먼트 {segment_index}] Speech 요청 전송: {seg_file_name}")
    response = requests.post(SPEECH_URL, json=seg_speech_request, headers=headers)
    result = response.json()
    if "name" not in result:
        raise Exception(
            f"[세그먼트 {segment_index}] Speech API 호출 실패: {response.text}"
        )
    operation_name = result["name"]
    operation_url = f"https://speech.googleapis.com/v1/operations/{operation_name}"

    attempt = 0
    operation_done = False
    while attempt < max_attempts and not operation_done:
        time.sleep(polling_interval)
        op_response = requests.get(operation_url, headers=headers)
        op_result = op_response.json()
        print(f"[세그먼트 {segment_index}] 폴링 응답 (시도 {attempt + 1}): {op_result}")

        if op_result.get("done"):
            operation_done = True
            if "error" in op_result:
                raise Exception(
                    f"[세그먼트 {segment_index}] Speech API 작업 에러: {op_result['error'].get('message', 'Unknown error')}"
                )
            if op_result.get("response") and op_result["response"].get("results"):
                conversation = ""
                SEGMENT_DURATION = 300.0
                for result in op_result["response"]["results"]:
                    alternative = result.get("alternatives", [])[0]
                    transcript = alternative.get("transcript", "").strip()
                    if not transcript:
                        continue
                    if "words" in alternative and alternative["words"]:
                        first_word = alternative["words"][0]
                        start_time_str = first_word.get("startTime", "0s")
                        if start_time_str.endswith("s"):
                            start_time = float(start_time_str.rstrip("s"))
                        else:
                            start_time = float(start_time_str)
                    else:
                        start_time = 0.0

                    cumulative_time = segment_index * SEGMENT_DURATION + start_time
                    cumulative_time_formatted = time.strftime(
                        "%H:%M:%S", time.gmtime(cumulative_time)
                    )
                    conversation += f"[{cumulative_time_formatted}] {transcript}\n"
                transcription = conversation.strip()
                print(f"[세그먼트 {segment_index}] 전사 결과: {transcription}")
                return (segment_index, transcription)
            raise Exception(
                f"[세그먼트 {segment_index}] 작업 완료되었으나 전사 결과가 비어 있습니다."
            )
        attempt += 1
    raise Exception(f"[세그먼트 {segment_index}] Speech-to-Text 작업 타임아웃")
