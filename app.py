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
        "AI가 쇼츠 하단 자막에 맞게 짧고 임팩트 있는 구성으로 나누는 중... (잠시만 기다려주세요)"
    ):
      prompt = f"""
            다음 글을 바탕으로 쇼츠/릴스 영상용 6~8컷의 스토리보드를 만들어주세요.
            조건: 각 컷의 'narration'은 쇼츠 하단 자막으로 쓰기 좋게 1문장의 아주 짧고 임팩트 있는 핵심 문구(15자 이내 권장)로 작성해주세요.
            반드시 아래 JSON 리스트 형식으로만 답변해주세요 (다른 설명 없이 ```json 과 ``` 사이에 넣어주세요):
            [
              {{"cut_number": 1, "narration": "짧은 자막 텍스트", "image_prompt": "English image prompt for vertical 9:16 simple flat vector illustration, minimalist cartoon style, clean background, no text"}},
              ...
            ]
            
            입력된 글:
            {safety_text}
            """
      
      response = None
      success = False
      for attempt in range(3):
        try:
          response = client.models.generate_content(
              model="gemini-3.8-flash",
              contents=prompt,
          )
          success = True
          break
        except Exception as e:
          time.sleep(3)

      if not success:
        st.error("서버가 혼잡하여 시나리오 생성에 실패했습니다. 잠시 후 다시 버튼을 눌러주세요.")
      else:
        try:
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
          st.error(f"데이터 파싱 오류 발생: {e}")
          st.write("AI 응답 원본:", response.text if response else "응답 없음")

if st.session_state.cuts:
  st.markdown("---")
  st.header("2. 컷 별 자막 및 이미지 프롬프트 수정 & 일괄 생성")

  if st.button("✨ 모든 컷 이미지 한 번에 생성하기 (서버 안정화 적용)", type="primary"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_cuts = len(st.session_state.cuts)

    for idx, cut in enumerate(st.session_state.cuts):
      status_text.text(f"진행 중: 총 {total_cuts}컷 중 {idx+1}번째 컷 생성 중...")
      try:
        user_prompt = cut["image_prompt"]
        clean_prompt = (
            f"{user_prompt}, vertical 9:16 aspect ratio, simple flat vector"
            " illustration, minimalist cartoon style, clean vector art,"
            " vibrant colors, no photorealistic, no text, no words, no letters"
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

        cut_success = False
        # 일괄 생성 시 각 컷마다 최대 4번 재시도 기회 부여
        for attempt in range(4):
          try:
            img_res = requests.get(img_url, headers=headers, timeout=60)
            if img_res.status_code == 200:
              image = Image.open(BytesIO(img_res.content)).convert("RGB")
              image = image.resize((720, 1280))

              # 자막 합성 (6등분 기준 5번째 칸 위치: Y 880 ~ 1030, 6번째 맨 아랫칸은 비워둠)
              draw = ImageDraw.Draw(image)
              draw.rounded_rectangle([40, 870, 680, 1040], radius=16, fill=(15, 15, 20))
              draw.rounded_rectangle([40, 870, 680, 1040], radius=16, outline=(60, 130, 246), width=4)

              font = None
              font_paths = [
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                  "malgun.ttf",
                  "DejaVuSans-Bold.ttf"
              ]
              for fp in font_paths:
                try:
                  font = ImageFont.truetype(fp, 44)  # 폰트 크기를 키워서 가독성 확보
                  break
                except:
                  continue
              if font is None:
                font = ImageFont.load_default()

              narration_text = cut["narration"]
              draw.text((70, 925), narration_text, fill=(255, 255, 255), font=font)

              os.makedirs("temp_images", exist_ok=True)
              img_path = f"temp_images/cut_{idx+1}.png"
              image.save(img_path)
              cut["image_path"] = img_path
              cut_success = True
              break
            else:
              time.sleep(3)
          except Exception:
            time.sleep(3)

        progress_bar.progress((idx + 1) / total_cuts)
        # 서버 과부하 및 402 에러 방지를 위해 컷마다 5초간 충분한 여유 대기 시간 부여
        time.sleep(5.0)
      except Exception as e:
        print(f"Cut {idx+1} error: {e}")

    status_text.empty()
    st.success("🎉 모든 컷의 일러스트 이미지와 큼직한 하단 자막 합성이 완료되었습니다!")
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
          with st.spinner("단순 일러스트 스타일로 이미지 생성 및 자막 합성 중..."):
            try:
              user_prompt = cut["image_prompt"]
              clean_prompt = (
                  f"{user_prompt}, vertical 9:16 aspect ratio, simple flat vector"
                  " illustration, minimalist cartoon style, clean vector art,"
                  " vibrant colors, no photorealistic, no text, no words, no letters"
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
              for attempt in range(4):
                img_res = requests.get(img_url, headers=headers, timeout=60)
                if img_res.status_code == 200:
                  image = Image.open(BytesIO(img_res.content)).convert("RGB")
                  image = image.resize((720, 1280))

                  draw = ImageDraw.Draw(image)
                  draw.rounded_rectangle([40, 870, 680, 1040], radius=16, fill=(15, 15, 20))
                  draw.rounded_rectangle([40, 870, 680, 1040], radius=16, outline=(60, 130, 246), width=4)

                  font = None
                  font_paths = [
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      "malgun.ttf",
                      "DejaVuSans-Bold.ttf"
                  ]
                  for fp in font_paths:
                    try:
                      font = ImageFont.truetype(fp, 44)
                      break
                    except:
                      continue
                  if font is None:
                    font = ImageFont.load_default()

                  narration_text = cut["narration"]
                  draw.text((70, 925), narration_text, fill=(255, 255, 255), font=font)

                  os.makedirs("temp_images", exist_ok=True)
                  img_path = f"temp_images/cut_{i+1}.png"
                  image.save(img_path)
                  cut["image_path"] = img_path
                  success = True
                  break
                else:
                  time.sleep(3)

              if success:
                st.success(f"컷 {i+1} 일러스트 이미지 생성 및 자막 합성 성공!")
              else:
                st.error("이미지 서버 혼잡. 3초 뒤 개별 생성 버튼을 다시 눌러주세요.")
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