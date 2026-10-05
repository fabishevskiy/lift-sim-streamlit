import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

# ---------- Настройка страницы ----------
st.set_page_config(
    page_title="Диспетчерская: Лифтовый трафик",
    page_icon="🏙️",
    layout="wide",
)

st.title("🏙️ Диспетчерская: симуляция лифтового трафика")
st.caption("Панель для оценки пассажиропотока и времени ожидания. Данные — расчётные (демо-режим).")

# ---------- Боковая панель: параметры ----------
with st.sidebar:
    st.subheader("🛠️ Параметры здания")

    building_type = st.selectbox(
        "Тип объекта",
        ["Жилой дом", "Офисный центр", "Торговый центр", "Гостиница"],
        index=0,
        help="Тип влияет на профиль пассажиропотока (пики утром/вечером, равномерность).",
    )

    col_f, col_h = st.columns([2, 1])
    with col_f:
        num_floors = st.slider("Этажность", 5, 50, 15)
    with col_h:
        floor_height = st.number_input("Высота этажа, м", 2.5, 4.5, 3.0, step=0.1)

    st.divider()

    st.subheader("👥 Нагрузка и трафик")

    occupancy_rate = st.slider(
        "Заполняемость, %", 10, 100, 75, step=5,
        help="Процент фактической загрузки здания. Влияет на интенсивность вызовов.",
    )

    num_elevators = st.slider("Количество лифтов", 1, 8, 2)

    duration_hours = st.slider(
        "Длительность симуляции, ч", 1, 48, 4,
        help="Модельное время работы системы. Для быстрой проверки ставьте 1–4 часа.",
    )

    st.divider()
    run_btn = st.button("🚀 Запустить расчёт", type="primary", use_container_width=True)


# ---------- Логика симуляции ----------
@st.cache_data(ttl=300)
def run_simulation(building_type, num_floors, floor_height, occupancy_rate, num_elevators, duration_hours):
    """Демо-расчёт. Позже здесь подключим полноценную модель на SimPy."""
    base_wait = 35
    peak_multiplier = 1.0
    if building_type == "Офисный центр":
        peak_multiplier = 1.3
    elif building_type == "Торговый центр":
        peak_multiplier = 1.1
    elif building_type == "Гостиница":
        peak_multiplier = 0.9

    # Больше лифтов — меньше ожидание (демо-логика с убывающей отдачей)
    elevator_factor = 2.0 / (1 + (num_elevators - 1) * 0.4)

    avg_wait = base_wait * peak_multiplier * elevator_factor * (100 / occupancy_rate)
    max_load = min(99.0, 60 + occupancy_rate * 0.4 - (num_elevators - 1) * 5)
    served_passengers = int(num_floors * occupancy_rate * 1.2 * duration_hours)
    peak_flow = int(served_passengers * 1.1)

    # Распределение потока по этажам: чем ниже этаж, тем больше трафик
    flow_by_floor = []
    for i in range(num_floors):
        weight = max(1.0, (num_floors - i) / num_floors)
        flow = int((occupancy_rate / 100) * 20 * weight * duration_hours)
        flow_by_floor.append(flow)

    # Суточный профиль нагрузки (24 часа)
    daily_profile = []
    for hour in range(24):
        morning = 2.2 * (2.718 ** -((hour - 8.5) ** 2) / 2)   # утренний пик ~8:30
        evening = 1.8 * (2.718 ** -((hour - 18.5) ** 2) / 2)  # вечерний пик ~18:30
        base = 0.5
        daily_profile.append(round((base + morning + evening) * peak_multiplier * 30))

    return {
        "avg_wait": round(avg_wait, 1),
        "max_load": round(max_load, 1),
        "served_passengers": served_passengers,
        "peak_flow": peak_flow,
        "flow_by_floor": flow_by_floor,
        "daily_profile": daily_profile,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }


# ---------- Основная область ----------
if run_btn:
    with st.spinner("🔄 Выполняется расчёт параметров движения..."):
        results = run_simulation(
            building_type, num_floors, floor_height,
            occupancy_rate, num_elevators, duration_hours
        )

    st.success(f"✅ Расчёт завершён ({results['timestamp']})")
    st.divider()

    # --- KPI ---
    st.subheader("📊 Ключевые показатели эффективности")

    cols = st.columns(4)
    cols[0].metric("Среднее ожидание", f"{results['avg_wait']} сек")
    cols[1].metric(
        "Макс. загрузка лифта", f"{results['max_load']}%",
        help="Если больше 85% — требуется оптимизация парка лифтов.",
    )
    cols[2].metric("Обслужено пассажиров", f"{results['served_passengers']:,}")
    cols[3].metric("Пиковая нагрузка", f"{results['peak_flow']} чел/ч")

    # --- Статус системы ---
    if results["max_load"] > 85:
        st.error("🚨 Высокая нагрузка: рекомендуем увеличить количество лифтов или оптимизировать маршрутизацию.")
    elif results["max_load"] > 70:
        st.warning("⚠️ Норма, но близко к пределу. Следите за пиковыми часами.")
    else:
        st.success("🟢 Система в норме.")

    st.divider()

    # --- График 1: поток по этажам ---
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("🗺️ Трафик по этажам")
        colors = ["#2ecc71" if v < 10 else "#f1c40f" if v < 20 else "#e74c3c" for v in results["flow_by_floor"]]
        fig_flow = go.Figure()
        fig_flow.add_bar(
            x=[f"Эт. {i + 1}" for i in range(num_floors)],
            y=results["flow_by_floor"],
            marker_color=colors,
            text=results["flow_by_floor"],
            textposition="outside",
        )
        fig_flow.update_layout(
            title="Пассажиропоток по этажам, чел/ч",
            xaxis_title="Этаж",
            yaxis_title="Пассажиры/час",
            height=450,
            hovermode="x unified",
        )
        st.plotly_chart(fig_flow, use_container_width=True)

    with col2:
        st.subheader("⚠️ Сводка")
        st.markdown(f"**Тип объекта:** {building_type}")
        st.markdown(f"**Этажей:** {num_floors}")
        st.markdown(f"**Высота этажа:** {floor_height} м")
        st.markdown(f"**Лифтов:** {num_elevators}")
        st.markdown(f"**Заполняемость:** {occupancy_rate}%")
        st.markdown(f"**Модельное время:** {duration_hours} ч")

    st.divider()

    # --- График 2: суточный профиль ---
    st.subheader("📈 Суточный профиль нагрузки")
    fig_daily = go.Figure()
    fig_daily.add_bar(x=list(range(24)), y=results["daily_profile"], marker_color="#5b8def")
    fig_daily.update_layout(
        title="Интенсивность вызовов по часам суток",
        xaxis_title="Час",
        yaxis_title="Вызовы/час",
        height=350,
    )
    st.plotly_chart(fig_daily, use_container_width=True)

    st.divider()

    # --- Скачивание отчёта ---
    df_floor = pd.DataFrame({
        "Этаж": range(1, num_floors + 1),
        "Пассажиропоток, чел/ч": results["flow_by_floor"],
    })
    csv = df_floor.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Скачать отчёт по этажам (CSV)",
        data=csv,
        file_name="lift_traffic_report.csv",
        mime="text/csv",
    )

else:
    st.info("👋 Настройте параметры в боковой панели и нажмите «Запустить расчёт».")
