from io import BytesIO
import os
import time
import urllib.parse
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from google import genai
import requests
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

st.header("1. 쇼츠 시나리오 글 입력")
safety_text = st.text_area(
    "쇼츠로 만들고 싶은 내용, 안전 수칙, 썰, 정보 등의 글을 입력하세요.",
    height=150,
    placeholder=(
        "예: 자소서에 맨날 나오는 안전보건관리체계, 도대체 뭘까요? 핵심만 짚어드립니다."
    ),
)

if st.button("🎬 6~8컷 쇼츠 시나리오 및 이미지 프롬프트 생성"):
  if not safety_text:
    st.error("내용을 입력해주세요.")
  else:
    with st.spinner(
        "AI가 쇼츠 하단 자막에 맞게 짧고 임팩트 있는 구성으로 나누는 중..."
    ):
      # 자막을 쇼츠 하단에 들어가기 좋게 아주 짧게(1문장 내외) 작성하도록 프롬프트 지시 강화
      prompt = f"""
            다음 글을 바탕으로 쇼츠/릴스 영상용 6~8컷의 스토리보드를 만들어주세요.
            조건: 각 컷의 'narration'은 쇼츠 하단 자막으로 쓰기 좋게 1문장의 아주 짧고 임팩트 있는 핵심 문구(20자 이내 권장)로 작성해주세요.
            반드시 아래 JSON 리스트 형식으로만 답변해주세요 (다른 설명 없이 ```json 과 ``` 사이에 넣어주세요):
            [
              {{"cut_number": 1, "narration": "짧은 자막 텍스트", "image_prompt": "English image prompt for vertical 9:16 illustration style, high quality, no text"}},
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
  st.header("2. 컷 별 자막 및 이미지 프롬프트 수정 & 일괄 생성")

  if st.button("✨ 모든 컷 이미지 한 번에 생성하기 (자막 자동 합성)", type="primary"):
    progress_bar = st.progress(0)
    total_cuts = len(st.session_state.cuts)

    for idx, cut in enumerate(st.session_state.cuts):
      try:
        user_prompt = cut["image_prompt"]
        clean_prompt = (
            f"{user_prompt}, vertical 9:16 aspect ratio, clean modern"
            " digital illustration, vibrant colors, masterpiece, no text,"
            " no words, no letters"
        )
        encoded_prompt = urllib.parse.quote(clean_prompt)
        img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&nologo=true&private=true"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        success = False
        for attempt in range(3):
          img_res = requests.get(img_url, headers=headers, timeout=60)
          if img_res.status_code == 200:
            # 1. 이미지 불러오기 및 9:16 비율 고정
            image = Image.open(BytesIO(img_res.content)).convert("RGB")
            image = image.resize((720, 1280))

            # 2. 이미지 하단에 자막바 및 자막 텍스트 합성
            draw = ImageDraw.Draw(image)
            
            # 하단 어두운 자막 배경 바 박스 그리기 (X: 40 ~ 680, Y: 1040 ~ 1220)
            draw.rounded_rectangle([40, 1040, 680, 1220], radius=16, fill=(15, 15, 20))
            
            # 테두리 포인트 효과
            draw.rounded_rectangle([40, 1040, 680, 1220], radius=16, outline=(60, 130, 246), width=3)

            # 자막 텍스트 삽입
            try:
              font = ImageFont.truetype("malgun.ttf", 36) # 윈도우 환경 기본 폰트 시도
            except:
              try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
              except:
                font = ImageFont.load_default()

            narration_text = cut["narration"]
            # 텍스트가 박스 안에 이쁘게 들어가도록 중앙 정렬 느낌으로 배치
            draw.text((70, 1100), narration_text, fill=(255, 255, 255), font=font)

            os.makedirs("temp_images", exist_ok=True)
            img_path = f"temp_images/cut_{idx+1}.png"
            image.save(img_path)
            cut["image_path"] = img_path
            success = True
            break
          else:
            time.sleep(2)

        progress_bar.progress((idx + 1) / total_cuts)
        time.sleep(1.5)
      except Exception as e:
        print(f"Cut {idx+1} error: {e}")

    st.success("🎉 모든 컷의 이미지가 자막 합성된 상태로 일괄 생성되었습니다!")
    st.rerun()

  st.info(
      "원하는 컷의 텍스트나 자막을 수정한 뒤 '개별 생성'을 누르거나, 위의 일괄 생성 버튼을 누르세요."
  )

  for i, cut in enumerate(st.session_state.cuts):
    with st.expander(
        f"컷 {cut.get('cut_number', i+1)} 상세 설정", expanded=True
    ):
      col_edit1, col_edit2 = st.columns([2, 1])

      with col_edit1:
        cut["narration"] = st.text_input(
            f"하단 자막/나레이션 {i+1}",
            cut.get("narration", ""),
            key=f"narr_{i}",
        )
        cut["image_prompt"] = st.text_area(
            f"이미지 생성 프롬프트 (영어 권장) {i+1}",
            cut.get("image_prompt", ""),
            key=f"prompt_{i}",
        )
        if st.button(f"🎨 이 컷 이미지 개별 생성/재생성", key=f"gen_{i}"):
          with st.spinner("AI 이미지 생성 및 자막 합성 중..."):
            try:
              user_prompt = cut["image_prompt"]
              clean_prompt = (
                  f"{user_prompt}, vertical 9:16 aspect ratio, clean modern"
                  " digital illustration, vibrant colors, masterpiece, no text,"
                  " no words, no letters"
              )
              encoded_prompt = urllib.parse.quote(clean_prompt)
              img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=1280&nologo=true&private=true"

              headers = {
                  "User-Agent": (
                      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
                  )
              }

              success = False
              for attempt in range(3):
                img_res = requests.get(img_url, headers=headers, timeout=60)
                if img_res.status_code == 200:
                  image = Image.open(BytesIO(img_res.content)).convert("RGB")
                  image = image.resize((720, 1280))

                  draw = ImageDraw.Draw(image)
                  draw.rounded_rectangle([40, 1040, 680, 1220], radius=16, fill=(15, 15, 20))
                  draw.rounded_rectangle([40, 1040, 680, 1220], radius=16, outline=(60, 130, 246), width=3)

                  try:
                    font = ImageFont.truetype("malgun.ttf", 36)
                  except:
                    font = ImageFont.load_default()

                  narration_text = cut["narration"]
                  draw.text((70, 1100), narration_text, fill=(255, 255, 255), font=font)

                  os.makedirs("temp_images", exist_ok=True)
                  img_path = f"temp_images/cut_{i+1}.png"
                  image.save(img_path)
                  cut["image_path"] = img_path
                  success = True
                  break
                else:
                  time.sleep(2)

              if success:
                st.success(f"컷 {i+1} 이미지 생성 및 자막 합성 성공!")
              else:
                st.error("이미지 서버 혼잡. 다시 시도해 주세요.")
            except Exception as e:
              st.error(f"이미지 생성 실패: {e}")

      with col_edit2:
        if "image_path" in cut and os.path.exists(cut["image_path"]):
          st.image(
              cut["image_path"],
              width=220,
              caption=f"컷 {i+1} 자막 포함 미리보기 (9:16)",
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
          "생성된 이미지가 없습니다. '모든 컷 이미지 한 번에 생성하기' 버튼을"
          " 먼저 눌러주세요."
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