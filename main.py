
import streamlit as st
import pandas as pd
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==========================================
# 1. 기본 설정
# ==========================================

st.set_page_config(
    page_title="민주적 점심",
    page_icon="🍱",
    layout="centered"
)

# 한국 시간 기준
KST = ZoneInfo("Asia/Seoul")

# 투표할 수 있는 메뉴
MENUS = [
    "샐러드",
    "샌드위치",
    "마라탕",
    "떡볶이",
    "치킨",
    "피자",
    "찜닭"
]

# 구글 시트 웹 앱 주소를 비밀 금고에서 가져오기
try:
    SHEET_URL = st.secrets["SHEET_URL"]
except (KeyError, FileNotFoundError):
    st.error("비밀 금고에 SHEET_URL을 등록해주세요.")
    st.stop()


# ==========================================
# 2. 구글 시트에서 기록 읽기
# ==========================================

def load_records():
    """구글 시트의 전체 기록을 가져옵니다."""

    try:
        # 파라미터 없이 요청하면 전체 기록이 옵니다.
        response = requests.get(
            SHEET_URL,
            timeout=15
        )
        response.raise_for_status()

        data = response.json()

        # 첫 줄은 머리글이므로 데이터에서 분리합니다.
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError("구글 시트 응답 형식이 올바르지 않습니다.")

        # 머리글만 있으면 빈 데이터프레임을 만듭니다.
        if len(data) == 1:
            return pd.DataFrame(
                columns=["시각", "팀원", "메뉴", "구분"]
            )

        df = pd.DataFrame(
            data[1:],
            columns=data[0]
        )

        # 열 순서를 정확히 맞춥니다.
        df = df[["시각", "팀원", "메뉴", "구분"]].copy()

        # 시각은 이미 한국 시간 문자열이므로
        # 시간대를 변환하지 않고 그대로 해석합니다.
        df["날짜시간"] = pd.to_datetime(
            df["시각"],
            errors="coerce"
        )

        return df

    except Exception as e:
        st.error(f"구글 시트 기록을 불러오지 못했어요: {e}")
        st.stop()


# ==========================================
# 3. 구글 시트에 기록 저장하기
# ==========================================

def save_record(member, menu, record_type):
    """투표 또는 식사 기록을 저장합니다."""

    if record_type not in ["먹고싶다", "먹었다"]:
        st.error("올바르지 않은 기록 유형입니다.")
        return False

    # 한글이 깨지지 않도록 params를 사용합니다.
    params = {
        "member": member,
        "menu": menu,
        "type": record_type
    }

    try:
        response = requests.get(
            SHEET_URL,
            params=params,
            timeout=15
        )
        response.raise_for_status()

        return True

    except requests.RequestException as e:
        st.error(f"저장하지 못했어요: {e}")
        return False


# ==========================================
# 4. 오늘 날짜와 최근 7일 계산
# ==========================================

now = datetime.now(KST)
today = now.date()

# 오늘을 포함해 최근 7일
seven_days_ago = today - timedelta(days=6)


# ==========================================
# 5. 화면 제목
# ==========================================

st.title("🍱 민주적 점심")

st.write(
    "오늘 점심은 혼자 고민하지 말아요! "
    "우리 팀의 소중한 한 표로 메뉴를 정해봐요. 😊"
)

st.divider()


# ==========================================
# 6. 투표 화면
# ==========================================

st.subheader("🗳️ 오늘 점심에 한 표!")

member = st.text_input(
    "이름을 알려주세요",
    placeholder="예: 수연"
)

selected_menu = st.selectbox(
    "오늘 어떤 메뉴가 당기세요?",
    MENUS
)

if st.button(
    "🙋 이 메뉴에 한 표",
    use_container_width=True,
    type="primary"
):

    if not member.strip():
        st.warning("투표하려면 이름을 입력해주세요!")

    else:
        success = save_record(
            member=member.strip(),
            menu=selected_menu,
            record_type="먹고싶다"
        )

        if success:
            st.success(
                f"{member.strip()}님의 '{selected_menu}' "
                "투표가 접수됐어요!"
            )
            st.rerun()


st.caption(
    "💡 마음이 바뀌셨나요? 다시 투표해도 괜찮아요. "
    "가장 마지막 표만 반영됩니다."
)

st.divider()


# ==========================================
# 7. 구글 시트 기록 불러오기
# ==========================================

df = load_records()

# 기록이 아예 없는 경우
if df.empty:

    st.info(
        "아직 기록이 없어요! "
        "첫 번째 투표의 주인공이 되어주세요. 🌱"
    )

    st.stop()


# 날짜 계산을 위한 열 만들기
df["날짜"] = df["날짜시간"].dt.date


# ==========================================
# 8. 오늘 투표 집계
# ==========================================

# 오늘의 '먹고싶다' 기록만 선택
today_votes = df[
    (df["날짜"] == today) &
    (df["구분"] == "먹고싶다")
].copy()

# 같은 사람이 여러 번 투표했으면
# 구글 시트에서 가장 마지막에 저장된 표만 인정합니다.
# 따라서 시트의 원래 행 순서를 유지합니다.
today_votes = today_votes.drop_duplicates(
    subset=["팀원"],
    keep="last"
)

# 메뉴별 득표 수 계산
vote_counts = (
    today_votes["메뉴"]
    .value_counts()
    .reindex(MENUS, fill_value=0)
)

# 투표를 받은 메뉴만 따로 정리
vote_result = vote_counts[
    vote_counts > 0
].reset_index()

vote_result.columns = ["메뉴", "득표 수"]


# ==========================================
# 9. 당선 메뉴 발표
# ==========================================

st.subheader("🏆 오늘의 점심 당선 메뉴")

if today_votes.empty:

    st.info(
        "아직 오늘의 투표가 없어요. "
        "첫 표를 기다리고 있어요! 🍽️"
    )

else:

    # 가장 많은 표를 받은 메뉴
    max_votes = vote_counts.max()

    # 동점 메뉴도 모두 확인
    winners = vote_counts[
        vote_counts == max_votes
    ].index.tolist()

    if len(winners) == 1:

        winner = winners[0]

        st.markdown(
            f"""
            <div style="
                text-align:center;
                background-color:#FFF4E5;
                padding:28px;
                border-radius:18px;
                border:2px solid #FFD6A5;
                color:#3D2C1E;
            ">
                <div style="font-size:20px;">
                    🎉 오늘의 선택 🎉
                </div>
                <div style="
                    font-size:42px;
                    font-weight:bold;
                    margin:14px 0;
                ">
                    {winner}
                </div>
                <div style="font-size:18px;">
                    총 {max_votes}표로 당선!
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.write("")

        # ==================================
        # 10. 최근 7일 중 같은 메뉴를 먹었는지 확인
        # ==================================

        eaten_records = df[
            (df["구분"] == "먹었다") &
            (df["메뉴"] == winner) &
            (df["날짜"] >= seven_days_ago) &
            (df["날짜"] <= today)
        ].copy()

        if not eaten_records.empty:

            # 가장 최근에 먹은 날짜
            last_eaten = eaten_records["날짜"].max()

            # 실제로 며칠 전인지 계산
            days_ago = (today - last_eaten).days

            st.warning(
                f"🤭 그 메뉴, {days_ago}일 전에도 "
                "드셨는데 괜찮으시겠어요?"
            )

        else:
            st.success(
                "✨ 최근 7일 동안 먹은 기록이 없는 메뉴예요! "
                "오늘 맛있게 드세요."
            )

        # ==================================
        # 11. 먹었다 버튼
        # ==================================

        st.write("")

        if st.button(
            "🍽️ 오늘 이거 먹었다",
            use_container_width=True
        ):

            success = save_record(
                member="우리팀",
                menu=winner,
                record_type="먹었다"
            )

            if success:
                st.success(
                    f"'{winner}' 먹은 기록을 저장했어요! 😋"
                )
                st.rerun()

    else:

        # 동점이면 임의로 당선시키지 않습니다.
        st.warning(
            "🤝 공동 1등이 나왔어요! "
            "아직 당선 메뉴를 정하지 못했어요."
        )

        st.markdown(
            "### 공동 1등: " + ", ".join(winners)
        )

        st.write(
            f"각각 {max_votes}표를 받았어요. "
            "한 표만 더 모아볼까요?"
        )

st.divider()


# ==========================================
# 12. 오늘의 득표 현황
# ==========================================

st.subheader("📊 오늘의 득표 현황")

if today_votes.empty:

    st.info("아직 집계할 투표가 없어요.")

else:

    st.dataframe(
        vote_result,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        f"오늘 참여한 팀원: {len(today_votes)}명 "
        "(중복 투표 제외)"
    )


st.divider()


# ==========================================
# 13. 최근 7일 동안 먹은 기록
# ==========================================

st.subheader("📅 최근 7일 동안 먹은 메뉴")

recent_eaten = df[
    (df["구분"] == "먹었다") &
    (df["날짜"] >= seven_days_ago) &
    (df["날짜"] <= today)
].copy()

if recent_eaten.empty:

    st.info(
        "최근 7일 동안 먹은 기록이 없어요. "
        "오늘부터 하나씩 기록해봐요! 🌷"
    )

else:

    # 최신 기록부터 보여줍니다.
    recent_eaten = recent_eaten.sort_values(
        by="날짜시간",
        ascending=False
    )

    # 시각 문자열은 원본 그대로 보여줍니다.
    st.dataframe(
        recent_eaten[
            ["시각", "팀원", "메뉴"]
        ],
        use_container_width=True,
        hide_index=True
    )


# ==========================================
# 14. 화면 아래 안내
# ==========================================

st.divider()

st.caption(
    "🍀 민주적 점심 | "
    "오늘도 맛있는 한 끼 되세요!"
)
