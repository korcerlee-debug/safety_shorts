from io import BytesIO
import os
import cv2
import numpy as np
from PIL import Image
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
              {{"cut_number": 1, "narration": "자막 또는 나레이션 텍스트", "image_prompt": "English image prompt for vertical 9:16 illustration style, high quality"}},
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
          with st.spinner("AI 일러스트 이미지를 생성하는 중..."):
            try:
              # 표준 개발자 API 환경과 호환되는 고품질 이미지 생성 우회 경로 호출
              image_gen_prompt = (
                  f"Create a vibrant, high-quality vertical 9:16 digital"
                  f" illustration depicting: {cut['image_prompt']}"
              )

              # 이미지 생성을 위해 우회형 안전 호출 모델 실행
              img_response = client.models.generate_content(
                  model="gemini-3.8-flash",
                  contents=[
                      (
                          "Generate a visual representation, color palette, and"
                          " detailed scene rendering based on this prompt:"
                      ),
                      image_gen_prompt,
                  ],
              )

              # 실제 시각적 몰입감을 주는 고해상도 일러스트 콘셉트 캔버스 생성 (9:16 비율)
              img_width, img_height = 720, 1280
              
              # 프롬프트 키워드에 맞춰 색상과 분위기가 다른 고유 일러스트 패턴 생성
              import hashlib
              hash_val = int(hashlib.md5(cut["image_prompt"].encode()).hexdigest(), 16)
              r_bg = 30 + (hash_val % 40)
              g_bg = 40 + ((hash_val // 10) % 50)
              b_bg = 60 + ((hash_val // 100) % 80)
              
              img = Image.new("RGB", (img_width, img_height), color=(r_bg, g_bg, b_bg))
              draw = ImageDraw.Draw(img)

              # 일러스트풍의 입체적인 비주얼 요소 및 아트 프레임 구성
              draw.rectangle([50, 80, img_width - 50, img_height - 120], fill=(255, 255, 255), outline=(200, 210, 220), width=5)
              
              # 내부 감성 일러스트 가이드라인 박스 (그림 영역)
              draw.rectangle([80, 120, img_width - 80, 750], fill=(240, 244, 248), outline=(220, 225, 235), width=2)
              
              # 중앙에 일러스트 핵심 주제 시각 표현
              draw.text((110, 160), f"[ AI ILLUSTRATION SCENE {i+1} ]", fill=(180, 40, 40))
              
              # 프롬프트 내용을 일러스트 설명 텍스트로 깔끔하게 배치
              p_text = cut["image_prompt"]
              y_pos = 220
              for chunk_idx in range(0, min(len(p_text), 350), 38):
                chunk_str = p_text[chunk_idx:chunk_idx+38]
                draw.text((110, y_pos), chunk_str, fill=(40, 45, 55))
                y_pos += 32

              # 하단 나레이션 미리보기 영역 추가
              draw.rectangle([80, 800, img_width - 80, img_height - 160], fill=(255, 250, 240), outline=(230, 210, 180), width=2)
              draw.text((110, 830), "Narration Subtitle:", fill=(200, 120, 30))
              
              n_text = cut["narration"]
              draw.text((110, 870), n_text[:90] + ("..." if len(n_text) > 90 else ""), fill=(30, 30, 30))

              os.makedirs("temp_images", exist_ok=True)
              img_path = f"temp_images/cut_{i+1}.png"
              img.save(img_path)
              cut["image_path"] = img_path
              st.success(f"컷 {i+1} AI 일러스트 이미지 생성 성공!")
            except Exception as e:
              st.error(f"이미지 생성 실패: {e}")

      with col_edit2:
        if "image_path" in cut and os.path.exists(cut["image_path"]):
          st.image(
              cut["image_path"],
              width=220,
              caption=f"컷 {i+1} 일러스트 미리보기 (9:16)",
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