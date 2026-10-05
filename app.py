# @title app.py
import numpy as np
import pandas as pd
import streamlit as st

from models import Building, Floor, DispatchStrategy, DoorType, TrafficScenario
from logic.simulation import run_simulation

st.set_page_config(page_title="Симуляция лифтов", layout="wide")
st.title("Симуляция лифтов — исходные данные и прогон")

def default_floors():
    rows = [
        {"floor": -1, "height": 3.0, "population": 0, "entry_percent": 10},
        {"floor": 1, "height": 4.0, "population": 0, "entry_percent": 90},
    ]
    for fn in range(2, 19):
        rows.append({"floor": fn, "height": 3.5, "population": 12,
                     "entry_percent": 0})
    rows.append({"floor": 19, "height": 3.5, "population": 12,
                 "entry_percent": 0})
    rows.append({"floor": 20, "height": 3.5, "population": 8,
                 "entry_percent": 0})
    return pd.DataFrame(rows)

with st.sidebar:
    st.header("Здание")
    building_name = st.text_input("Название", "Жилой дом, 20 этажей")

    st.header("Лифты")
    num_elevators = st.slider("Количество лифтов", 1, 8, 4)
    capacity = st.slider("Вместимость кабины, чел", 1, 20, 10)
    home_floor = st.number_input("Этаж парковки", -5, 30, 1)

    with st.expander("Кинематика"):
        speed = st.slider("Номинальная скорость, м/с", 0.5, 6.0, 2.5, 0.1)
        accel = st.slider("Ускорение, м/с²", 0.3, 2.0, 1.2, 0.05)
        jerk = st.slider("Рывок, м/с³", 0.5, 3.0, 2.0, 0.1)
        motor_delay = st.slider("Задержка пуска двигателя, с", 0.0, 2.0, 0.2, 0.05)

    with st.expander("Двери"):
        door_type = st.selectbox("Тип дверей", list(DoorType))
        door_width = st.select_slider("Ширина проёма, мм",
                                      options=list(range(500, 1250, 50)),
                                      value=900)
        start_delay = st.slider("Задержка перед стартом, с", 0.5, 5.0, 1.5, 0.1)
        door_close_delay = st.slider("Задержка перед закрытием, с",
                                     1.0, 10.0, 3.0, 0.5)
        max_door_reopens = st.slider("Переоткрытий дверей за стоянку", 0, 3, 1,
            help="Сколько раз новый вызов с этажа может переоткрыть "
                 "двери. 0 — функция выключена")

    st.header("Трафик")
    rate_coef = st.slider("Коэффициент интенсивности", 0.01, 0.30, 0.06, 0.01)
    scenario = st.selectbox("Сценарий", list(TrafficScenario))

    st.header("Диспетчеризация")
    strategy = st.selectbox("Стратегия",
                            [DispatchStrategy.NC, DispatchStrategy.DDS])
    re_dispatch_threshold = st.slider("Порог переназначения вызова, с",
                                      10, 120, 30, 5)

    st.header("Прогон")
    sim_minutes = st.slider("Длительность, мин", 1, 120, 30)
    seed = st.number_input("Seed", 0, 10**6, 42)

st.subheader("Этажи здания")

if "floors_df" not in st.session_state:
    st.session_state.floors_df = default_floors()

floors_df = st.data_editor(
    st.session_state.floors_df,
    column_config={
        "floor": st.column_config.NumberColumn("Этаж", step=1),
        "height": st.column_config.NumberColumn("Высота, м",
                                                min_value=2.0, max_value=8.0,
                                                step=0.1),
        "population": st.column_config.NumberColumn("Заселённость, чел",
                                                    min_value=0, max_value=200,
                                                    step=1),
        "entry_percent": st.column_config.NumberColumn("Вход/выход, %",
                                                       min_value=0,
                                                       max_value=100, step=5),
    },
    num_rows="dynamic", use_container_width=True, key="floors_editor",
)
st.session_state.floors_df = floors_df

cfg = dict(
    name=building_name,
    floors=floors_df.to_dict("records"),
    num_elevators=num_elevators, capacity=capacity, home_floor=home_floor,
    speed=speed, accel=accel, jerk=jerk, motor_delay=motor_delay,
    door_type=door_type, door_width=door_width,
    start_delay=start_delay, door_close_delay=door_close_delay,
    max_door_reopens=max_door_reopens,
    rate_coef=rate_coef, scenario=scenario,
    strategy=strategy, re_dispatch_threshold=re_dispatch_threshold,
    duration=int(sim_minutes * 60), seed=int(seed),
)

if st.button("▶ Запустить симуляцию", type="primary"):
    errors = []
    fnums = [int(r["floor"]) for r in cfg["floors"]]
    if len(fnums) != len(set(fnums)):
        errors.append("В таблице есть дубликаты номеров этажей.")
    if len(fnums) < 2:
        errors.append("Нужно минимум два этажа.")
    if not any(r["entry_percent"] > 0 for r in cfg["floors"]):
        errors.append("Нет ни одного этажа с «вход/выход».")
    if errors:
        for e in errors:
            st.error(e)
        st.stop()
    with st.spinner("Симуляция выполняется…"):
        st.session_state.results = run_simulation(cfg)
        st.session_state.cfg_used = cfg

res = st.session_state.get("results")
if res is None:
    st.info("Задайте параметры и нажмите «Запустить симуляцию».")
    st.stop()

stats, elevators, building, kin = res

st.subheader(f"Результаты: {building.name}")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Перевезено пассажиров", getattr(stats, "delivered", 0))
m2.metric("Сгенерировано", getattr(stats, "generated", 0))
m3.metric("Среднее ожидание, с", f"{getattr(stats, 'avg_wait_time', 0):.1f}")
m4.metric("Средняя поездка, с", f"{getattr(stats, 'avg_ride_time', 0):.1f}")

m5, m6, m7 = st.columns(3)
m5.metric("Остановок", getattr(stats, "stops", 0))
m6.metric("Переоткрытий дверей", getattr(stats, "door_reopens", 0))
m7.metric("Максимальная очередь",
          max((f.count() for f in building.all_floors()), default=0))

st.subheader("Итоговое состояние лифтов")
st.dataframe(pd.DataFrame([{
    "Лифт": e.name, "Этаж": e.current_floor,
    "Состояние": e.state.value, "В кабине, чел": len(e.pax),
} for e in elevators]), use_container_width=True, hide_index=True)
