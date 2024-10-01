import random
import simpy
import statistics
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

def run_simulation():
    """
    Функция для запуска симуляции контакт-центра с динамическим переключением между
    базовыми и упрощёнными нейросетевыми агентами, используя управление доступностью агентов.
    QoE вычисляется как функция от типа модели и времени ожидания.
    """
    # Параметры симуляции
    SIM_TIME = 1000  # Продолжительность симуляции (единицы времени)
    NUM_AGENTS_FULL = 10  # Количество агентов при использовании базовых моделей
    NUM_AGENTS_SIMPLIFIED = 20  # Количество агентов при использовании упрощённых моделей
    AVG_PROCESSING_TIME = 1  # Среднее время обработки запроса (единицы времени)
    QUEUE_THRESHOLD_TO_BASE = 0  # Порог для переключения на базовые агенты
    QoE_FULL_BASE = 1.0  # Базовое QoE при использовании базовых моделей
    QoE_SIMPLIFIED_BASE = 0.8  # Базовое QoE при использовании упрощённых моделей
    ALPHA = 0.05  # Коэффициент влияния задержки на QoE

    # Уровни нагрузки для симуляции
    arrival_rates = [0.1 * i for i in range(1, 10)] + list(range(1, 21))  # От 0.1 до 20

    # Значения порога для переключения на упрощённые агенты
    queue_thresholds = [1, 3, 5, 7, 10]  # Можно изменить или добавить значения

    # Хранилища для результатов по всем порогам
    results_waiting_times = {}  # Ключ: порог, Значение: список средних задержек
    results_qoe_values = {}  # Ключ: порог, Значение: список средних QoE
    results_simplified_agents = {}  # Ключ: порог, Значение: список средних дополнительных агентов

    # Основной цикл по значениям порога
    for QUEUE_THRESHOLD_TO_SIMP in queue_thresholds:
        # Хранилища для результатов текущего порога
        average_waiting_times = []
        average_qoe_values = []
        simplified_agent_counts = []

        print(f"\nСимуляция для QUEUE_THRESHOLD_TO_SIMP = {QUEUE_THRESHOLD_TO_SIMP}\n")

        # Цикл по уровням нагрузки
        for REQUEST_ARRIVAL_RATE in arrival_rates:
            # Инициализация метрик для текущей нагрузки
            qoe_values = []
            waiting_times = []
            time_points = []
            simplified_agent_counts_over_time = []
            time_qoe = []
            qoe_over_time = []

            # Создание среды симуляции
            env = simpy.Environment()

            # Начальные значения
            agent_type = 'full'  # Текущий тип агентов ('full' или 'simplified')
            busy_agents = 0  # Счётчик занятых агентов
            available_agents = NUM_AGENTS_FULL  # Текущее количество доступных агентов

            # Создание ресурса агентов с максимальной ёмкостью
            agent_resource = simpy.Resource(env, capacity=NUM_AGENTS_SIMPLIFIED)

            # Функция обработки каждого запроса
            def process_request(env, request_id):
                nonlocal busy_agents
                arrival_time = env.now  # Время прибытия запроса

                with agent_resource.request() as req:
                    yield req  # Ожидание доступного агента в очереди ресурса

                    # Ждём, пока будет доступен агент
                    while busy_agents >= available_agents:
                        yield env.timeout(0.01)  # Небольшая пауза перед повторной проверкой

                    busy_agents += 1  # Агент занят

                    waiting_time = env.now - arrival_time  # Время ожидания запроса
                    waiting_times.append(waiting_time)  # Сохранение времени ожидания

                    # Время обработки запроса
                    processing_time = random.expovariate(1.0 / AVG_PROCESSING_TIME)

                    # Определение базового QoE в зависимости от типа агента
                    if agent_type == 'full':
                        base_qoe = QoE_FULL_BASE
                    else:
                        base_qoe = QoE_SIMPLIFIED_BASE

                    # Вычисление QoE с учётом задержки
                    qoe = max(0, base_qoe - ALPHA * waiting_time)  # QoE не может быть отрицательным
                    qoe_values.append(qoe)

                    yield env.timeout(processing_time)  # Обработка запроса

                    busy_agents -= 1  # Агент освободился

            # Функция генерации входящих запросов
            def generate_requests(env):
                request_id = 0
                while True:
                    # Интервал между запросами
                    inter_arrival_time = random.expovariate(REQUEST_ARRIVAL_RATE)
                    yield env.timeout(inter_arrival_time)
                    request_id += 1
                    env.process(process_request(env, request_id))  # Запуск процесса обработки запроса

            # Функция мониторинга длины очереди и переключения типов агентов
            def monitor_queue(env):
                nonlocal agent_type, available_agents
                while True:
                    queue_length = len(agent_resource.queue)  # Текущая длина очереди

                    # Переключение на упрощённые агенты
                    if queue_length > QUEUE_THRESHOLD_TO_SIMP and agent_type != 'simplified':
                        agent_type = 'simplified'
                        available_agents = NUM_AGENTS_SIMPLIFIED  # Увеличиваем доступное количество агентов
                        print(f"Переключение на упрощённые агенты в момент времени {env.now} при нагрузке {REQUEST_ARRIVAL_RATE}")
                    # Переключение обратно на базовые агенты
                    elif (queue_length <= QUEUE_THRESHOLD_TO_BASE and agent_type != 'full' and
                          busy_agents <= NUM_AGENTS_FULL):
                        agent_type = 'full'
                        available_agents = NUM_AGENTS_FULL  # Уменьшаем доступное количество агентов
                        print(f"Переключение на базовые агенты в момент времени {env.now} при нагрузке {REQUEST_ARRIVAL_RATE}")

                    # Сохранение данных для графиков
                    time_points.append(env.now)
                    num_simplified_agents = available_agents - NUM_AGENTS_FULL if agent_type == 'simplified' else 0
                    simplified_agent_counts_over_time.append(num_simplified_agents)

                    yield env.timeout(1)  # Проверка состояния каждые 1 единицу времени

            # Функция мониторинга QoE во времени
            def monitor_qoe(env):
                while True:
                    current_time = env.now
                    current_qoe = sum(qoe_values) / len(qoe_values) if qoe_values else QoE_FULL_BASE
                    time_qoe.append(current_time)
                    qoe_over_time.append(current_qoe)
                    yield env.timeout(1)

            # Запуск процессов симуляции
            env.process(generate_requests(env))
            env.process(monitor_queue(env))
            env.process(monitor_qoe(env))

            # Запуск симуляции до заданного времени
            env.run(until=SIM_TIME)

            # Вычисление средних метрик для текущей нагрузки
            average_qoe = sum(qoe_values) / len(qoe_values) if qoe_values else QoE_FULL_BASE
            average_waiting_time = sum(waiting_times) / len(waiting_times) if waiting_times else 0
            average_simplified_agents = statistics.mean(simplified_agent_counts_over_time) if simplified_agent_counts_over_time else 0

            # Сохранение средних значений
            average_qoe_values.append(average_qoe)
            average_waiting_times.append(average_waiting_time)
            simplified_agent_counts.append(average_simplified_agents)

        # Сохранение результатов для текущего порога
        results_waiting_times[QUEUE_THRESHOLD_TO_SIMP] = average_waiting_times
        results_qoe_values[QUEUE_THRESHOLD_TO_SIMP] = average_qoe_values
        results_simplified_agents[QUEUE_THRESHOLD_TO_SIMP] = simplified_agent_counts

    # Построение графиков по результатам симуляции для разных порогов

    # График 1: Средняя задержка vs Интенсивность нагрузки для разных порогов
    plt.figure()
    for QUEUE_THRESHOLD_TO_SIMP in queue_thresholds:
        plt.plot(arrival_rates, results_waiting_times[QUEUE_THRESHOLD_TO_SIMP], marker='o', label=f'Порог: {QUEUE_THRESHOLD_TO_SIMP}')
    plt.title('Средняя задержка vs Интенсивность нагрузки')
    plt.xlabel('Интенсивность нагрузки')
    plt.ylabel('Средняя задержка')
    plt.legend()
    plt.grid(True)
    plt.show()

    # График 2: Среднее QoE vs Интенсивность нагрузки для разных порогов
    plt.figure()
    for QUEUE_THRESHOLD_TO_SIMP in queue_thresholds:
        plt.plot(arrival_rates, results_qoe_values[QUEUE_THRESHOLD_TO_SIMP], marker='o', label=f'Порог: {QUEUE_THRESHOLD_TO_SIMP}')
    plt.title('Среднее QoE vs Интенсивность нагрузки')
    plt.xlabel('Интенсивность нагрузки')
    plt.ylabel('Среднее QoE')
    plt.legend()
    plt.grid(True)
    plt.show()

    # График 3: Среднее число дополнительных агентов vs Интенсивность нагрузки для разных порогов
    plt.figure()
    for QUEUE_THRESHOLD_TO_SIMP in queue_thresholds:
        plt.plot(arrival_rates, results_simplified_agents[QUEUE_THRESHOLD_TO_SIMP], marker='o', label=f'Порог: {QUEUE_THRESHOLD_TO_SIMP}')
    plt.title('Среднее число дополнительных агентов vs Интенсивность нагрузки')
    plt.xlabel('Интенсивность нагрузки')
    plt.ylabel('Среднее число дополнительных агентов')
    plt.legend()
    plt.grid(True)
    plt.show()

    # Дополнительно: Средняя задержка vs Среднее число дополнительных агентов для разных порогов
    plt.figure()
    for QUEUE_THRESHOLD_TO_SIMP in queue_thresholds:
        plt.plot(results_simplified_agents[QUEUE_THRESHOLD_TO_SIMP], results_waiting_times[QUEUE_THRESHOLD_TO_SIMP], marker='o', label=f'Порог: {QUEUE_THRESHOLD_TO_SIMP}')
    plt.title('Средняя задержка vs Среднее число дополнительных агентов')
    plt.xlabel('Среднее число дополнительных агентов')
    plt.ylabel('Средняя задержка')
    plt.legend()
    plt.grid(True)
    plt.show()

    # График 8: Зависимость QoE и задержки от нагрузки (3D-график) для разных порогов
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    for QUEUE_THRESHOLD_TO_SIMP in queue_thresholds:
        ax.plot(
            arrival_rates,
            results_waiting_times[QUEUE_THRESHOLD_TO_SIMP],
            results_qoe_values[QUEUE_THRESHOLD_TO_SIMP],
            marker='o',
            label=f'Порог: {QUEUE_THRESHOLD_TO_SIMP}'
        )

    ax.set_xlabel('Интенсивность нагрузки')
    ax.set_ylabel('Средняя задержка')
    ax.set_zlabel('Среднее QoE')
    ax.set_title('Зависимость QoE и задержки от нагрузки')
    ax.legend()
    plt.show()

if __name__ == "__main__":
    run_simulation()
