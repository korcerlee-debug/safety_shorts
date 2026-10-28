from io import BytesIO
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from google import genai
import streamlit as st

st.set_page_config(page_title="안전 쇼츠 자동 제작기", layout="wide")
st.title("🚨 안전 교육 및 홍보 쇼츠/릴스 자동 생성기")

# 사이드바: API 키 입력 및 상시 저장
st.sidebar.header("설정")
st.sidebar.markdown(
    "👉 [구글 API 키 무료 발급받기 (Google AI"
    " Studio)](https://aistudio.google.com/app/apikey)"
)

saved_api_key = ""
if "GEMINI_API_KEY" in os.environ:
  saved_api_key = os.environ["GEMINI_API_KEY"]

api_key = st.sidebar.text_input(
    "Google Gemini API Key",
    value=saved_api_key,
    type="password",
    placeholder="API 키를 입력하세요",
)

if api_key:
  os.environ["GEMINI_API_KEY"] = api_key

if not api_key:
  st.warning("좌측 사이드바에 Google Gemini API Key를 입력해주세요.")
  st.info("위의 링크 버튼을 눌러 무료로 API 키를 발급받으실 수 있습니다.")
  st.stop()

client = genai.Client(api_key=api_key)

# 세션 상태 초기화
if "cuts" not in st.session_state:
  st.session_state.cuts = []

st.header("1. 안전 관련 글 입력")
safety_text = st.text_area(
    "쇼츠로 만들고 싶은 안전 수칙, 사고 사례, 현장 가이드 등의 글을"
    " 입력하세요.",
    height=150,
    placeholder=(
        "예: 밀폐공간 작업 시 반드시 산소 및 유해가스 농도를 측정해야 합니다..."
    ),
)

if st.button("🎬 6~8컷 시나리오 및 이미지 프롬프트 생성"):
  if not safety_text:
    st.error("내용을 입력해주세요.")
  else:
    with st.spinner(
        "AI가 안전 글을 분석하여 쇼츠 구성과 이미지 프롬프트를 만드는 중..."
    ):
      prompt = f"""
            다음 글을 바탕으로 쇼츠/릴스 영상용 6~8컷의 스토리보드를 만들어주세요.
            반드시 아래 JSON 리스트 형식으로만 답변해주세요 (다른 설명 없이 ```json 과 ``` 사이에 넣어주세요):
            [
              {{"cut_number": 1, "narration": "자막 또는 나레이션 텍스트", "image_prompt": "English image prompt for vertical 9:16 illustration"}},
              ...
            ]
            
            입력된 글:
            {safety_text}
            """
      try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )

        import json
        import re

        text_content = response.text
        match = re.search(r"```json\s*(.*?)\s*```", text_content, re.DOTALL)
        if match:
          json_str = match.group(1)
          st.session_state.cuts = json.loads(json_str)
          st.success("시나리오 생성 완료!")
        else:
          st.session_state.cuts = json.loads(text_content)
          st.success("시나리오 생성 완료!")
      except Exception as e:
        st.error(f"오류 발생: {e}")
        st.write(
            "AI 응답 원본:",
            response.text if "response" in locals() else "응답 없음",
        )

if st.session_state.cuts:
  st.markdown("---")
  st.header("2. 컷 별 자막 및 이미지 프롬프트 수정 & 생성")
  st.info(
      "원하는 컷의 텍스트나 이미지 프롬프트를 수정한 뒤 '이미지 생성' 버튼을"
      " 누를 수 있습니다."
  )

  for i, cut in enumerate(st.session_state.cuts):
    with st.expander(
        f"컷 {cut.get('cut_number', i+1)} 상세 설정", expanded=True
    ):
      col_edit1, col_edit2 = st.columns([2, 1])

      with col_edit1:
        cut["narration"] = st.text_input(
            f"자막/나레이션 {i+1}",
            cut.get("narration", ""),
            key=f"narr_{i}",
        )
        cut["image_prompt"] = st.text_area(
            f"이미지 생성 프롬프트 (영어 권장) {i+1}",
            cut.get("image_prompt", ""),
            key=f"prompt_{i}",
        )
        if st.button(f"🎨 이 컷 이미지 생성/재생성", key=f"gen_{i}"):
          with st.spinner("세로형 쇼츠 카드 렌더링 중..."):
            try:
              # 9:16 비율 세로형 해상도 (720 x 1280)
              img_width, img_height = 720, 1280
              # 모던한 다크/시네마틱 배경 톤
              img = Image.new(
                  "RGB", (img_width, img_height), color=(25, 28, 36)
              )
              draw = ImageDraw.Draw(img)

              # 세로형 카드 프레임 박스 디자인
              draw.rounded_rectangle(
                  [40, 40, img_width - 40, img_height - 40],
                  radius=24,
                  fill=(38, 43, 54),
                  outline=(70, 80, 100),
                  width=4,
              )

              # 상단 컷 번호 배지 영역
              draw.rounded_rectangle(
                  [80, 90, 260, 170],
                  radius=12,
                  fill=(220, 60, 60),
              )

              try:
                font_title = ImageFont.load_default()
              except:
                font_title = None

              # 텍스트 배치 (세로 정렬감 유지)
              draw.text(
                  (110, 112),
                  f"CUT {i+1} SCENE",
                  fill=(255, 255, 255),
                  font=font_title,
              )

              # 나레이션 자막 가이드 박스
              draw.rounded_rectangle(
                  [80, 220, img_width - 80, 420],
                  radius=16,
                  fill=(48, 55, 68),
              )
              draw.text(
                  (110, 250),
                  "[ 자막 / 나레이션 ]",
                  fill=(140, 180, 255),
                  font=font_title,
              )
              narr_text = cut["narration"]
              draw.text(
                  (110, 290),
                  narr_text[:80] + ("..." if len(narr_text) > 80 else ""),
                  fill=(240, 240, 240),
                  font=font_title,
              )

              # 이미지 프롬프트 가이드 박스
              draw.rounded_rectangle(
                  [80, 470, img_width - 80, img_height - 100],
                  radius=16,
                  fill=(48, 55, 68),
              )
              draw.text(
                  (110, 500),
                  "[ 이미지 생성 프롬프트 ]",
                  fill=(255, 200, 100),
                  font=font_title,
              )

              prompt_text = cut["image_prompt"]
              # 프롬프트 내용 길이에 맞춰 깔끔하게 출력
              y_pos = 550
              for chunk_start in range(0, min(len(prompt_text), 300), 40):
                chunk = prompt_text[chunk_start : chunk_start + 40]
                draw.text(
                    (110, y_pos),
                    chunk,
                    fill=(220, 220, 220),
                    font=font_title,
                )
                y_pos += 35

              os.makedirs("temp_images", exist_ok=True)
              img_path = f"temp_images/cut_{i+1}.png"
              img.save(img_path)
              cut["image_path"] = img_path
              st.success(f"컷 {i+1} 세로형 쇼츠 카드 생성 완료!")
            except Exception as e:
              st.error(f"이미지 생성 실패: {e}")

      with col_edit2:
        if "image_path" in cut and os.path.exists(cut["image_path"]):
          st.image(
              cut["image_path"],
              width=220,
              caption=f"컷 {i+1} 세로형 미리보기 (9:16)",
          )
        else:
          st.write("아직 생성된 이미지가 없습니다.")

  st.markdown("---")
  st.header("3. 최종 쇼츠 영상 제작 (컷신 합치기)")
  fps = st.slider(
      "장면 전환 속도 (초당 프레임 수 - 낮을수록 한 화면이 오래 보임)",
      min_value=1,
      max_value=5,
      value=1,
  )

  if st.button("🎥 최종 쇼츠 영상 파일 만들기"):
    valid_cuts = [
        c
        for c in st.session_state.cuts
        if "image_path" in c and os.path.exists(c["image_path"])
    ]
    if not valid_cuts:
      st.error(
          "생성된 이미지가 없습니다. 각 컷의 '이미지 생성' 버튼을 먼저"
          " 눌러주세요."
      )
    else:
      with st.spinner("영상을 렌더링 중입니다..."):
        output_video = "safety_shorts.mp4"
        first_img = cv2.imread(valid_cuts[0]["image_path"])
        height, width, _ = first_img.shape

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

        frames_per_image = fps * 3

        for cut in valid_cuts:
          img = cv2.imread(cut["image_path"])
          img = cv2.resize(img, (width, height))
          for _ in range(frames_per_image):
            out.write(img)

        out.release()
        st.success("영상 제작 완료!")
        st.video(output_video)

        with open(output_video, "rb") as file:
          st.download_button(
              label="📥 완성된 쇼츠 영상 다운로드 (.mp4)",
              data=file,
              file_name="safety_shorts.mp4",
              mime="video/mp4",
          )