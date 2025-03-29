#!/bin/bash

# ruff 체크 및 수정
uv run ruff check . --fix
echo "✅ ruff 체크 및 수정 완료"


# ruff 포맷팅
uv run ruff format .
echo "✅ ruff 포맷팅 완료"

# mypy 타입 검사
uv run mypy .
echo "✅ mypy 타입 검사 완료"
