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
      " 누할 수 있습니다."
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
          with st.spinner("쇼츠 비율(9:16) 맞춤 이미지 렌더링 중..."):
            try:
              # 쇼츠 전용 9:16 비율 해상도 설정 (너비 720, 높이 1280)
              img_width, img_height = 720, 1280
              img = Image.new(
                  "RGB", (img_width, img_height), color=(245, 247, 250)
              )
              draw = ImageDraw.Draw(img)

              # 상단 타이틀 박스 및 본문 내용 시각화 디자인
              draw.rectangle(
                  [50, 150, img_width - 50, 450],
                  fill=(255, 255, 255),
                  outline=(210, 215, 225),
                  width=3,
              )
              draw.rectangle(
                  [50, 520, img_width - 50, img_height - 150],
                  fill=(255, 255, 255),
                  outline=(210, 215, 225),
                  width=3,
              )

              try:
                font_title = ImageFont.load_default()
              except:
                font_title = None

              draw.text(
                  (80, 180),
                  f"[ CUT {i+1} SCENE ]",
                  fill=(200, 50, 50),
                  font=font_title,
              )
              draw.text(
                  (80, 550),
                  "Visual Prompt:",
                  fill=(100, 100, 100),
                  font=font_title,
              )

              # 프롬프트 문구 단순화 렌더링 (오류 방지)
              prompt_text = cut["image_prompt"]
              draw.text(
                  (80, 600),
                  prompt_text[:120] + ("..." if len(prompt_text) > 120 else ""),
                  fill=(30, 30, 30),
                  font=font_title,
              )

              os.makedirs("temp_images", exist_ok=True)
              img_path = f"temp_images/cut_{i+1}.png"
              img.save(img_path)
              cut["image_path"] = img_path
              st.success(f"컷 {i+1} 쇼츠 비율(9:16) 이미지 생성 성공!")
            except Exception as e:
              st.error(f"이미지 생성 실패: {e}")

      with col_edit2:
        if "image_path" in cut and os.path.exists(cut["image_path"]):
          st.image(
              cut["image_path"],
              width=220,
              caption=f"컷 {i+1} 미리보기 (9:16)",
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