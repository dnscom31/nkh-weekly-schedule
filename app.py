import streamlit as st
import random
import time

# --- 설정 및 상수 ---
st.set_page_config(page_title="Coup: 4-Player Deluxe", layout="wide")

# 고품질 판타지풍 이미지 (Unsplash Source API 활용)
ROLE_IMAGES = {
    "Duke": "https://source.unsplash.com/800x600/?portrait,king,noble",
    "Assassin": "https://source.unsplash.com/800x600/?portrait,assassin,ninja,hood",
    "Captain": "https://source.unsplash.com/800x600/?portrait,knight,soldier,armor",
    "Ambassador": "https://source.unsplash.com/800x600/?portrait,diplomat,merchant",
    "Contessa": "https://source.unsplash.com/800x600/?portrait,queen,lady,noblewoman"
}

ROLE_KOREAN = {
    "Duke": "공작", "Assassin": "암살자", "Captain": "사령관",
    "Ambassador": "대사", "Contessa": "귀부인"
}

ACTIONS = {
    "Income": {"cost": 0, "role": None, "desc": "소득 (+1원, 방어 불가)"},
    "Foreign Aid": {"cost": 0, "role": None, "blockable": True, "block_role": "Duke", "desc": "해외원조 (+2원, 누구나 공작으로 방어 가능)"},
    "Tax": {"cost": 0, "role": "Duke", "desc": "세금징수 (+3원, 공작 능력)"},
    "Steal": {"cost": 0, "role": "Captain", "blockable": True, "block_roles": ["Captain", "Ambassador"], "desc": "갈취 (+2원 뺏기, 사령관/대사로 방어)"},
    "Assassinate": {"cost": 3, "role": "Assassin", "blockable": True, "block_role": "Contessa", "desc": "암살 (코인 3원 소모, 귀부인으로 방어)"},
    "Exchange": {"cost": 0, "role": "Ambassador", "desc": "교환 (카드 2장 뽑아 교체)"},
    "Coup": {"cost": 7, "role": None, "desc": "쿠 (코인 7원 소모, 방어 불가 일격)"},
}

# --- 게임 상태 초기화 ---
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.log = ["게임이 시작되었습니다. 4인 플레이를 준비합니다."]
    st.session_state.phase = "TURN_START" # TURN_START, WAIT_FOR_INTERVENTION, WAIT_FOR_BLOCK_CHALLENGE
    
    # 덱 생성 (각 3장 * 5종류 = 15장)
    deck = []
    for r in list(ROLE_IMAGES.keys()):
        deck.extend([r] * 3)
    random.shuffle(deck)
    st.session_state.deck = deck
    
    # 4명의 플레이어 생성
    st.session_state.players = []
    names = ["나 (Player)", "AI 1 (Alpha)", "AI 2 (Beta)", "AI 3 (Gamma)"]
    for i in range(4):
        st.session_state.players.append({
            "id": i,
            "name": names[i],
            "is_ai": i > 0,
            "coins": 2,
            "cards": [st.session_state.deck.pop(), st.session_state.deck.pop()],
            "alive_cards": [True, True],
            "alive": True
        })
    
    st.session_state.turn_idx = random.randint(0, 3) # 랜덤 시작
    log(f"첫 번째 턴은 '{st.session_state.players[st.session_state.turn_idx]['name']}' 입니다.")
    
    st.session_state.current_action = None # {actor_idx, action_name, target_idx, blocker_idx}

# --- 헬퍼 함수 ---
def log(msg):
    st.session_state.log.insert(0, msg)

def get_current_player():
    return st.session_state.players[st.session_state.turn_idx]

def get_alive_cards(player_idx):
    p = st.session_state.players[player_idx]
    return [c for idx, c in enumerate(p["cards"]) if p["alive_cards"][idx]]

def draw_card():
    if st.session_state.deck: return st.session_state.deck.pop()
    else: return random.choice(list(ROLE_IMAGES.keys())) # 예외 처리

def next_turn():
    # 다음 살아있는 플레이어 찾기
    next_idx = (st.session_state.turn_idx + 1) % 4
    while not st.session_state.players[next_idx]["alive"]:
        next_idx = (next_idx + 1) % 4
    st.session_state.turn_idx = next_idx
    st.session_state.current_action = None
    st.session_state.phase = "TURN_START"
    st.rerun()

def check_game_over():
    alive_players = [p for p in st.session_state.players if p["alive"]]
    if len(alive_players) == 1:
        winner = alive_players[0]
        if winner["is_ai"]:
            st.error(f"게임 종료! 승자는 {winner['name']} 입니다.")
        else:
            st.balloons()
            st.success("축하합니다! 최후의 승자가 되셨습니다!")
        st.stop()

def lose_life(player_idx):
    p = st.session_state.players[player_idx]
    # 살아있는 첫 번째 카드를 제거 (단순화)
    for i in range(2):
        if p["alive_cards"][i]:
            p["alive_cards"][i] = False
            log(f"💀 {p['name']}의 카드 [{ROLE_KOREAN[p['cards'][i]]}] 제거됨!")
            break
    if not any(p["alive_cards"]):
        p["alive"] = False
        log(f"⚰️ {p['name']} 탈락!")
    check_game_over()

# --- AI 로직 ---
def get_ai_target(actor_idx):
    # 살아있는 다른 플레이어 중 랜덤 선택
    targets = [i for i in range(4) if i != actor_idx and st.session_state.players[i]["alive"]]
    return random.choice(targets) if targets else None

def ai_decide_action(ai_idx):
    ai = st.session_state.players[ai_idx]
    hand = get_alive_cards(ai_idx)
    target_idx = get_ai_target(ai_idx)
    
    if ai["coins"] >= 7: return "Coup", target_idx
    if ai["coins"] >= 3 and ("Assassin" in hand or random.random() < 0.3): return "Assassinate", target_idx
    if "Duke" in hand or random.random() < 0.5: return "Tax", None
    if "Captain" in hand and target_idx is not None: return "Steal", target_idx
    return ("Foreign Aid", None) if random.random() < 0.6 else ("Income", None)

def ai_should_intervene(ai_idx):
    """AI가 다른 사람의 행동에 도전하거나 방해할지 결정"""
    ai = st.session_state.players[ai_idx]
    act = st.session_state.current_action
    actor = st.session_state.players[act['actor_idx']]
    action_name = act['action_name']
    
    # 1. 도전(Challenge) 여부
    needed_role = ACTIONS[action_name]["role"]
    if needed_role:
        # 내 손에 그 카드가 2장 있으면 100% 도전
        if get_alive_cards(ai_idx).count(needed_role) == 2:
            return "Challenge"
        # 10% 확률로 블러핑 의심
        if random.random() < 0.1:
            return "Challenge"
            
    # 2. 방해(Block) 여부
    # 내가 타겟일 때 (암살, 갈취)
    if act['target_idx'] == ai_idx:
        if action_name == "Assassinate":
            # 귀부인 있거나, 없어도 50% 확률로 방어 시도
            if "Contessa" in get_alive_cards(ai_idx) or random.random() < 0.5: return "Block"
        if action_name == "Steal":
            # 사령관/대사 있거나, 없어도 30% 방어 시도
            hand = get_alive_cards(ai_idx)
            if "Captain" in hand or "Ambassador" in hand or random.random() < 0.3: return "Block"
            
    # 해외 원조는 누구나 방해 가능 (공작 있는 척)
    if action_name == "Foreign Aid":
        # 공작 있거나, 없어도 20% 확률로 방해 시도
        if "Duke" in get_alive_cards(ai_idx) or random.random() < 0.2: return "Block"
        
    return None

def ai_should_challenge_block(ai_idx):
    """누군가 행동을 방해했을 때, AI가 그 방어에 도전할지 결정"""
    # 20% 확률로 도전
    return random.random() < 0.2

# --- 액션 실행 로직 ---
def execute_final_action():
    act = st.session_state.current_action
    actor = st.session_state.players[act['actor_idx']]
    target = st.session_state.players[act['target_idx']] if act['target_idx'] is not None else None
    action_name = act['action_name']
    
    # 비용 지불
    actor["coins"] -= ACTIONS[action_name]["cost"]
    log(f"✅ {actor['name']}의 [{ACTIONS[action_name]['desc'].split(' ')[0]}] 성공!")

    if action_name == "Income": actor["coins"] += 1
    elif action_name == "Foreign Aid": actor["coins"] += 2
    elif action_name == "Tax": actor["coins"] += 3
    elif action_name == "Steal":
        steal_amount = min(2, target["coins"])
        target["coins"] -= steal_amount
        actor["coins"] += steal_amount
        log(f"{steal_amount}원을 뺏었습니다.")
    elif action_name in ["Assassinate", "Coup"]:
        lose_life(target["id"])
    elif action_name == "Exchange":
        # 4인용 자동 교환 로직
        new_cards = [draw_card(), draw_card()]
        current_hand = get_alive_cards(actor["id"])
        pool = current_hand + new_cards
        random.shuffle(pool)
        lives = sum(actor["alive_cards"])
        keep = pool[:lives]
        st.session_state.deck.extend(pool[lives:])
        random.shuffle(st.session_state.deck)
        alive_idx = 0
        for i in range(2):
            if actor["alive_cards"][i]:
                actor["cards"][i] = keep[alive_idx]
                alive_idx += 1
        log(f"{actor['name']}가 카드를 교환했습니다.")
    
    next_turn()

def resolve_challenge(challenger_idx, target_idx, role_claimed):
    challenger = st.session_state.players[challenger_idx]
    target = st.session_state.players[target_idx]
    target_hand = get_alive_cards(target_idx)
    
    if role_claimed in target_hand:
        log(f"🛡️ {target['name']} 인증 성공! ({ROLE_KOREAN[role_claimed]})")
        log(f"❌ {challenger['name']} 도전 실패! 패널티 적용.")
        lose_life(challenger_idx)
        # 인증한 카드 덱에 넣고 교체
        st.session_state.deck.append(role_claimed)
        random.shuffle(st.session_state.deck)
        for i in range(2):
            if target["alive_cards"][i] and target["cards"][i] == role_claimed:
                target["cards"][i] = draw_card()
                break
        return True # 인증 성공
    else:
        log(f"🤥 {target['name']} 블러핑 적발! ({ROLE_KOREAN[role_claimed]} 없음)")
        log(f"⚔️ {challenger['name']} 도전 성공!")
        lose_life(target_idx)
        return False # 인증 실패

# --- UI 렌더링 (4인 레이아웃) ---
# 상단: AI 1, 2, 3 표시
ai_cols = st.columns(3)
for i in range(1, 4):
    p = st.session_state.players[i]
    with ai_cols[i-1]:
        if p["alive"]:
            st.subheader(f"🤖 {p['name']}")
            st.metric("💰 코인", p["coins"])
            c_cols = st.columns(2)
            for j in range(2):
                with c_cols[j]:
                    if p["alive_cards"][j]:
                        st.info("뒷면")
                    else:
                        st.image(ROLE_IMAGES[p["cards"][j]], caption=f"❌ {ROLE_KOREAN[p['cards'][j]]}", width=60)
        else:
             st.subheader(f"⚰️ {p['name']} (탈락)")

st.divider()

# 중앙: 게임 상황 및 내 정보
mid_col1, mid_col2 = st.columns([2, 1])
with mid_col1:
    # 내 정보 표시
    me = st.session_state.players[0]
    if me["alive"]:
        st.subheader(f"👤 {me['name']} (나)")
        st.metric("💰 코인", me["coins"])
        c_cols = st.columns(2)
        for j in range(2):
            with c_cols[j]:
                card = me["cards"][j]
                alive = me["alive_cards"][j]
                st.image(ROLE_IMAGES[card], caption=f"{'' if alive else '❌'} {ROLE_KOREAN[card]}", width=100, 
                         use_column_width=False, output_format="PNG") # 이미지 품질 위해 PNG 지정
    else:
        st.error("당신은 탈락했습니다. 관전 모드입니다.")

with mid_col2:
    st.header("📜 게임 로그")
    log_container = st.container(height=300)
    for msg in st.session_state.log:
        log_container.text(msg)
    
    if st.session_state.current_action:
        act = st.session_state.current_action
        actor_name = st.session_state.players[act['actor_idx']]['name']
        action_desc = ACTIONS[act['action_name']]['desc'].split(' ')[0]
        target_msg = f" -> {st.session_state.players[act['target_idx']]['name']}" if act['target_idx'] is not None else ""
        st.info(f"📢 현재: {actor_name}가 [{action_desc}]{target_msg} 선언!")

st.divider()
st.header("🎮 게임 컨트롤")

# === 게임 메인 루프 ===

curr_p = get_current_player()

# 1. 턴 시작: 행동 선택 (플레이어 or AI)
if st.session_state.phase == "TURN_START":
    if curr_p["id"] == 0 and curr_p["alive"]: # 내 턴
        st.subheader("⚡ 당신의 차례입니다. 행동을 선택하세요.")
        
        if curr_p["coins"] >= 10:
            st.warning("코인이 10개 이상입니다. 쿠를 강제합니다.")
            target_idx = st.selectbox("쿠 대상 선택", [i for i in range(1,4) if st.session_state.players[i]["alive"]], format_func=lambda x: st.session_state.players[x]['name'])
            if st.button("Coup (쿠) 실행"):
                st.session_state.current_action = {"actor_idx": 0, "action_name": "Coup", "target_idx": target_idx, "blocker_idx": None}
                execute_final_action() # 쿠는 방어 불가
        else:
            # 행동 버튼들
            col1, col2, col3, col4 = st.columns(4)
            if col1.button("소득 (+1)"): 
                st.session_state.current_action = {"actor_idx": 0, "action_name": "Income", "target_idx": None, "blocker_idx": None}
                st.session_state.phase = "WAIT_FOR_INTERVENTION"
                st.rerun()
            if col2.button("해외원조 (+2)"):
                st.session_state.current_action = {"actor_idx": 0, "action_name": "Foreign Aid", "target_idx": None, "blocker_idx": None}
                st.session_state.phase = "WAIT_FOR_INTERVENTION"
                st.rerun()
            if col3.button("세금징수 (+3, 공작)"):
                st.session_state.current_action = {"actor_idx": 0, "action_name": "Tax", "target_idx": None, "blocker_idx": None}
                st.session_state.phase = "WAIT_FOR_INTERVENTION"
                st.rerun()
            if col4.button("교환 (카드변경, 대사)"):
                st.session_state.current_action = {"actor_idx": 0, "action_name": "Exchange", "target_idx": None, "blocker_idx": None}
                st.session_state.phase = "WAIT_FOR_INTERVENTION"
                st.rerun()
                
            col5, col6, col7 = st.columns(3)
            targets = [i for i in range(1,4) if st.session_state.players[i]["alive"]]
            target_idx = st.selectbox("대상 선택 (갈취/암살/쿠)", targets, format_func=lambda x: st.session_state.players[x]['name']) if targets else None

            if col5.button("갈취 (+2뺏기, 사령관)"):
                if target_idx:
                    st.session_state.current_action = {"actor_idx": 0, "action_name": "Steal", "target_idx": target_idx, "blocker_idx": None}
                    st.session_state.phase = "WAIT_FOR_INTERVENTION"
                    st.rerun()
            if col6.button("암살 (-3코인, 암살자)"):
                if curr_p["coins"] >=3 and target_idx:
                    st.session_state.current_action = {"actor_idx": 0, "action_name": "Assassinate", "target_idx": target_idx, "blocker_idx": None}
                    st.session_state.phase = "WAIT_FOR_INTERVENTION"
                    st.rerun()
            if col7.button("쿠 (-7코인)"):
                if curr_p["coins"] >=7 and target_idx:
                    st.session_state.current_action = {"actor_idx": 0, "action_name": "Coup", "target_idx": target_idx, "blocker_idx": None}
                    execute_final_action()

    elif curr_p["is_ai"] and curr_p["alive"]: # AI 턴
        with st.spinner(f"{curr_p['name']}가 생각 중..."):
            time.sleep(1)
            act_name, target_idx = ai_decide_action(curr_p["id"])
            st.session_state.current_action = {"actor_idx": curr_p["id"], "action_name": act_name, "target_idx": target_idx, "blocker_idx": None}
            
            if act_name in ["Coup", "Income"]: # 개입 불가 행동
                execute_final_action()
            else:
                st.session_state.phase = "WAIT_FOR_INTERVENTION"
                st.rerun()
    elif not curr_p["alive"]:
        next_turn()

# 2. 개입 대기 단계 (도전 또는 방해)
if st.session_state.phase == "WAIT_FOR_INTERVENTION":
    act = st.session_state.current_action
    actor = st.session_state.players[act['actor_idx']]
    act_info = ACTIONS[act['action_name']]
    
    # 2-1. AI들의 개입 결정 처리 (순차적)
    ai_intervened = False
    for i in range(1, 4):
        ai_p = st.session_state.players[i]
        if ai_p["alive"] and ai_p["id"] != act['actor_idx']:
            decision = ai_should_intervene(i)
            if decision == "Challenge":
                st.warning(f"🚨 {ai_p['name']}가 도전을 외쳤습니다!")
                if resolve_challenge(i, act['actor_idx'], act_info['role']): # 인증 성공
                    execute_final_action()
                else: # 인증 실패 (행동 취소)
                    next_turn()
                ai_intervened = True; break
            elif decision == "Block":
                st.warning(f"🛡️ {ai_p['name']}가 방해를 선언했습니다!")
                act['blocker_idx'] = i
                st.session_state.phase = "WAIT_FOR_BLOCK_CHALLENGE"
                st.rerun()
                ai_intervened = True; break
    
    # 2-2. 플레이어(나)의 개입 기회 (AI가 아무도 개입 안 했을 때)
    if not ai_intervened and st.session_state.players[0]["alive"] and act['actor_idx'] != 0:
        st.subheader("행동에 개입하시겠습니까?")
        col1, col2, col3 = st.columns(3)
        
        if col1.button("허용하기"):
            execute_final_action()
            
        # 도전 버튼
        if act_info['role'] and col2.button("도전하기 (블러핑 의심)"):
            if resolve_challenge(0, act['actor_idx'], act_info['role']):
                 execute_final_action()
            else:
                 next_turn()
                 
        # 방해 버튼 (조건 충족 시)
        can_block = False
        block_role_needed = None
        if act_info.get('blockable'):
            if act_info.get('block_role') == "Duke": # 해외원조는 누구나 방해 가능
                can_block = True
                block_role_needed = "Duke"
            elif act['target_idx'] == 0: # 내가 타겟일 때
                can_block = True
                block_role_needed = act_info.get('block_role') or act_info.get('block_roles')[0] # 단순화

        if can_block and col3.button(f"방해하기 ({ROLE_KOREAN[block_role_needed]} 주장)"):
            act['blocker_idx'] = 0
            st.session_state.phase = "WAIT_FOR_BLOCK_CHALLENGE"
            st.rerun()
            
    elif not ai_intervened and (not st.session_state.players[0]["alive"] or act['actor_idx'] == 0):
        # 나도 개입할 수 없는 상황이면 바로 실행
        execute_final_action()

# 3. 방해에 대한 도전 대기 단계
if st.session_state.phase == "WAIT_FOR_BLOCK_CHALLENGE":
    act = st.session_state.current_action
    blocker = st.session_state.players[act['blocker_idx']]
    act_info = ACTIONS[act['action_name']]
    
    # 방어에 필요한 역할 결정
    block_role_claimed = ""
    if act['action_name'] == "Foreign Aid": block_role_claimed = "Duke"
    elif act['action_name'] == "Assassinate": block_role_claimed = "Contessa"
    elif act['action_name'] == "Steal": block_role_claimed = "Captain" # 단순화

    st.info(f"🛡️ {blocker['name']}가 {ROLE_KOREAN[block_role_claimed]} 자격으로 행동을 막았습니다.")

    # 3-1. 플레이어가 행동자일 때 -> 방해자에게 도전할지 결정
    if act['actor_idx'] == 0 and st.session_state.players[0]["alive"]:
        st.subheader("당신의 행동이 막혔습니다. 방해자에게 도전하시겠습니까?")
        c1, c2 = st.columns(2)
        if c1.button("도전하기 (거짓 방어다!)"):
            if resolve_challenge(0, act['blocker_idx'], block_role_claimed): # 방어 인증 성공
                next_turn() # 행동 막힘
            else: # 방어 거짓 -> 행동 실행
                execute_final_action()
        if c2.button("인정하기 (방어 허용)"):
            log("방어를 인정했습니다. 행동이 취소됩니다.")
            next_turn()

    # 3-2. AI가 행동자일 때 -> AI가 도전할지 결정
    elif st.session_state.players[act['actor_idx']]["is_ai"]:
        with st.spinner("AI가 대응을 고민 중..."):
            time.sleep(1)
            if ai_should_challenge_block(act['actor_idx']):
                 st.warning(f"🚨 {st.session_state.players[act['actor_idx']]['name']}가 방어에 도전했습니다!")
                 if resolve_challenge(act['actor_idx'], act['blocker_idx'], block_role_claimed):
                     next_turn()
                 else:
                     execute_final_action()
            else:
                 log("AI가 방어를 인정했습니다.")
                 next_turn()
    else:
        # 내가 관전자거나 관련 없는 제3자면 그냥 넘어감
        next_turn()
