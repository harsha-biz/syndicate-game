import streamlit as st
import random
import pandas as pd
import altair as alt

# ==========================================
# 1. UI & CSS STYLING
# ==========================================
def inject_custom_css():
    st.markdown("""
        <style>
        .ledger-success {background-color: #d1e7dd; color: #0f5132; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #badbcc;}
        .ledger-fail {background-color: #f8d7da; color: #842029; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #f5c2c7;}
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. GLOBAL GAME STATE MANAGEMENT
# ==========================================
class GameState:
    def __init__(self):
        self.round = 1
        self.max_rounds = 8
        self.game_over = False
        self.vault_names = ["Vault A", "Vault B", "Vault C"] 
        self.roles_available = ["Mastermind", "Detective", "Associate", "Associate", "Associate"]
        self.host_pin = "host123"
        self.player_pins = {1: "p1", 2: "p2", 3: "p3", 4: "p4", 5: "p5"}
        self.players = {
            i: {
                "name": f"Player {i}",
                "role": "Associate",
                "cash": 30.0,
                "invest_choice": None,
                "sabotage_choice": None,
                "inbox": [],
                "unread": 0,
                "total_sabotages": 0,
                "bankrupt_warning": False
            } for i in range(1, 6)
        }
        self.history = []
        self.wealth_history = {i: [30.0] for i in range(1, 6)} 
        self.host_script = "Welcome to the Syndicate. Read the Dossier. Negotiate your positions. Round 1 begins."

@st.cache_resource
def get_state(): return GameState()
state = get_state()

# ==========================================
# 3. GAME LOGIC & RESOLUTION
# ==========================================
def assign_random_roles():
    roles = state.roles_available.copy()
    random.shuffle(roles)
    for i in range(1, 6): state.players[i]["role"] = roles[i-1]

def get_player_title(cash):
    if cash <= 10.0: return "🐀 Liability"
    elif cash <= 30.0: return "💼 Associate"
    elif cash <= 60.0: return "🤝 Senior Partner"
    else: return "👑 Underboss"

def render_wealth_chart():
    chart_data = pd.DataFrame(state.wealth_history)
    chart_data.rename(columns={i: state.players[i]['name'] for i in range(1, 6)}, inplace=True)
    chart_data['Round'] = chart_data.index
    melted = chart_data.melt('Round', var_name='Player', value_name='Wealth')
    
    base = alt.Chart(melted).encode(x=alt.X('Round:O', title='Round'), y=alt.Y('Wealth:Q', title='Wealth (₹ Lakhs)'), color='Player:N')
    line = base.mark_line(point=True)
    text = base.mark_text(align='left', baseline='bottom', dx=5, dy=-5, fontSize=12).encode(text='Wealth:Q')
    return (line + text).properties(height=400)

def resolve_round():
    vault_data = {v: {"investors": [], "sabotages": 0, "pool": 0} for v in state.vault_names}
    player_snapshot = {}
    
    for pid, pdata in state.players.items():
        inv, sab = pdata["invest_choice"], pdata["sabotage_choice"]
        player_snapshot[pid] = {"name": pdata["name"], "role": pdata["role"], "invest_choice": inv, "sabotage_choice": sab, "vault_payout": 0, "bonus_income": 0, "net_change": 0}
        
        if inv in state.vault_names:
            vault_data[inv]["investors"].append(pid)
            vault_data[inv]["pool"] += 10.0
            state.players[pid]["cash"] -= 10.0
        if sab in state.vault_names:
            vault_data[sab]["sabotages"] += 1
            state.players[pid]["total_sabotages"] += 1 

    round_results = {}
    mastermind_bonus = 0
    total_sabotages = sum(v["sabotages"] for v in vault_data.values())

    for v_name, v_info in vault_data.items():
        base_chance, penalty = 90, 25 * v_info["sabotages"] 
        success_chance = max(10, base_chance - penalty)
        success = random.randint(1, 100) <= success_chance
        
        if success:
            multiplier = random.choice([1.5, 2.0, 2.5])
            payout = (v_info["pool"] * multiplier) / len(v_info["investors"]) if v_info["investors"] else 0
            for pid in v_info["investors"]:
                state.players[pid]["cash"] += payout
                player_snapshot[pid]["vault_payout"] = payout
            round_results[v_name] = {"status": "SUCCESS", "multiplier": multiplier, "sabs": v_info["sabotages"], "payout": payout}
        else:
            round_results[v_name] = {"status": "FAILED", "multiplier": 0, "sabs": v_info["sabotages"], "payout": 0}
            mastermind_bonus += 10.0 
            
    for pid, pdata in state.players.items():
        bonus = mastermind_bonus if pdata["role"] == "Mastermind" else 0
        state.players[pid]["cash"] += (10.0 + bonus)
        if bonus > 0: player_snapshot[pid]["bonus_income"] += bonus
            
        net = 10.0 + player_snapshot[pid]["vault_payout"] + bonus
        if player_snapshot[pid]["invest_choice"] in state.vault_names: net -= 10.0
        player_snapshot[pid]["net_change"] = net
        
        if pdata["role"] == "Detective":
            state.players[pid]["inbox"].append(f"🕵️‍♂️ SYSTEM CLUE: There were exactly {total_sabotages} sabotages total in Round {state.round}.")
            state.players[pid]["unread"] += 1

        if state.players[pid]["cash"] <= 0:
            state.players[pid]["cash"] = 10.0
            state.players[pid]["bankrupt_warning"] = True

        state.wealth_history[pid].append(state.players[pid]["cash"])
        state.players[pid]["invest_choice"] = None
        state.players[pid]["sabotage_choice"] = None

    state.history.append({"round": state.round, "results": round_results, "players": player_snapshot})
    succeeded = len([v for v, d in round_results.items() if d["status"] == "SUCCESS"])
    if succeeded == 3: state.host_script = f"Round {state.round-1} conclusion: Flawless execution. All three vaults cracked."
    elif succeeded == 0: state.host_script = f"Round {state.round-1} conclusion: A bloodbath. All vaults compromised. Total loss."
    else: state.host_script = f"Round {state.round-1} conclusion: Mixed outcomes. Trust is fracturing."

    if state.round >= state.max_rounds: state.game_over = True
    else: state.round += 1

# ==========================================
# 4. ENDGAME LEADERBOARD
# ==========================================
def leaderboard_view(player_id=None):
    ranked_players = sorted(state.players.items(), key=lambda x: (x[1]['cash'], -x[1]['total_sabotages']), reverse=True)
    top_cash, top_sabs = ranked_players[0][1]['cash'], ranked_players[0][1]['total_sabotages']
    winners = [pid for pid, p in ranked_players if p['cash'] == top_cash and p['total_sabotages'] == top_sabs]
    
    if player_id is not None:
        if player_id in winners:
            if state.players[player_id]['role'] == "Mastermind":
                st.error("### 🩸 THE PERFECT CRIME. You played them for fools and burned the city to the ground. The Syndicate is yours.")
                st.balloons()
            else:
                st.success("### 👑 YOU ARE CHOSEN. You survived the bloodbath. Step into my office. You are the new Right Hand.")
                st.snow()
        else:
            winner_names = " and ".join([state.players[w]['name'] for w in winners])
            st.warning(f"### ❌ YOU FAILED. You lacked the killer instinct. The streets belong to {winner_names} now. Kiss the ring or pack your bags.")

    st.title("🚨 THE DUST SETTLES: ENDGAME RESULTS 🚨")
    st.divider()
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📊 Final Rankings")
        final_table = [{"Rank": f"#{i+1}", "Player": p["name"], "Role": p["role"], "Cash": f"₹{p['cash']:,.1f} Lakhs", "Sabs": p["total_sabotages"]} for i, (pid, p) in enumerate(ranked_players)]
        st.dataframe(pd.DataFrame(final_table), use_container_width=True, hide_index=True)

    with col2:
        st.subheader("📈 Final Wealth Trajectories")
        st.altair_chart(render_wealth_chart(), use_container_width=True)

# ==========================================
# 5. HOST VIEW
# ==========================================
def host_view():
    if state.game_over:
        leaderboard_view()
        return

    st.title("🏦 Host Dashboard")
    st.info(f"**🗣️ Read to players:**\n\n{state.host_script}")
    
    ready_count = sum(1 for p in state.players.values() if p["invest_choice"] and p["sabotage_choice"])
    col1, col2 = st.columns([2, 1])
    with col1: 
        st.header(f"Current Round: {state.round} / {state.max_rounds}")
        st.progress(ready_count / 5.0, text=f"Associates Ready: {ready_count} / 5")
    with col2: 
        if st.button("🔄 Force Global Sync", use_container_width=True): st.rerun()

    st.sidebar.header("⚙️ Game Controls")
    if ready_count == 5:
        if st.sidebar.button("🚨 RESOLVE ROUND 🚨", type="primary", use_container_width=True):
            resolve_round()
            st.rerun()
    else:
        st.sidebar.warning(f"Waiting for {5 - ready_count} players to lock in.")

    with st.sidebar.expander("🎭 1. Setup & Roles"):
        if st.button("Shuffle Roles"): assign_random_roles()
        for i in range(1, 6):
            new_name = st.text_input(f"P{i} Name", value=state.players[i]["name"], key=f"n_{i}")
            if new_name: state.players[i]["name"] = new_name

    with st.sidebar.expander("✉️ 2. Send Secret Message"):
        target = st.selectbox("Select Player", range(1, 6), format_func=lambda x: state.players[x]["name"])
        msg = st.text_area("Message to Player")
        if st.button("Send as Host"):
            state.players[target]["inbox"].append(f"👑 FROM HOST: {msg}")
            state.players[target]["unread"] += 1
            st.success("Message Sent!")

    with st.sidebar.expander("🔑 3. Manage Access PINs"):
        for i in range(1, 6):
            new_pin = st.text_input(f"{state.players[i]['name']} PIN", value=state.player_pins[i], key=f"pin_{i}")
            if new_pin: state.player_pins[i] = new_pin

    st.sidebar.divider()
    with st.sidebar.expander("⚠️ DANGER ZONE: Hard Reset"):
        reset_pin = st.text_input("Enter Host PIN to confirm:", type="password", key="reset")
        if st.button("🚨 CONFIRM HARD RESET", use_container_width=True):
            if reset_pin == state.host_pin:
                st.cache_resource.clear()
                st.session_state.logged_in_user = None
                st.rerun()
            elif reset_pin != "": st.error("Invalid PIN.")

    st.subheader("👁️ Live Player Actions")
    player_data = [{"Name": p["name"], "Role": p["role"], "Cash": f"₹{p['cash']:,.1f} Lakhs", "Invested In": p["invest_choice"] or "⏳ Waiting", "Sabotaging": p["sabotage_choice"] or "⏳ Waiting"} for p in state.players.values()]
    st.dataframe(pd.DataFrame(player_data), use_container_width=True)

    st.subheader("📈 Live Wealth Analytics")
    st.altair_chart(render_wealth_chart(), use_container_width=True)

    st.divider()
    st.subheader("📜 Historical Round Data")
    if state.history:
        round_options = [f"Round {h['round']}" for h in state.history]
        selected_str = st.selectbox("Select Past Round", reversed(round_options))
        r_num = int(selected_str.split(" ")[1])
        r_data = next(h for h in state.history if h['round'] == r_num)
        
        res = r_data['results']
        cols = st.columns(3)
        for idx, v in enumerate(state.vault_names):
            with cols[idx]:
                if res[v]["status"] == "SUCCESS": st.success(f"**{v}**\n\n✅ SUCCESS\n\nSabs: **{res[v]['sabs']}**\n\nMulti: {res[v]['multiplier']}x\n\nPayout: ₹{res[v]['payout']:,.1f} Lakhs")
                else: st.error(f"**{v}**\n\n❌ FAILED\n\nSabs: **{res[v]['sabs']}**\n\nLost")
        
        hist_table = [{"Name": p["name"], "Role": p["role"], "Invested In": p["invest_choice"] or "Hold Cash", "Sabotaged": p["sabotage_choice"] or "None", "Vault Payout": f"₹{p['vault_payout']:,.1f} Lakhs", "Net Change": f"{'+' if p['net_change'] >= 0 else ''}₹{p['net_change']:,.1f} Lakhs"} for p in r_data['players'].values()]
        st.dataframe(pd.DataFrame(hist_table), use_container_width=True, hide_index=True)

# ==========================================
# 6. PLAYER VIEW
# ==========================================
def player_view(player_id):
    if state.game_over:
        leaderboard_view(player_id)
        return

    pdata = state.players[player_id]
    
    st.markdown(f"## 👤 {pdata['name']} | Status: {get_player_title(pdata['cash'])}")
    
    if pdata.get("bankrupt_warning"):
        st.error("🩸 **BANKRUPTCY AVERTED:** You lost everything. The Syndicate has fronted you ₹10 Lakhs to stay in the game. Do not embarrass us again.")
        state.players[player_id]["bankrupt_warning"] = False

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Liquid Assets", f"₹{pdata['cash']:,.1f} Lakhs")
    c2.metric("⏱️ Active Round", f"{state.round} / {state.max_rounds}")
    with c3:
        if st.button("📡 Ping Server", use_container_width=True): st.rerun()

    with st.expander("👁️ Reveal Encrypted Identity"):
        st.info(f"Your hidden role is: **{pdata['role']}**")

    st.divider()
    comms_name = f"📡 Comms 🔴 ({pdata['unread']})" if pdata["unread"] > 0 else "📡 Comms"
    tab_action, tab_comms, tab_ledger, tab_dossier = st.tabs(["⚡ Terminal", comms_name, "📜 Ledger", "📁 Dossier"])

    with tab_action:
        if pdata["invest_choice"] and pdata["sabotage_choice"]:
            st.success("✅ Protocol locked. Awaiting Syndicate resolution.")
        else:
            if pdata["role"] == "Mastermind": st.write("### 🩸 Select your targets, Boss. The bank is ready to wire your failure bonuses.")
            elif pdata["role"] == "Detective": st.write("### 🕵️‍♂️ Lock in your moves. Wiretaps are active for post-round sabotage data.")
            else: st.write("### 💼 Lock in your market positions.")
            
            with st.form("action_form"):
                col_inv, col_sab = st.columns(2)
                with col_inv: invest = st.radio("💰 1. Investment (Costs ₹10 Lakhs)", ["🏦 Vault A", "🏦 Vault B", "🏦 Vault C", "💵 Hold Cash"])
                with col_sab: sabotage = st.radio("🧨 2. Sabotage (Free)", ["🛑 None", "🧨 Vault A", "🧨 Vault B", "🧨 Vault C"])
                
                if st.form_submit_button("🔒 Execute Directives", type="primary", use_container_width=True):
                    state.players[player_id]["invest_choice"] = invest.replace("🏦 ", "").replace("💵 ", "")
                    state.players[player_id]["sabotage_choice"] = sabotage.replace("🧨 ", "").replace("🛑 ", "")
                    st.rerun()

    with tab_comms:
        c_inbox, c_send = st.columns(2)
        with c_inbox:
            st.subheader("📥 Inbox")
            ik = f"inbox_{player_id}"
            if ik not in st.session_state: st.session_state[ik] = False
            def toggle(): 
                st.session_state[ik] = not st.session_state[ik]
                if st.session_state[ik]: state.players[player_id]["unread"] = 0 
            st.button("🙈 Hide" if st.session_state[ik] else "👁️ Reveal", on_click=toggle, use_container_width=True)

            if st.session_state[ik]:
                st.markdown("<br>", unsafe_allow_html=True)
                for m in reversed(pdata["inbox"]): st.info(m)
            else: st.caption("Messages hidden to prevent shoulder-surfing.")

        with c_send:
            st.subheader("📤 Transmit")
            st.caption("Cost: ₹1.0 Lakhs per message")
            target_id = st.selectbox("Recipient", [i for i in range(1, 6) if i != player_id], format_func=lambda x: state.players[x]['name'])
            msg_text = st.text_input("Payload:")
            if st.button("Send (-₹1L)"):
                if pdata["cash"] >= 1.0:
                    state.players[player_id]["cash"] -= 1.0
                    state.players[target_id]["inbox"].append(f"📩 From {pdata['name']}: {msg_text}")
                    state.players[target_id]["unread"] += 1
                    st.success("Transmitted!")
                else: st.error("Insufficient liquidity.")

    with tab_ledger:
        st.markdown("### 📜 Market Report")
        for h in reversed(state.history):
            with st.expander(f"Round {h['round']} Audit", expanded=(h['round'] == state.round - 1)):
                cols = st.columns(3)
                for idx, v in enumerate(state.vault_names):
                    res = h['results'][v]
                    with cols[idx]:
                        if res["status"] == "SUCCESS": st.markdown(f'<div class="ledger-success"><h3>{v}</h3><b>✅ CRACKED</b><br><br>Multi: <b>{res["multiplier"]}x</b><br>Payout: <b>₹{res["payout"]:,.1f}L</b></div>', unsafe_allow_html=True)
                        else: st.markdown(f'<div class="ledger-fail"><h3>{v}</h3><b>❌ COMPROMISED</b><br><br>Investments<br><b>LOST</b></div>', unsafe_allow_html=True)

    with tab_dossier:
        st.markdown("""
        ### 📜 Letter from the Don
        I am giving you 8 rounds to prove your worth. Silence is death; you must negotiate, build trust, and deceive to survive.
        
        * **The Goal:** End the game with the highest net worth. Only one player walks away as the winner.
        * **The Income:** You passively receive ₹10 Lakhs at the end of every round just for surviving.
        * **The Investment:** You may invest ₹10 Lakhs into Vault A, B, or C. If the heist succeeds, the total pool is multiplied (1.5x, 2.0x, or 2.5x) and split evenly among the investors. If it fails, you lose your investment. You can also choose to 'Hold Cash' to keep your money completely safe.
        * **The Sabotage:** You can secretly plant explosives on any vault for free. Each sabotage drops that vault's success rate by 25% (from a starting base of 90%).
        * **Hidden Roles:** You all have a secret identity. Most of you are 'Associates' trying to make money. However, one of you is the **Mastermind**, who receives a secret ₹10 Lakhs bonus for *every* vault that fails. Another is the **Detective**, who receives a secret message each round revealing exactly how many total sabotages were planted.
        * **Secure Comms:** Use your encrypted messaging to form private cartels, extort rivals, or coordinate attacks. Each message costs ₹1.0 Lakh.
        
        Trust no one. Form a cartel. Make me rich.
        """)

# ==========================================
# 7. ROUTING
# ==========================================
def main():
    st.set_page_config(page_title="The Syndicate", layout="wide", page_icon="🏦")
    inject_custom_css()
    if "logged_in_user" not in st.session_state: st.session_state.logged_in_user = None

    if st.session_state.logged_in_user is not None:
        if st.sidebar.button("🚪 Log Out Terminal"):
            st.session_state.logged_in_user = None
            st.rerun()

    if st.session_state.logged_in_user is None:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        _, center, _ = st.columns([1, 2, 1])
        with center:
            with st.form("login_form", border=True):
                st.markdown("<h2 style='text-align: center; margin-top: 0;'>🏦 The Syndicate Network</h2>", unsafe_allow_html=True)
                pin_input = st.text_input("Clearance PIN", type="password", placeholder="Enter PIN here...")
                if st.form_submit_button("Authenticate", type="primary", use_container_width=True):
                    if pin_input == state.host_pin: st.session_state.logged_in_user = "HOST"; st.rerun()
                    else:
                        for pid, pin in state.player_pins.items():
                            if pin_input == pin: st.session_state.logged_in_user = pid; st.rerun()
                        if st.session_state.logged_in_user is None: st.error("Access Denied.")
                
    elif st.session_state.logged_in_user == "HOST": host_view()
    else: player_view(st.session_state.logged_in_user)

if __name__ == "__main__": main()