import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Text, Tuple

from rasa_sdk import Action, Tracker
from rasa_sdk.events import AllSlotsReset, FollowupAction, SlotSet
from rasa_sdk.executor import CollectingDispatcher


# ---------------------------------------------------------------------------
# Question text & examples
# ---------------------------------------------------------------------------

QUESTION_TEXT: Dict[str, str] = {
    "utter_ask_name": "Как вас зовут?",
    "utter_ask_experience": "Сколько лет у вас опыта в IT или сфере данных?",
    "utter_ask_role": "Какая позиция вас интересует?",
    # Data Scientist
    "utter_ask_ds_ml_experience": "Расскажите об опыте разработки ML-моделей.",
    "utter_ask_ds_task_types": "Какие типы ML-задач решали? (классификация, регрессия, NLP, CV и т.д.)",
    "utter_ask_ds_feature_engineering": "Работали ли с feature engineering? Приведите пример.",
    "utter_ask_ds_validation": "Как валидировали модели? Какие метрики использовали?",
    "utter_ask_ds_ab_testing": "Есть ли опыт A/B тестирования?",
    "utter_ask_ds_llm": "Работали ли с LLM или генеративными моделями?",
    "utter_ask_ds_inference_opt": "Есть ли опыт оптимизации inference (latency, memory)?",
    "utter_ask_ds_python_level": "Какой у вас уровень Python? (начальный / средний / продвинутый)",
    "utter_ask_ds_frameworks": "Какие ML-фреймворки использовали?",
    "utter_ask_ds_production": "Был ли опыт вывода ML-моделей в production?",
    # Data Engineer
    "utter_ask_de_pipeline": "Опишите опыт с ETL/ELT пайплайнами.",
    "utter_ask_de_data_volumes": "С какими объёмами данных работали? (GB/TB/PB)",
    "utter_ask_de_batch_streaming": "Работали ли с batch и/или streaming обработкой?",
    "utter_ask_de_kafka_spark": "Есть ли опыт Kafka или Spark?",
    "utter_ask_de_warehouse": "Работали ли с Data Warehouse (Snowflake, BigQuery, Redshift и т.д.)?",
    "utter_ask_de_sql_optimization": "Оптимизировали ли сложные SQL-запросы? Опыт оконных функций?",
    "utter_ask_de_orchestration": "Какие оркестраторы использовали (Airflow, Prefect, Dagster)?",
    "utter_ask_de_monitoring": "Как обеспечивали мониторинг качества данных?",
    "utter_ask_de_tools": "Какие инструменты использовали?",
    "utter_ask_de_cloud": "Есть ли опыт с облачными платформами?",
    "utter_ask_de_sql": "Как оцените свой уровень SQL?",
    # Data Analyst
    "utter_ask_da_domain": "В каких предметных областях работали аналитиком?",
    "utter_ask_da_product_metrics": "Строили ли продуктовые метрики? Какие?",
    "utter_ask_da_ab_tests": "Есть ли опыт A/B тестирования или статистических тестов?",
    "utter_ask_da_funnel_cohort": "Работали ли с funnel или cohort analysis?",
    "utter_ask_da_bi": "Какие BI-инструменты используете? Строили ли дашборды для stakeholders?",
    "utter_ask_da_stakeholders": "Как взаимодействовали со стейкхолдерами? Переводили бизнес-задачу в аналитическую?",
    "utter_ask_da_product_thinking": "Приведите пример, когда аналитика помогла принять продуктовое решение.",
    "utter_ask_da_viz": "Какие инструменты визуализации используете?",
    "utter_ask_da_sql": "Оцените свой уровень SQL: базовый, средний или продвинутый?",
    # Project Manager
    "utter_ask_pm_team_size": "Какой максимальный размер команды вы координировали?",
    "utter_ask_pm_methodology": "Какие методологии применяли?",
    "utter_ask_pm_ml_understanding": "Как оцените своё понимание ML-проектов и их специфики?",
    "utter_ask_pm_risk_management": "Как управляли рисками на проектах?",
    "utter_ask_pm_budget": "Был ли у вас budget ownership? Каков был бюджет?",
    "utter_ask_pm_conflict": "Приведите пример разрешения конфликта в команде.",
    "utter_ask_pm_delivery": "Расскажите о проекте, за delivery которого вы несли полную ответственность.",
    "utter_ask_pm_distributed_team": "Работали ли с распределёнными или кросс-функциональными командами?",
    "utter_ask_pm_ai_ml_projects": "Есть ли опыт управления AI/ML проектами?",
    # MLOps Engineer
    "utter_ask_mlops_cicd": "Есть ли опыт CI/CD для ML-проектов?",
    "utter_ask_mlops_tools": "Какие MLOps-инструменты знаете?",
    "utter_ask_mlops_monitoring": "Есть ли опыт мониторинга моделей?",
    "utter_ask_mlops_kubernetes": "Есть ли опыт работы с Kubernetes?",
    "utter_ask_mlops_model_registry": "Работали ли с model registry (MLflow, DVC, Neptune)?",
    "utter_ask_mlops_docker": "Используете ли Docker в ML-пайплайнах?",
    "utter_ask_mlops_iac": "Есть ли опыт IaC (Terraform, Pulumi)?",
    "utter_ask_mlops_serving": "Как организовывали ML serving (Triton, TorchServe, BentoML и т.д.)?",
    "utter_ask_mlops_gpu": "Есть ли опыт работы с GPU-инфраструктурой?",
    # Common
    "utter_ask_salary": "Какой уровень вознаграждения вас интересует (₽/мес, до вычета налогов)?",
    "utter_low_experience_warning": "Были ли стажировки или учебные проекты?",
}

QUESTION_EXAMPLES: Dict[str, str] = {
    "utter_ask_name": "Меня зовут Иван.",
    "utter_ask_experience": "У меня 3 года опыта.",
    "utter_ask_role": "Data Scientist или кнопкой в списке.",
    "utter_ask_ds_ml_experience": "Делал классификацию оттока в sklearn и CatBoost.",
    "utter_ask_ds_task_types": "Классификация, NLP (sentiment analysis), немного CV.",
    "utter_ask_ds_feature_engineering": "Да, создавал лаговые фичи для временных рядов.",
    "utter_ask_ds_validation": "Cross-validation, ROC-AUC, F1 для классификации.",
    "utter_ask_ds_ab_testing": "Да, проводил A/B тесты с t-test и bootstrap.",
    "utter_ask_ds_llm": "Да, файнтюнил LLaMA для внутреннего чат-бота.",
    "utter_ask_ds_inference_opt": "Квантизировал модели, перешли с FP32 на INT8.",
    "utter_ask_ds_python_level": "Средний уровень Python.",
    "utter_ask_ds_frameworks": "PyTorch, pandas, scikit-learn.",
    "utter_ask_ds_production": "Да, выкатывали через Docker и REST API.",
    "utter_ask_de_pipeline": "ETL в Airflow из Postgres в S3, затем Spark.",
    "utter_ask_de_data_volumes": "Работал с терабайтными датасетами в S3.",
    "utter_ask_de_batch_streaming": "Batch через Airflow, streaming через Kafka + Flink.",
    "utter_ask_de_kafka_spark": "Kafka для event streaming, Spark для batch обработки.",
    "utter_ask_de_warehouse": "BigQuery и dbt для трансформаций.",
    "utter_ask_de_sql_optimization": "Оптимизировал оконные функции, партиционирование.",
    "utter_ask_de_orchestration": "Airflow с DAG'ами для ежедневных пайплайнов.",
    "utter_ask_de_monitoring": "Great Expectations для data quality, алерты в Slack.",
    "utter_ask_de_tools": "Airflow, dbt, Kafka.",
    "utter_ask_de_cloud": "Да, AWS S3 и Glue.",
    "utter_ask_de_sql": "Продвинутый SQL, оконные функции.",
    "utter_ask_da_domain": "E-commerce, метрики конверсии.",
    "utter_ask_da_product_metrics": "DAU, Retention, LTV, conversion rate.",
    "utter_ask_da_ab_tests": "Да, тесты с t-test, считал sample size заранее.",
    "utter_ask_da_funnel_cohort": "Cohort retention в e-commerce, воронки onboarding.",
    "utter_ask_da_bi": "Power BI дашборды для C-level, Tableau для продукта.",
    "utter_ask_da_stakeholders": "Проводил discovery-сессии, формализовал требования.",
    "utter_ask_da_product_thinking": "Анализ оттока показал, что нужен onboarding-тур.",
    "utter_ask_da_viz": "Power BI и иногда Plotly.",
    "utter_ask_da_sql": "Средний уровень SQL.",
    "utter_ask_pm_team_size": "Координировал команду из 8 человек.",
    "utter_ask_pm_methodology": "Scrum с двухнедельными спринтами.",
    "utter_ask_pm_ml_understanding": "Базовое понимание цикла ML.",
    "utter_ask_pm_risk_management": "Risk register, еженедельный review рисков.",
    "utter_ask_pm_budget": "Да, бюджет $200k, ежемесячный burn-rate контроль.",
    "utter_ask_pm_conflict": "Конфликт DS и бизнеса по метрикам — провёл воркшоп.",
    "utter_ask_pm_delivery": "Запустил ML-систему ценообразования за 6 месяцев.",
    "utter_ask_pm_distributed_team": "3 страны, синхронизировались через Jira и Confluence.",
    "utter_ask_pm_ai_ml_projects": "Да, ML-платформа для рекомендаций.",
    "utter_ask_mlops_cicd": "Да, GitHub Actions для обучения и деплоя.",
    "utter_ask_mlops_tools": "MLflow, Kubernetes, Docker.",
    "utter_ask_mlops_monitoring": "Grafana и алерты по дрейфу.",
    "utter_ask_mlops_kubernetes": "Да, деплой моделей в K8s через Helm charts.",
    "utter_ask_mlops_model_registry": "MLflow для версионирования и сравнения моделей.",
    "utter_ask_mlops_docker": "Да, контейнеризировал training и serving пайплайны.",
    "utter_ask_mlops_iac": "Terraform для AWS инфраструктуры.",
    "utter_ask_mlops_serving": "Triton Inference Server для high-load serving.",
    "utter_ask_mlops_gpu": "Настраивал GPU-кластер на AWS EC2 p3 instances.",
    "utter_ask_salary": "150000.",
    "utter_low_experience_warning": "Был курс и pet-проект с Kaggle.",
}


# ---------------------------------------------------------------------------
# Salary benchmarks by role and level (₽/мес gross)
# ---------------------------------------------------------------------------

SALARY_BENCHMARKS: Dict[str, Dict[str, Tuple[int, int]]] = {
    "data_scientist":  {"junior": (80_000, 140_000),  "middle": (150_000, 280_000), "senior": (290_000, 500_000)},
    "data_engineer":   {"junior": (80_000, 140_000),  "middle": (150_000, 270_000), "senior": (280_000, 480_000)},
    "data_analyst":    {"junior": (60_000, 110_000),  "middle": (120_000, 220_000), "senior": (230_000, 380_000)},
    "project_manager": {"junior": (80_000, 130_000),  "middle": (140_000, 260_000), "senior": (270_000, 450_000)},
    "mlops_engineer":  {"junior": (90_000, 150_000),  "middle": (160_000, 300_000), "senior": (310_000, 550_000)},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _latest_text(tracker: Tracker) -> str:
    return (tracker.latest_message.get("text") or "").strip()


def _latest_text_lower(tracker: Tracker) -> str:
    return _latest_text(tracker).lower()


def _intent_name(tracker: Tracker) -> Optional[str]:
    return tracker.latest_message.get("intent", {}).get("name")


def _extract_number(text: str) -> Optional[float]:
    match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _parse_salary_from_raw(raw: str) -> Optional[float]:
    if not raw:
        return None
    raw = raw.strip().lower().replace(" ", "")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*к\b", raw)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(тыс|тысяч)", raw)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000
    m = re.search(r"(\d{4,})", raw)
    if m:
        return float(m.group(1))
    # Last resort: standalone number not glued to letters (e.g. avoid INT8 → 8)
    m = re.search(r"(?<![a-zA-Zа-яёА-ЯЁ])(\d+(?:[.,]\d+)?)(?![a-zA-Zа-яёА-ЯЁ])", raw)
    if m:
        val = float(m.group(1).replace(",", "."))
        if val < 1000:
            return val * 1000
        return val
    return None


def _norm_sql_level(text: str) -> Optional[str]:
    txt = text.lower()
    if any(x in txt for x in ["продвин", "advanced", "эксперт", "оконные", "оптимиз"]):
        return "advanced"
    if any(x in txt for x in ["средн", "intermediate", "join", "подзапрос"]):
        return "intermediate"
    if any(x in txt for x in ["баз", "beginner", "select"]):
        return "beginner"
    return None


def _norm_python_level(text: str) -> Optional[str]:
    txt = text.lower()
    if any(x in txt for x in ["advanced", "продвин", "эксперт", "senior"]):
        return "advanced"
    if any(x in txt for x in ["intermediate", "средн", "middle"]):
        return "intermediate"
    if any(x in txt for x in ["beginner", "начина", "баз"]):
        return "beginner"
    return None


def _norm_bool(text: str) -> Optional[bool]:
    t = text.lower()
    if re.search(r"\bда\b", t) or re.search(r"\bага\b", t) or re.search(r"\bесть\b", t):
        return True
    if re.search(r"\bконечно\b", t) or re.search(r"\bверно\b", t) or re.search(r"\bточно\b", t):
        return True
    if re.search(r"\bподтверждаю\b", t):
        return True
    if re.search(r"\bнет\b", t) or re.search(r"\bнеа\b", t) or re.search(r"\bникогда\b", t):
        return False
    if "не использовал" in t or "не работал" in t or "не настраивал" in t:
        return False
    if "не выводил" in t or "только исслед" in t or "без прода" in t:
        return False
    return None


def _extract_list_from_text(text: str) -> List[str]:
    cleaned = re.sub(r"[.;:!?]", ",", text.lower())
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    return parts[:12]


def _role_interview_stage(role: Optional[str]) -> str:
    return {
        "data_scientist": "interview_ds",
        "data_engineer": "interview_de",
        "data_analyst": "interview_da",
        "project_manager": "interview_pm",
        "mlops_engineer": "interview_mlops",
    }.get(role or "", "collect_role")


def _slot_get(tracker: Tracker, pending: Dict[str, Any], key: Text) -> Any:
    if key in pending:
        return pending[key]
    return tracker.get_slot(key)


def _determine_level(exp_years: float) -> str:
    """Determine candidate level based on experience years."""
    if exp_years < 1.0:
        return "junior"
    if exp_years < 4.0:
        return "middle"
    return "senior"


def _level_display_ru(level: str) -> str:
    return {"junior": "Junior", "middle": "Middle", "senior": "Senior"}.get(level, level)


def _hire_decision_from_score(score: int) -> str:
    if score >= 80:
        return "Strong Hire"
    if score >= 60:
        return "Hire"
    if score >= 40:
        return "Maybe"
    return "Reject"


def _hire_recommendation_ru(decision: str) -> str:
    return {
        "Strong Hire": "Рекомендация: приглашать на следующий этап в приоритетном порядке.",
        "Hire": "Рекомендация: приглашать на следующий этап.",
        "Maybe": "Рекомендация: дополнительное интервью или проверка по сомнительным пунктам.",
        "Reject": "Рекомендация: не продолжать процесс на текущий момент.",
    }.get(decision, "Рекомендация: требуется ручная проверка HR.")


def _ds_production_points(tracker: Tracker) -> Tuple[int, List[str], List[str]]:
    """
    Production experience 0–15 (TZ): нет 0; Docker/API 8; масштабируемый деплой 15.
    """
    strengths: List[str] = []
    weaknesses: List[str] = []
    has_prod = tracker.get_slot("ds_has_production")
    if has_prod is not True:
        weaknesses.append("нет production-опыта")
        return 0, strengths, weaknesses

    ml_exp = str(tracker.get_slot("ds_ml_experience") or "").lower()
    frameworks = tracker.get_slot("ds_frameworks") or []
    fw_t = " ".join(frameworks).lower() if isinstance(frameworks, list) else str(frameworks).lower()
    blob = f"{ml_exp} {fw_t}"

    scalable_kw = [
        "kubernetes", "k8s", "kube", "helm",
        "микросервис", "автомасштаб", "autoscaling", "горизонталь",
        "high load", "высоконагружен", "triton", "torchserve", "seldon", "kserve",
        "distributed", "шард", "реплик",
    ]
    api_kw = ["docker", "контейнер", "rest", "fastapi", "flask", "django", "grpc", "endpoint", "api ", "api.", "сервис"]

    if any(k in blob for k in scalable_kw):
        strengths.append("сильный production / масштабируемый деплой")
        return 15, strengths, weaknesses
    if any(k in blob for k in api_kw):
        strengths.append("production через Docker/API")
        return 8, strengths, weaknesses
    strengths.append("есть production-опыт")
    return 8, strengths, weaknesses


def _apply_level_score_adjustment(
    score: int, level: str, role: Optional[str], tracker: Tracker
) -> int:
    """Корректировка score по уровню: для Junior смягчаем штрафы, для Senior — выше планка."""
    adj = score
    if level == "junior":
        if role == "data_scientist":
            if tracker.get_slot("ds_has_production") is not True:
                adj += 5
            if tracker.get_slot("ds_python_level") == "beginner":
                adj += 4
        if role == "data_engineer" and tracker.get_slot("de_cloud_experience") is not True:
            adj += 3
    elif level == "senior":
        if role == "data_scientist" and tracker.get_slot("ds_has_production") is not True:
            adj -= 10
        if role == "data_engineer" and tracker.get_slot("de_sql_level") != "advanced":
            adj -= 6
        if role == "project_manager" and tracker.get_slot("pm_ml_understanding") == "none":
            adj -= 8
        if role == "mlops_engineer" and tracker.get_slot("mlops_ci_cd") is not True:
            adj -= 8
    return max(0, min(adj, 100))


# ---------------------------------------------------------------------------
# Soft skills scoring
# ---------------------------------------------------------------------------

def _score_soft_skills(tracker: Tracker, role: Optional[str]) -> Tuple[int, List[str], List[str]]:
    """
    Evaluates soft skills based on answer quality signals.
    Returns (score 0-15, strengths, weaknesses).

    Dimensions assessed:
      - Communication clarity  (length + structured vocabulary)
      - Ownership / leadership (first-person action verbs)
      - Business understanding (business/product vocabulary)
    Each dimension is worth 0-5 points → total 0-15.
    """
    score = 0
    strengths: List[str] = []
    weaknesses: List[str] = []

    # Collect all free-text answers relevant to the role
    answer_slots: List[str] = []

    if role == "data_scientist":
        answer_slots = [
            tracker.get_slot("ds_ml_experience") or "",
            tracker.get_slot("ds_task_types") or "",
            tracker.get_slot("ds_feature_engineering") or "",
            tracker.get_slot("ds_validation") or "",
        ]
    elif role == "data_engineer":
        answer_slots = [
            tracker.get_slot("de_pipeline_experience") or "",
            tracker.get_slot("de_monitoring") or "",
            tracker.get_slot("de_orchestration") or "",
        ]
    elif role == "data_analyst":
        answer_slots = [
            tracker.get_slot("da_product_thinking") or "",
            tracker.get_slot("da_stakeholders") or "",
            tracker.get_slot("da_business_domain") or "",
        ]
    elif role == "project_manager":
        answer_slots = [
            tracker.get_slot("pm_conflict") or "",
            tracker.get_slot("pm_delivery") or "",
            tracker.get_slot("pm_risk_management") or "",
        ]
    elif role == "mlops_engineer":
        answer_slots = [
            tracker.get_slot("mlops_serving") or "",
            tracker.get_slot("mlops_kubernetes") or "",
            tracker.get_slot("mlops_iac") or "",
        ]

    combined = " ".join(answer_slots).lower()
    total_len = sum(len(a) for a in answer_slots)

    # --- Communication clarity (0-5) ---
    # Signals: structured connectors, concrete examples, adequate length
    clarity_signals = ["например", "в частности", "то есть", "в результате",
                       "во-первых", "во-вторых", "таким образом", "конкретно",
                       "instance", "specifically", "for example", "as a result"]
    clarity_hits = sum(1 for s in clarity_signals if s in combined)
    if total_len > 400 and clarity_hits >= 2:
        score += 5; strengths.append("чёткая и структурированная коммуникация")
    elif total_len > 200 or clarity_hits >= 1:
        score += 3
    elif total_len > 80:
        score += 1
    else:
        weaknesses.append("короткие или неинформативные ответы")

    # --- Ownership / initiative (0-5) ---
    # Signals: first-person active verbs
    ownership_signals = ["я разработал", "я внедрил", "я настроил", "я запустил",
                         "я отвечал", "я координировал", "я предложил", "я построил",
                         "я оптимизировал", "я провёл", "я реализовал", "я возглавил",
                         "мне удалось", "под моим руководством", "i built", "i led",
                         "i implemented", "i designed", "i owned"]
    ownership_hits = sum(1 for s in ownership_signals if s in combined)
    if ownership_hits >= 3:
        score += 5; strengths.append("высокий ownership и инициативность")
    elif ownership_hits >= 1:
        score += 3; strengths.append("ownership присутствует")
    else:
        weaknesses.append("слабо выражен ownership (мало личных примеров)")

    # --- Business understanding (0-5) ---
    # Signals: business/product vocabulary
    biz_signals = ["бизнес", "продукт", "метрик", "kpi", "roi", "stakeholder",
                   "revenue", "конверси", "выручк", "impact", "value", "клиент",
                   "пользовател", "retention", "churn", "cost", "эффективн",
                   "decision", "решени", "приоритет", "стратег"]
    biz_hits = sum(1 for s in biz_signals if s in combined)
    if biz_hits >= 4:
        score += 5; strengths.append("сильное бизнес-мышление")
    elif biz_hits >= 2:
        score += 3; strengths.append("базовое понимание бизнес-контекста")
    elif biz_hits >= 1:
        score += 1
    else:
        weaknesses.append("слабое бизнес-понимание в ответах")

    return score, strengths, weaknesses


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def _score_data_scientist(tracker: Tracker, exp: float) -> Tuple[int, List[str], List[str]]:
    """Returns (score 0-100, strengths, weaknesses)."""
    score = 0
    strengths: List[str] = []
    weaknesses: List[str] = []

    # Experience (0–20)
    if exp >= 5:
        score += 20; strengths.append("большой опыт (5+ лет)")
    elif exp >= 3:
        score += 15; strengths.append("хороший опыт (3–5 лет)")
    elif exp >= 1:
        score += 10
    else:
        score += 5; weaknesses.append("менее 1 года опыта")

    # Python (0–15)
    python_lvl = tracker.get_slot("ds_python_level")
    if python_lvl == "advanced":
        score += 15; strengths.append("продвинутый Python")
    elif python_lvl == "intermediate":
        score += 8
    else:
        score += 3; weaknesses.append("слабый Python")

    # Frameworks (0–15) — TZ: sklearn only 5; PyTorch/TF 10; несколько стеков 15
    frameworks = tracker.get_slot("ds_frameworks") or []
    fw_text = " ".join(frameworks).lower() if isinstance(frameworks, list) else str(frameworks).lower()
    has_dl = any(x in fw_text for x in ["pytorch", "tensorflow", "keras", "jax"])
    has_boost = any(x in fw_text for x in ["catboost", "xgboost", "lightgbm"])
    has_sklearn = any(x in fw_text for x in ["sklearn", "scikit"])
    stack_count = sum(1 for x in (has_dl, has_boost, has_sklearn) if x)
    if stack_count >= 2 and has_dl:
        score += 15; strengths.append("несколько ML-стеков + DL-фреймворки")
    elif has_dl:
        score += 10; strengths.append("PyTorch/TensorFlow/Keras")
    elif has_boost:
        score += 10
    elif has_sklearn:
        score += 5
    elif frameworks and frameworks != ["нет практики"]:
        score += 5
    else:
        weaknesses.append("слабый стек ML-фреймворков")

    # Production (0–15) — градация вместо жёсткого да/нет
    prod_pts, prod_str, prod_weak = _ds_production_points(tracker)
    score += prod_pts
    strengths.extend(prod_str)
    weaknesses.extend(prod_weak)

    # ML task types (0–10)
    task_types = str(tracker.get_slot("ds_task_types") or "").lower()
    task_variety = sum(
        1 for t in ["nlp", "cv", "classification", "regression", "ranking", "llm", "генерат", "временн"]
        if t in task_types
    )
    if task_variety >= 3:
        score += 10; strengths.append("широкий спектр ML-задач")
    elif task_variety >= 1:
        score += 5
    else:
        weaknesses.append("узкий опыт задач")

    # A/B testing (0–5)
    ab_raw = str(tracker.get_slot("ds_ab_testing") or "")
    ab_lower = ab_raw.lower()
    if (
        _norm_bool(ab_lower) is True
        or any(x in ab_lower for x in ["a/b", "ab тест", "ab-тест", "сплит", "bucket", "bootstrap", "t-test"])
    ):
        score += 5; strengths.append("опыт A/B тестирования")

    # LLM experience (0–5)
    if str(tracker.get_slot("ds_llm_experience") or "").lower() not in ["", "нет", "false", "no"]:
        score += 5; strengths.append("опыт с LLM")

    # Feature engineering (0–5)
    if str(tracker.get_slot("ds_feature_engineering") or "").lower() not in ["", "нет", "false", "no"]:
        score += 5; strengths.append("feature engineering")

    # Inference optimization (0–5)
    if str(tracker.get_slot("ds_inference_opt") or "").lower() not in ["", "нет", "false", "no"]:
        score += 5

    # Validation & metrics (0–5)
    validation_text = str(tracker.get_slot("ds_validation") or "").lower()
    if any(x in validation_text for x in ["cross", "roc", "auc", "f1", "метрик", "precision", "recall"]):
        score += 5; strengths.append("грамотная валидация моделей")
    else:
        weaknesses.append("слабое описание метрик и валидации")

    # Soft skills (0–15, capped so total stays ≤100)
    soft_score, soft_str, soft_weak = _score_soft_skills(tracker, "data_scientist")
    score += soft_score
    strengths.extend(soft_str)
    weaknesses.extend(soft_weak)

    return min(score, 100), strengths, weaknesses


def _score_data_engineer(tracker: Tracker, exp: float) -> Tuple[int, List[str], List[str]]:
    score = 0
    strengths: List[str] = []
    weaknesses: List[str] = []

    # Experience (0–20)
    if exp >= 5:
        score += 20; strengths.append("большой опыт (5+ лет)")
    elif exp >= 3:
        score += 15; strengths.append("хороший опыт (3–5 лет)")
    elif exp >= 1:
        score += 10
    else:
        score += 5; weaknesses.append("менее 1 года опыта")

    # SQL (0–15)
    sql_lvl = tracker.get_slot("de_sql_level")
    if sql_lvl == "advanced":
        score += 15; strengths.append("продвинутый SQL")
    elif sql_lvl == "intermediate":
        score += 8
    else:
        score += 3; weaknesses.append("слабый SQL")

    # SQL optimization / сложные запросы (0–10)
    sql_opt = str(tracker.get_slot("de_sql_optimization") or "").lower()
    if any(
        x in sql_opt
        for x in ["партиц", "индекс", "оконн", "window", "partition", "explain", "оптимиз", "CTE", "cte"]
    ):
        score += 10; strengths.append("оптимизация сложного SQL")
    elif sql_opt and sql_opt not in ["нет", "нет опыта", ""]:
        score += 5
    else:
        weaknesses.append("мало сигналов по оптимизации SQL")

    # Pipeline / orchestration tools (0–15)
    tools = tracker.get_slot("de_tools") or []
    tools_text = " ".join(tools).lower() if isinstance(tools, list) else str(tools).lower()
    pipeline_text = str(tracker.get_slot("de_pipeline_experience") or "").lower()
    combined = tools_text + " " + pipeline_text
    tool_score = 0
    if any(x in combined for x in ["airflow", "prefect", "dagster"]):
        tool_score += 5
    if any(x in combined for x in ["kafka", "kinesis", "pulsar"]):
        tool_score += 5; strengths.append("streaming (Kafka/Kinesis)")
    if any(x in combined for x in ["spark", "flink", "beam"]):
        tool_score += 5; strengths.append("большие данные (Spark/Flink)")
    if tool_score == 0:
        weaknesses.append("слабый стек инструментов")
    score += tool_score

    # Cloud (0–10)
    if tracker.get_slot("de_cloud_experience") is True:
        score += 10; strengths.append("облачный опыт")
    else:
        weaknesses.append("нет облачного опыта")

    # Data Warehouse (0–10)
    warehouse = str(tracker.get_slot("de_warehouse") or "").lower()
    if any(x in warehouse for x in ["bigquery", "snowflake", "redshift", "clickhouse", "databricks"]):
        score += 10; strengths.append("Data Warehouse опыт")
    elif warehouse and warehouse not in ["нет", "нет опыта", ""]:
        score += 5
    else:
        weaknesses.append("нет опыта с DWH")

    # Monitoring / data quality (0–10)
    monitoring = str(tracker.get_slot("de_monitoring") or "").lower()
    if any(x in monitoring for x in ["great expectations", "dbt test", "качество", "alert", "grafana", "datadog"]):
        score += 10; strengths.append("data quality / мониторинг")
    elif monitoring and monitoring not in ["нет", ""]:
        score += 5
    else:
        weaknesses.append("слабый мониторинг данных")

    # Batch vs streaming (0–5)
    bs = str(tracker.get_slot("de_batch_streaming") or "").lower()
    if "streaming" in bs or "kafka" in bs or "flink" in bs:
        score += 5

    # Kafka / Spark direct (0–5)
    ks = str(tracker.get_slot("de_kafka_spark") or "").lower()
    if any(x in ks for x in ["kafka", "spark", "flink"]):
        score += 5

    # Data volumes (0–5)
    volumes = str(tracker.get_slot("de_data_volumes") or "").lower()
    if any(x in volumes for x in ["tb", "тера", "pb", "пета", "петабайт"]):
        score += 5; strengths.append("опыт с большими объёмами данных (TB+)")

    # Soft skills (0–15)
    soft_score, soft_str, soft_weak = _score_soft_skills(tracker, "data_engineer")
    score += soft_score
    strengths.extend(soft_str)
    weaknesses.extend(soft_weak)

    return min(score, 100), strengths, weaknesses


def _score_data_analyst(tracker: Tracker, exp: float) -> Tuple[int, List[str], List[str]]:
    score = 0
    strengths: List[str] = []
    weaknesses: List[str] = []

    # Experience (0–20)
    if exp >= 5:
        score += 20; strengths.append("большой опыт (5+ лет)")
    elif exp >= 3:
        score += 15
    elif exp >= 1:
        score += 10
    else:
        score += 5; weaknesses.append("менее 1 года опыта")

    # SQL (0–20)
    sql_lvl = tracker.get_slot("da_sql_level")
    if sql_lvl == "advanced":
        score += 20; strengths.append("продвинутый SQL")
    elif sql_lvl == "intermediate":
        score += 12
    else:
        score += 4; weaknesses.append("слабый SQL")

    # BI tools (0–15)
    viz = tracker.get_slot("da_viz_tools") or []
    viz_text = " ".join(viz).lower() if isinstance(viz, list) else str(viz).lower()
    bi_text = str(tracker.get_slot("da_bi_dashboards") or "").lower()
    combined_viz = viz_text + " " + bi_text
    if any(x in combined_viz for x in ["tableau", "power bi", "looker", "superset", "metabase"]):
        score += 15; strengths.append("опыт с BI-инструментами")
    elif viz and viz != ["нет практики"]:
        score += 8
    else:
        weaknesses.append("слабые BI / визуализация навыки")

    # Product metrics (0–15)
    metrics = str(tracker.get_slot("da_product_metrics") or "").lower()
    if any(x in metrics for x in ["dau", "mau", "ltv", "retention", "conversion", "churn", "arpu"]):
        score += 15; strengths.append("понимание продуктовых метрик")
    elif metrics and metrics not in ["нет", ""]:
        score += 8
    else:
        weaknesses.append("слабое понимание продуктовых метрик")

    # A/B tests (0–10)
    ab = str(tracker.get_slot("da_ab_tests") or "").lower()
    if any(x in ab for x in ["t-test", "bootstrap", "mann", "wilcoxon", "sample size", "p-value"]):
        score += 10; strengths.append("статистически грамотное A/B тестирование")
    elif ab and ab not in ["нет", "нет опыта", ""]:
        score += 5
    else:
        weaknesses.append("слабое A/B тестирование")

    # Funnel / cohort analysis (0–10)
    funnel = str(tracker.get_slot("da_funnel_cohort") or "").lower()
    if any(x in funnel for x in ["cohort", "funnel", "воронк", "когорт"]):
        score += 10; strengths.append("funnel / cohort analysis")
    elif funnel and funnel not in ["нет", ""]:
        score += 5
    else:
        weaknesses.append("нет опыта cohort/funnel analysis")

    # Stakeholder / product thinking (0–10)
    pt = str(tracker.get_slot("da_product_thinking") or "").lower()
    stakeholders = str(tracker.get_slot("da_stakeholders") or "").lower()
    if len(pt) > 30 or len(stakeholders) > 30:
        score += 10; strengths.append("product thinking и работа со стейкхолдерами")
    else:
        weaknesses.append("слабое описание работы со стейкхолдерами")

    # Soft skills (0–15) — особенно важны для DA
    soft_score, soft_str, soft_weak = _score_soft_skills(tracker, "data_analyst")
    score += soft_score
    strengths.extend(soft_str)
    weaknesses.extend(soft_weak)

    return min(score, 100), strengths, weaknesses


def _score_project_manager(tracker: Tracker, exp: float) -> Tuple[int, List[str], List[str]]:
    score = 0
    strengths: List[str] = []
    weaknesses: List[str] = []

    # Experience (0–20)
    if exp >= 5:
        score += 20; strengths.append("большой опыт (5+ лет)")
    elif exp >= 3:
        score += 15
    elif exp >= 1:
        score += 10
    else:
        score += 5; weaknesses.append("менее 1 года опыта")

    # Team size (0–15)
    team_size = float(tracker.get_slot("pm_team_size") or 0.0)
    if team_size >= 15:
        score += 15; strengths.append(f"управление большой командой ({int(team_size)}+ чел.)")
    elif team_size >= 7:
        score += 10; strengths.append(f"управление командой ({int(team_size)} чел.)")
    elif team_size >= 3:
        score += 6
    else:
        weaknesses.append("опыт работы только с маленькими командами")

    # Methodology (0–10)
    methodology = tracker.get_slot("pm_methodology") or []
    method_text = " ".join(methodology).lower() if isinstance(methodology, list) else str(methodology).lower()
    if any(x in method_text for x in ["scrum", "kanban", "safe", "agile", "less"]):
        score += 10; strengths.append("Agile/Scrum методологии")
    elif methodology and methodology != ["не применял"]:
        score += 5
    else:
        weaknesses.append("слабое знание методологий")

    # ML understanding (0–15)
    ml_und = tracker.get_slot("pm_ml_understanding")
    if ml_und == "good":
        score += 15; strengths.append("хорошее понимание ML")
    elif ml_und == "basic":
        score += 8
    else:
        weaknesses.append("слабое понимание ML-проектов")

    # Risk management (0–10)
    risk = str(tracker.get_slot("pm_risk_management") or "").lower()
    if any(x in risk for x in ["risk register", "риск", "митигац", "escalat", "issue log"]):
        score += 10; strengths.append("управление рисками")
    elif risk and risk not in ["нет", ""]:
        score += 5
    else:
        weaknesses.append("слабое описание управления рисками")

    # Budget ownership (0–10)
    budget = str(tracker.get_slot("pm_budget") or "").lower()
    if any(x in budget for x in ["бюджет", "budget", "$", "млн", "миллион", "тысяч"]):
        score += 10; strengths.append("budget ownership")
    else:
        weaknesses.append("нет опыта управления бюджетом")

    # Delivery (0–10)
    delivery = str(tracker.get_slot("pm_delivery") or "").lower()
    if len(delivery) > 40:
        score += 10; strengths.append("чёткое описание delivery-опыта")
    elif delivery and delivery not in ["нет", ""]:
        score += 5
    else:
        weaknesses.append("слабое описание delivery")

    # Conflict management (0–8)
    conflict = str(tracker.get_slot("pm_conflict") or "").lower()
    if len(conflict) > 60 and any(
        x in conflict for x in ["конфликт", "mediat", "медиат", "сторон", "договор", "решил", "соглас"]
    ):
        score += 8; strengths.append("опыт разрешения конфликтов")
    elif len(conflict) > 25:
        score += 4
    else:
        weaknesses.append("слабо раскрыт conflict management")

    # AI/ML projects (0–5)
    ai_proj = str(tracker.get_slot("pm_ai_ml_projects") or "").lower()
    if ai_proj and ai_proj not in ["нет", "no", ""]:
        score += 5; strengths.append("опыт AI/ML проектов")
    else:
        weaknesses.append("нет опыта AI/ML проектов")

    # Distributed team (0–5)
    dist = str(tracker.get_slot("pm_distributed_team") or "").lower()
    if any(x in dist for x in ["да", "yes", "страна", "удалённ", "remote", "distributed"]):
        score += 5

    # Soft skills (0–15) — для PM особенно критичны
    soft_score, soft_str, soft_weak = _score_soft_skills(tracker, "project_manager")
    score += soft_score
    strengths.extend(soft_str)
    weaknesses.extend(soft_weak)

    return min(score, 100), strengths, weaknesses


def _score_mlops_engineer(tracker: Tracker, exp: float) -> Tuple[int, List[str], List[str]]:
    score = 0
    strengths: List[str] = []
    weaknesses: List[str] = []

    # Experience (0–20)
    if exp >= 5:
        score += 20; strengths.append("большой опыт (5+ лет)")
    elif exp >= 3:
        score += 15
    elif exp >= 1:
        score += 10
    else:
        score += 5; weaknesses.append("менее 1 года опыта")

    # CI/CD (0–15)
    if tracker.get_slot("mlops_ci_cd") is True:
        score += 15; strengths.append("CI/CD для ML")
    else:
        weaknesses.append("нет CI/CD опыта")

    # Tools (0–15)
    tools = tracker.get_slot("mlops_tools") or []
    tools_text = " ".join(tools).lower() if isinstance(tools, list) else str(tools).lower()
    docker_slot = str(tracker.get_slot("mlops_docker") or "").lower()
    docker_ok = (
        _norm_bool(docker_slot) is True
        or any(x in docker_slot for x in ["docker", "контейнер", "image", "dockerfile"])
    )
    tool_score = 0
    if any(x in tools_text for x in ["mlflow", "kubeflow", "neptune", "wandb", "dvc"]):
        tool_score += 5; strengths.append("ML-платформы (MLflow/Kubeflow)")
    if any(x in tools_text for x in ["kubernetes", "k8s", "helm"]):
        tool_score += 5; strengths.append("Kubernetes")
    if any(x in tools_text for x in ["docker", "containerd"]) or docker_ok:
        tool_score += 5; strengths.append("Docker")
    if tool_score == 0:
        weaknesses.append("слабый MLOps-стек")
    score += tool_score

    # Monitoring (0–10)
    if tracker.get_slot("mlops_monitoring") is True:
        score += 10; strengths.append("мониторинг моделей")
    else:
        weaknesses.append("нет мониторинга моделей")

    # Kubernetes direct slot (0–10)
    k8s = str(tracker.get_slot("mlops_kubernetes") or "").lower()
    if any(x in k8s for x in ["да", "yes", "helm", "kubectl", "namespace", "pod"]):
        score += 10

    # Model registry (0–5)
    registry = str(tracker.get_slot("mlops_model_registry") or "").lower()
    if any(x in registry for x in ["mlflow", "dvc", "neptune", "wandb", "registry"]):
        score += 5; strengths.append("model registry")
    else:
        weaknesses.append("нет опыта с model registry")

    # IaC (0–5)
    iac = str(tracker.get_slot("mlops_iac") or "").lower()
    if any(x in iac for x in ["terraform", "pulumi", "ansible", "cloudformation"]):
        score += 5; strengths.append("IaC (Terraform/Pulumi)")
    else:
        weaknesses.append("нет IaC опыта")

    # ML serving (0–10)
    serving = str(tracker.get_slot("mlops_serving") or "").lower()
    if any(x in serving for x in ["triton", "torchserve", "bentoml", "seldon", "kserve", "serving"]):
        score += 10; strengths.append("ML serving")
    elif serving and serving not in ["нет", ""]:
        score += 5
    else:
        weaknesses.append("слабый ML serving опыт")

    # GPU infrastructure (0–5)
    gpu = str(tracker.get_slot("mlops_gpu") or "").lower()
    if any(x in gpu for x in ["gpu", "cuda", "nvidia", "a100", "p3", "g4"]):
        score += 5; strengths.append("GPU-инфраструктура")

    # Soft skills (0–15)
    soft_score, soft_str, soft_weak = _score_soft_skills(tracker, "mlops_engineer")
    score += soft_score
    strengths.extend(soft_str)
    weaknesses.extend(soft_weak)

    return min(score, 100), strengths, weaknesses


def _score_candidate(tracker: Tracker) -> Tuple[int, str, str, List[str], List[str], List[str]]:
    """
    Returns (score, level, hire_decision, strengths, weaknesses, consistency_warnings).
    """
    role = tracker.get_slot("desired_role")
    exp = float(tracker.get_slot("experience_years") or 0.0)
    level = _determine_level(exp)

    score_funcs = {
        "data_scientist": _score_data_scientist,
        "data_engineer": _score_data_engineer,
        "data_analyst": _score_data_analyst,
        "project_manager": _score_project_manager,
        "mlops_engineer": _score_mlops_engineer,
    }

    if role in score_funcs:
        score, strengths, weaknesses = score_funcs[role](tracker, exp)
    else:
        score, strengths, weaknesses = 0, [], ["Роль не определена"]

    score = _apply_level_score_adjustment(score, level, role, tracker)

    warnings = _consistency_checks(tracker, exp, role)

    decision = _hire_decision_from_score(score)

    return score, level, decision, strengths, weaknesses, warnings


def _consistency_checks(tracker: Tracker, exp: float, role: Optional[str]) -> List[str]:
    """Returns list of inconsistency warning strings."""
    warnings: List[str] = []

    python_lvl = tracker.get_slot("ds_python_level")
    if exp < 0.75 and python_lvl == "advanced":
        warnings.append("⚠️ Менее 9 мес. опыта, но заявлен продвинутый Python — стоит уточнить.")

    da_sql = str(tracker.get_slot("da_sql_level") or "")
    da_domain = str(tracker.get_slot("da_business_domain") or "").lower()
    if da_sql == "beginner" and any(x in da_domain for x in ["оконные", "window", "partition by"]):
        warnings.append("⚠️ Заявлен начальный SQL, но упомянуты оконные функции — противоречие.")

    de_sql = str(tracker.get_slot("de_sql_level") or "")
    de_pipeline = str(tracker.get_slot("de_pipeline_experience") or "").lower()
    if de_sql == "beginner" and any(x in de_pipeline for x in ["оконные", "partition", "window", "оптимиз"]):
        warnings.append("⚠️ Заявлен начальный SQL, но описана оптимизация сложных запросов.")

    has_prod = tracker.get_slot("ds_has_production")
    mlops_tools = tracker.get_slot("mlops_tools") or []
    mlops_text = " ".join(mlops_tools).lower() if isinstance(mlops_tools, list) else ""
    if has_prod is False and any(x in mlops_text for x in ["kubernetes", "triton", "seldon", "kserve"]):
        warnings.append("⚠️ Нет production-опыта, но заявлен опыт с production-grade MLOps инструментами.")

    pm_team = float(tracker.get_slot("pm_team_size") or 0.0)
    if exp < 1.5 and pm_team >= 15:
        warnings.append(f"⚠️ Менее 1.5 лет опыта, но координация команды {int(pm_team)}+ чел. — стоит уточнить.")

    # Новые consistency checks
    # DS: нет фреймворков, но есть production
    frameworks = tracker.get_slot("ds_frameworks") or []
    fw_text = " ".join(frameworks).lower() if isinstance(frameworks, list) else str(frameworks).lower()
    if has_prod is True and (not frameworks or fw_text in ["нет практики", ""]):
        warnings.append("⚠️ Заявлен production-опыт, но не указаны ML-фреймворки — стоит уточнить стек.")

    # MLOps: CI/CD есть, но нет Docker/K8s
    cicd = tracker.get_slot("mlops_ci_cd")
    mlops_docker_ans = str(tracker.get_slot("mlops_docker") or "").lower()
    if cicd is True and not any(x in mlops_text for x in ["docker", "kubernetes", "k8s"]) and not any(
        x in mlops_docker_ans for x in ["docker", "k8", "helm", "kubectl"]
    ):
        warnings.append("⚠️ Есть CI/CD опыт, но не упомянуты Docker/Kubernetes — стоит уточнить.")

    # DA: advanced SQL, но нет BI-инструментов
    da_sql_lvl = tracker.get_slot("da_sql_level")
    da_bi = str(tracker.get_slot("da_bi_dashboards") or "").lower()
    if da_sql_lvl == "beginner" and any(x in da_bi for x in ["оконные", "window", "partition", "оптимиз"]):
        warnings.append("⚠️ Заявлен начальный SQL, но в BI/SQL-контексте упомянуты сложные конструкции — уточнить.")

    sql_opt_de = str(tracker.get_slot("de_sql_optimization") or "").lower()
    if de_sql == "beginner" and any(x in sql_opt_de for x in ["оконные", "window", "partition", "оптимиз"]):
        warnings.append("⚠️ Заявлен начальный SQL, но описана оптимизация сложных запросов / оконные функции.")

    da_viz = tracker.get_slot("da_viz_tools") or []
    da_viz_text = " ".join(da_viz).lower() if isinstance(da_viz, list) else str(da_viz).lower()
    if da_sql_lvl == "advanced" and (not da_viz or da_viz_text in ["нет практики", ""]):
        warnings.append("⚠️ Продвинутый SQL, но нет BI-инструментов — нетипично для DA.")

    return warnings


def _salary_assessment(tracker: Tracker, level: str, score: Optional[int] = None) -> Optional[str]:
    """Проверка зарплаты: рынок по уровню, завышение, salary-to-skill ratio."""
    salary = tracker.get_slot("salary_expectation")
    if salary is None:
        return None
    role = tracker.get_slot("desired_role")
    benchmarks = SALARY_BENCHMARKS.get(role or "", {})
    if not benchmarks:
        return None
    low, high = benchmarks.get(level, (0, 0))
    salary_f = float(salary)
    parts: List[str] = []

    if salary_f < low * 0.8:
        parts.append(
            f"Ожидания ({int(salary_f):,} ₽) ниже типичного рынка для {_level_display_ru(level)} "
            f"(ориентир: {low:,}–{high:,} ₽) — возможно, недооценка"
        )
    elif salary_f > high * 1.25:
        parts.append(
            f"Ожидания ({int(salary_f):,} ₽) заметно выше рынка для {_level_display_ru(level)} "
            f"(ориентир: {low:,}–{high:,} ₽)"
        )
    else:
        parts.append(
            f"Ожидания ({int(salary_f):,} ₽) в разумном диапазоне для {_level_display_ru(level)} "
            f"(ориентир: {low:,}–{high:,} ₽)"
        )

    if score is not None and high > low:
        mid = (low + high) / 2.0
        ratio = (salary_f - low) / (high - low + 1)
        skill_norm = max(0.0, min(1.0, score / 100.0))
        if salary_f > mid and score < 55:
            parts.append("Salary-to-skill: высокие ожидания при относительно низком score — стоит валидировать на техсобесе")
        elif salary_f > high and skill_norm + 0.15 < ratio:
            parts.append("Salary-to-skill: зарплата выше рынка сильнее, чем отражает оценка навыков")
        elif salary_f < low * 0.9 and score >= 75:
            parts.append("Salary-to-skill: сильный профиль при скромных ожиданиях — хороший match по мотивации/бюджету")

    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Next question routing
# ---------------------------------------------------------------------------

def _next_question_response(gv: Any) -> Tuple[str, List[Dict[Text, Any]]]:
    role = gv("desired_role")
    events: List[Dict[Text, Any]] = []

    if role == "data_scientist":
        if not gv("ds_ml_experience"):
            return "utter_ask_ds_ml_experience", events
        if not gv("ds_task_types"):
            return "utter_ask_ds_task_types", events
        if not gv("ds_feature_engineering"):
            return "utter_ask_ds_feature_engineering", events
        if not gv("ds_validation"):
            return "utter_ask_ds_validation", events
        if not gv("ds_python_level"):
            return "utter_ask_ds_python_level", events
        if not gv("ds_frameworks"):
            return "utter_ask_ds_frameworks", events
        if gv("ds_has_production") is None:
            return "utter_ask_ds_production", events
        if not gv("ds_ab_testing"):
            return "utter_ask_ds_ab_testing", events
        if not gv("ds_llm_experience"):
            return "utter_ask_ds_llm", events
        if not gv("ds_inference_opt"):
            return "utter_ask_ds_inference_opt", events

    elif role == "data_engineer":
        if not gv("de_pipeline_experience"):
            return "utter_ask_de_pipeline", events
        if not gv("de_data_volumes"):
            return "utter_ask_de_data_volumes", events
        if not gv("de_batch_streaming"):
            return "utter_ask_de_batch_streaming", events
        if not gv("de_kafka_spark"):
            return "utter_ask_de_kafka_spark", events
        if not gv("de_warehouse"):
            return "utter_ask_de_warehouse", events
        if not gv("de_tools"):
            return "utter_ask_de_tools", events
        if gv("de_cloud_experience") is None:
            return "utter_ask_de_cloud", events
        if not gv("de_sql_level"):
            return "utter_ask_de_sql", events
        if not gv("de_sql_optimization"):
            return "utter_ask_de_sql_optimization", events
        if not gv("de_orchestration"):
            return "utter_ask_de_orchestration", events
        if not gv("de_monitoring"):
            return "utter_ask_de_monitoring", events

    elif role == "data_analyst":
        if not gv("da_business_domain"):
            return "utter_ask_da_domain", events
        if not gv("da_product_metrics"):
            return "utter_ask_da_product_metrics", events
        if not gv("da_ab_tests"):
            return "utter_ask_da_ab_tests", events
        if not gv("da_funnel_cohort"):
            return "utter_ask_da_funnel_cohort", events
        if not gv("da_viz_tools"):
            return "utter_ask_da_viz", events
        if not gv("da_sql_level"):
            return "utter_ask_da_sql", events
        if not gv("da_bi_dashboards"):
            return "utter_ask_da_bi", events
        if not gv("da_stakeholders"):
            return "utter_ask_da_stakeholders", events
        if not gv("da_product_thinking"):
            return "utter_ask_da_product_thinking", events

    elif role == "project_manager":
        if gv("pm_team_size") is None:
            return "utter_ask_pm_team_size", events
        if not gv("pm_methodology"):
            return "utter_ask_pm_methodology", events
        if not gv("pm_ml_understanding"):
            return "utter_ask_pm_ml_understanding", events
        if not gv("pm_risk_management"):
            return "utter_ask_pm_risk_management", events
        if not gv("pm_budget"):
            return "utter_ask_pm_budget", events
        if not gv("pm_conflict"):
            return "utter_ask_pm_conflict", events
        if not gv("pm_delivery"):
            return "utter_ask_pm_delivery", events
        if not gv("pm_distributed_team"):
            return "utter_ask_pm_distributed_team", events
        if not gv("pm_ai_ml_projects"):
            return "utter_ask_pm_ai_ml_projects", events

    elif role == "mlops_engineer":
        if gv("mlops_ci_cd") is None:
            return "utter_ask_mlops_cicd", events
        if not gv("mlops_tools"):
            return "utter_ask_mlops_tools", events
        if gv("mlops_monitoring") is None:
            return "utter_ask_mlops_monitoring", events
        if not gv("mlops_kubernetes"):
            return "utter_ask_mlops_kubernetes", events
        if not gv("mlops_model_registry"):
            return "utter_ask_mlops_model_registry", events
        if not gv("mlops_docker"):
            return "utter_ask_mlops_docker", events
        if not gv("mlops_iac"):
            return "utter_ask_mlops_iac", events
        if not gv("mlops_serving"):
            return "utter_ask_mlops_serving", events
        if not gv("mlops_gpu"):
            return "utter_ask_mlops_gpu", events

    events.append(SlotSet("interview_stage", "collect_salary"))
    return "utter_ask_salary", events


def _pending_to_events(pending: Dict[str, Any]) -> List[Dict[Text, Any]]:
    return [SlotSet(k, v) for k, v in pending.items()]


def _fill_no_experience(pending: Dict[str, Any], last_key: str, role: Optional[str], text_raw: str) -> None:
    note = text_raw or "Нет такого опыта"
    lk = last_key or ""
    # DS
    if "ds_ml" in lk:
        pending["ds_ml_experience"] = note
    elif "ds_task_type" in lk:
        pending["ds_task_types"] = note
    elif "ds_feature" in lk:
        pending["ds_feature_engineering"] = note
    elif "ds_valid" in lk:
        pending["ds_validation"] = note
    elif "ds_python" in lk:
        pending["ds_python_level"] = "beginner"
    elif "ds_framework" in lk:
        pending["ds_frameworks"] = ["нет практики"]
    elif "ds_production" in lk:
        pending["ds_has_production"] = False
    elif "ds_ab" in lk:
        pending["ds_ab_testing"] = "нет"
    elif "ds_llm" in lk:
        pending["ds_llm_experience"] = "нет"
    elif "ds_inference" in lk:
        pending["ds_inference_opt"] = "нет"
    # DE
    elif "de_pipeline" in lk:
        pending["de_pipeline_experience"] = note
    elif "de_data_vol" in lk:
        pending["de_data_volumes"] = "нет данных"
    elif "de_batch" in lk:
        pending["de_batch_streaming"] = "нет"
    elif "de_kafka" in lk:
        pending["de_kafka_spark"] = "нет"
    elif "de_warehouse" in lk:
        pending["de_warehouse"] = "нет"
    elif "de_tools" in lk:
        pending["de_tools"] = ["нет практики"]
    elif "de_cloud" in lk:
        pending["de_cloud_experience"] = False
    elif "de_sql" in lk and "optimization" not in lk:
        pending["de_sql_level"] = "beginner"
    elif "de_sql_optimization" in lk or ("de_sql" in lk and "optimization" in lk):
        pending["de_sql_optimization"] = "нет"
    elif "de_orchestration" in lk:
        pending["de_orchestration"] = "нет"
    elif "de_monitoring" in lk:
        pending["de_monitoring"] = "нет"
    # DA
    elif "da_domain" in lk:
        pending["da_business_domain"] = note
    elif "da_product_metrics" in lk:
        pending["da_product_metrics"] = "нет"
    elif "da_ab_tests" in lk:
        pending["da_ab_tests"] = "нет"
    elif "da_funnel" in lk:
        pending["da_funnel_cohort"] = "нет"
    elif "da_viz" in lk:
        pending["da_viz_tools"] = ["нет практики"]
    elif "da_sql" in lk:
        pending["da_sql_level"] = "beginner"
    elif "da_bi" in lk:
        pending["da_bi_dashboards"] = "нет"
    elif "da_stakeholder" in lk:
        pending["da_stakeholders"] = "нет"
    elif "da_product_thinking" in lk:
        pending["da_product_thinking"] = "нет"
    # PM
    elif "pm_team" in lk:
        pending["pm_team_size"] = 0.0
    elif "pm_method" in lk:
        pending["pm_methodology"] = ["не применял"]
    elif "pm_ml" in lk:
        pending["pm_ml_understanding"] = "none"
    elif "pm_risk" in lk:
        pending["pm_risk_management"] = "нет"
    elif "pm_budget" in lk:
        pending["pm_budget"] = "нет"
    elif "pm_conflict" in lk:
        pending["pm_conflict"] = "нет"
    elif "pm_delivery" in lk:
        pending["pm_delivery"] = "нет"
    elif "pm_distributed" in lk:
        pending["pm_distributed_team"] = "нет"
    elif "pm_ai" in lk:
        pending["pm_ai_ml_projects"] = "нет"
    # MLOps
    elif "mlops_cicd" in lk:
        pending["mlops_ci_cd"] = False
    elif "mlops_tools" in lk:
        pending["mlops_tools"] = ["нет практики"]
    elif "mlops_monitoring" in lk:
        pending["mlops_monitoring"] = False
    elif "mlops_kubernetes" in lk:
        pending["mlops_kubernetes"] = "нет"
    elif "mlops_model_registry" in lk:
        pending["mlops_model_registry"] = "нет"
    elif "mlops_docker" in lk:
        pending["mlops_docker"] = "нет"
    elif "mlops_iac" in lk:
        pending["mlops_iac"] = "нет"
    elif "mlops_serving" in lk:
        pending["mlops_serving"] = "нет"
    elif "mlops_gpu" in lk:
        pending["mlops_gpu"] = "нет"
    elif role == "data_scientist" and not pending.get("ds_ml_experience"):
        pending["ds_ml_experience"] = note
    elif role == "data_engineer" and not pending.get("de_pipeline_experience"):
        pending["de_pipeline_experience"] = note


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

class ActionGreet(Action):
    def name(self) -> Text:
        return "action_greet"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        stage = tracker.get_slot("interview_stage")
        if stage and stage not in ("idle", None, "farewell", "end"):
            return []
        events: List[Dict[Text, Any]] = []
        if stage in ("farewell", "end"):
            events.append(AllSlotsReset())
        dispatcher.utter_message(response="utter_greet")
        events += [
            SlotSet("interview_stage", "greeting"),
            SlotSet("last_question_key", "utter_ask_name"),
        ]
        return events


class ActionConfirmReadiness(Action):
    def name(self) -> Text:
        return "action_confirm_readiness"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        if tracker.get_slot("candidate_name"):
            dispatcher.utter_message(response="utter_confirm_receipt")
            return []
        dispatcher.utter_message(response="utter_intro_after_readiness")
        return [SlotSet("last_question_key", "utter_ask_name")]


class ActionCollectName(Action):
    """Extracts candidate name from the current message and advances to experience."""

    def name(self) -> Text:
        return "action_collect_name"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        text_raw = _latest_text(tracker)

        # Try entity first, then fall back to raw text (capitalised word)
        name: Optional[str] = None
        for ent in tracker.latest_message.get("entities", []) or []:
            if ent.get("entity") in ("PERSON", "person", "candidate_name"):
                name = ent.get("value", "").strip()
                break

        if not name:
            # Heuristic: take first capitalised word that isn't a stop-word
            stop = {"меня", "зовут", "мое", "моё", "имя", "я", "мой"}
            for token in text_raw.split():
                clean = re.sub(r"[^\w]", "", token)
                if clean and clean[0].isupper() and clean.lower() not in stop:
                    name = clean
                    break

        if not name:
            name = text_raw.strip() or "Кандидат"

        # Extract first name for addressing (take first word of full name/ФИО)
        first_name = name.split()[0] if name.split() else name

        dispatcher.utter_message(
            response="utter_name_acknowledged",
            **{"candidate_first_name": first_name},
        )
        dispatcher.utter_message(response="utter_ask_experience")
        return [
            SlotSet("candidate_name", name),
            SlotSet("candidate_first_name", first_name),
            SlotSet("interview_stage", "collect_experience"),
            SlotSet("last_question_key", "utter_ask_experience"),
        ]


class ActionCollectExperience(Action):
    """Parses years of experience, decides whether to warn about low exp."""

    def name(self) -> Text:
        return "action_collect_experience"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        text = _latest_text_lower(tracker)

        # Try entity first
        exp: Optional[float] = None
        for ent in tracker.latest_message.get("entities", []) or []:
            if ent.get("entity") in ("experience_years", "number"):
                try:
                    exp = float(ent["value"])
                except (TypeError, ValueError):
                    pass
                break

        if exp is None:
            # Parse "менее года" / "меньше года" → 0.5
            if re.search(r"(менее|меньше|меньше чем|less than)\s*(год|1\s*год)", text):
                exp = 0.5
            # Parse "нет опыта" / "без опыта"
            elif re.search(r"(нет|без)\s*(опыта|experience)", text):
                exp = 0.0
            else:
                exp = _extract_number(text)

        if exp is None:
            dispatcher.utter_message(response="utter_experience_parse_error")
            return [SlotSet("last_question_key", "utter_ask_experience")]

        events: List[Dict[Text, Any]] = [
            SlotSet("experience_years", float(exp)),
            SlotSet("last_question_key", "utter_ask_role"),
        ]

        if exp < 1.0:
            dispatcher.utter_message(response="utter_low_experience_warning")
            events.append(SlotSet("interview_stage", "collect_experience_low"))
        else:
            dispatcher.utter_message(response="utter_ask_role")
            events.append(SlotSet("interview_stage", "collect_role"))

        return events


class ActionCollectRole(Action):
    """Maps user reply to a canonical role slug and starts the interview."""

    ROLE_MAP: Dict[str, str] = {
        # Data Scientist
        "data scientist": "data_scientist",
        "data science": "data_scientist",
        "ml engineer": "data_scientist",
        "machine learning": "data_scientist",
        "датасаентист": "data_scientist",
        "дата сайентист": "data_scientist",
        "ml-инженер": "data_scientist",
        # Data Engineer
        "data engineer": "data_engineer",
        "дата инженер": "data_engineer",
        "data engineering": "data_engineer",
        "де": "data_engineer",
        # Data Analyst
        "data analyst": "data_analyst",
        "аналитик данных": "data_analyst",
        "аналитик": "data_analyst",
        "da": "data_analyst",
        # Project Manager
        "project manager": "project_manager",
        "проджект менеджер": "project_manager",
        "pm": "project_manager",
        "product manager": "project_manager",
        # MLOps
        "mlops": "mlops_engineer",
        "mlops engineer": "mlops_engineer",
        "ml ops": "mlops_engineer",
        "девопс": "mlops_engineer",
        "devops": "mlops_engineer",
    }

    def name(self) -> Text:
        return "action_collect_role"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        text_lower = _latest_text_lower(tracker)

        # Entity from NLU
        role: Optional[str] = None
        for ent in tracker.latest_message.get("entities", []) or []:
            if ent.get("entity") == "desired_role":
                role = ent.get("value")
                break

        # Keyword fallback
        if not role:
            for keyword, slug in self.ROLE_MAP.items():
                if keyword in text_lower:
                    role = slug
                    break

        if not role:
            dispatcher.utter_message(response="utter_role_not_recognized")
            return [SlotSet("last_question_key", "utter_ask_role")]

        role_labels = {
            "data_scientist": "Data Scientist",
            "data_engineer": "Data Engineer",
            "data_analyst": "Data Analyst",
            "project_manager": "Project Manager",
            "mlops_engineer": "MLOps Engineer",
        }
        role_label = role_labels.get(role, role)
        dispatcher.utter_message(response="utter_role_confirmed", **{"role": role_label})
        return [
            SlotSet("desired_role", role),
            SlotSet("interview_stage", "collect_role"),
            SlotSet("last_question_key", "utter_ask_role"),
            FollowupAction("action_route_to_role_interview"),
        ]


class ActionStopInterview(Action):
    """Gracefully ends the interview on user request."""

    def name(self) -> Text:
        return "action_stop_interview"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        stage = tracker.get_slot("interview_stage") or ""

        # If we have enough data, save what we have
        has_role = bool(tracker.get_slot("desired_role"))
        has_exp = tracker.get_slot("experience_years") is not None

        dispatcher.utter_message(response="utter_farewell_stopped")

        events: List[Dict[Text, Any]] = [
            SlotSet("interview_stage", "farewell"),
        ]

        if has_role and has_exp:
            events.append(FollowupAction("action_save_candidate_data"))

        return events


class ActionHandleUnsuitable(Action):
    def name(self) -> Text:
        return "action_handle_unsuitable"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(response="utter_unsuitable_ack")
        follow = tracker.get_slot("last_question_key")
        if follow and isinstance(follow, str) and follow.startswith("utter_"):
            dispatcher.utter_message(response=follow)
        return []


class ActionAskRepeat(Action):
    def name(self) -> Text:
        return "action_ask_repeat"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        count = int(tracker.get_slot("ask_repeat_count") or 0)
        key = tracker.get_slot("last_question_key") or "utter_ask_experience"
        question = QUESTION_TEXT.get(key, "Повторю предыдущий вопрос.")
        example = QUESTION_EXAMPLES.get(key, "Кратко и по делу.")

        if count >= 1:
            dispatcher.utter_message(text=f"Повторяю вопрос: {question}")
            return [SlotSet("ask_repeat_count", float(count + 1))]

        dispatcher.utter_message(
            response="utter_ask_repeat_rephrase",
            **{"last_question": question, "example": example},
        )
        return [SlotSet("ask_repeat_count", float(count + 1))]


class ActionHandleUnclearAnswer(Action):
    def name(self) -> Text:
        return "action_handle_unclear_answer"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        stage = tracker.get_slot("interview_stage") or ""
        if stage in ("farewell", "end"):
            return []

        clarify = int(tracker.get_slot("clarify_count") or 0)
        key = str(tracker.get_slot("last_question_key") or "")

        if clarify >= 2:
            dispatcher.utter_message(response="utter_unclear_move_on")
            stage = tracker.get_slot("interview_stage") or ""
            if stage == "collect_salary":
                return [
                    SlotSet("clarify_count", 0.0),
                    FollowupAction("action_collect_salary"),
                ]
            return [
                SlotSet("clarify_count", 0.0),
                FollowupAction("action_route_to_role_interview"),
            ]

        if "python" in key or "sql" in key:
            dispatcher.utter_message(response="utter_clarify_options")
        else:
            dispatcher.utter_message(response="utter_not_recognized")

        return [SlotSet("clarify_count", float(clarify + 1))]


class ActionCollectSalary(Action):
    def name(self) -> Text:
        return "action_collect_salary"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        text = _latest_text(tracker)
        attempts = int(tracker.get_slot("salary_parse_attempts") or 0)

        stage = tracker.get_slot("interview_stage") or ""
        if stage != "collect_salary":
            return []

        # Guard against rule-chaining: action_route_to_role_interview sets
        # interview_stage=collect_salary in the same turn as the user's last
        # interview answer, causing Rasa to immediately re-fire this action via
        # the "Collect salary - open answer" rule before the user has replied.
        # We detect this by checking that a user event exists AFTER the last
        # action_route_to_role_interview event in the tracker history.
        last_route_idx = -1
        last_user_idx = -1
        for i, ev in enumerate(tracker.events):
            name = ev.get("name", "") if ev.get("event") == "action" else ""
            if name == "action_route_to_role_interview":
                last_route_idx = i
            if ev.get("event") == "user":
                last_user_idx = i
        if last_route_idx >= 0 and last_user_idx <= last_route_idx:
            return []

        salary = tracker.get_slot("salary_expectation")
        if salary is None:
            for ent in tracker.latest_message.get("entities", []) or []:
                if ent.get("entity") == "salary_expectation" and ent.get("value") is not None:
                    try:
                        salary = float(ent.get("value"))
                    except (TypeError, ValueError):
                        salary = None
                    break

        if salary is None:
            salary = _parse_salary_from_raw(text.lower())

        if salary is not None:
            return [
                SlotSet("salary_expectation", float(salary)),
                SlotSet("salary_parse_attempts", 0.0),
                SlotSet("interview_stage", "assessment"),
                FollowupAction("action_assess_candidate"),
            ]

        if attempts >= 2:
            return [
                SlotSet("salary_parse_attempts", float(attempts + 1)),
                SlotSet("interview_stage", "assessment"),
                FollowupAction("action_assess_candidate"),
            ]

        dispatcher.utter_message(response="utter_salary_format_hint")
        return [SlotSet("salary_parse_attempts", float(attempts + 1))]


class ActionRouteToRoleInterview(Action):
    def name(self) -> Text:
        return "action_route_to_role_interview"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        text_lower = _latest_text_lower(tracker)
        text_raw = _latest_text(tracker)
        intent = _intent_name(tracker)
        role = tracker.get_slot("desired_role")
        last_key = str(tracker.get_slot("last_question_key") or "")

        if not role:
            dispatcher.utter_message(response="utter_ask_role")
            return [SlotSet("last_question_key", "utter_ask_role")]

        current_stage = tracker.get_slot("interview_stage")
        entering_interview = current_stage == "collect_role"

        pending: Dict[str, Any] = {}
        events: List[Dict[Text, Any]] = [
            SlotSet("interview_stage", _role_interview_stage(role)),
            SlotSet("clarify_count", 0.0),
            SlotSet("ask_repeat_count", 0.0),
        ]

        # --- DS slots ---
        if role == "data_scientist" and (
            intent in {"provide_project_experience", "answer_ml_experience"}
            or (intent == "answer_interview_open" and last_key == "utter_ask_ds_ml_experience")
        ):
            pending["ds_ml_experience"] = text_raw
        if last_key == "utter_ask_ds_task_types" and intent not in {"stop_interview", "goodbye", "out_of_scope"}:
            pending["ds_task_types"] = text_raw
        if last_key == "utter_ask_ds_feature_engineering" and intent not in {"stop_interview", "goodbye", "out_of_scope"}:
            pending["ds_feature_engineering"] = text_raw
        if last_key == "utter_ask_ds_validation" and intent not in {"stop_interview", "goodbye", "out_of_scope"}:
            pending["ds_validation"] = text_raw
        if last_key == "utter_ask_ds_llm" and intent not in {"stop_interview", "goodbye", "out_of_scope"}:
            pending["ds_llm_experience"] = text_raw
        if last_key == "utter_ask_ds_inference_opt" and intent not in {"stop_interview", "goodbye", "out_of_scope"}:
            pending["ds_inference_opt"] = text_raw
        if last_key == "utter_ask_ds_ab_testing":
            val = _norm_bool(text_lower)
            pending["ds_ab_testing"] = "да" if val else ("нет" if val is False else text_raw)

        # --- DE slots ---
        if intent == "answer_pipeline_experience" or (
            intent == "answer_interview_open" and last_key == "utter_ask_de_pipeline"
        ):
            pending["de_pipeline_experience"] = text_raw
        if last_key == "utter_ask_de_data_volumes":
            pending["de_data_volumes"] = text_raw
        if last_key == "utter_ask_de_batch_streaming":
            pending["de_batch_streaming"] = text_raw
        if last_key == "utter_ask_de_kafka_spark":
            pending["de_kafka_spark"] = text_raw
        if last_key == "utter_ask_de_warehouse":
            pending["de_warehouse"] = text_raw
        if last_key == "utter_ask_de_orchestration":
            pending["de_orchestration"] = text_raw
        if last_key == "utter_ask_de_sql_optimization":
            pending["de_sql_optimization"] = text_raw
        if last_key == "utter_ask_de_monitoring":
            pending["de_monitoring"] = text_raw

        # --- DA slots ---
        if intent == "answer_business_domain" or (
            last_key == "utter_ask_da_domain"
            and intent not in {"stop_interview", "goodbye", "ask_repeat", "out_of_scope"}
        ):
            pending["da_business_domain"] = text_raw
        if last_key == "utter_ask_da_product_metrics":
            pending["da_product_metrics"] = text_raw
        if last_key == "utter_ask_da_ab_tests":
            pending["da_ab_tests"] = text_raw
        if last_key == "utter_ask_da_funnel_cohort":
            pending["da_funnel_cohort"] = text_raw
        if last_key == "utter_ask_da_bi":
            pending["da_bi_dashboards"] = text_raw
        if last_key == "utter_ask_da_stakeholders":
            pending["da_stakeholders"] = text_raw
        if last_key == "utter_ask_da_product_thinking":
            pending["da_product_thinking"] = text_raw

        # --- PM slots ---
        if intent == "answer_methodology" or (
            intent == "answer_interview_open" and last_key == "utter_ask_pm_methodology"
        ):
            pending["pm_methodology"] = _extract_list_from_text(text_raw)
        if last_key == "utter_ask_pm_risk_management":
            pending["pm_risk_management"] = text_raw
        if last_key == "utter_ask_pm_budget":
            pending["pm_budget"] = text_raw
        if last_key == "utter_ask_pm_conflict":
            pending["pm_conflict"] = text_raw
        if last_key == "utter_ask_pm_delivery":
            pending["pm_delivery"] = text_raw
        if last_key == "utter_ask_pm_distributed_team":
            pending["pm_distributed_team"] = text_raw
        if last_key == "utter_ask_pm_ai_ml_projects":
            pending["pm_ai_ml_projects"] = text_raw

        # --- MLOps slots ---
        if last_key == "utter_ask_mlops_kubernetes":
            pending["mlops_kubernetes"] = text_raw
        if last_key == "utter_ask_mlops_model_registry":
            pending["mlops_model_registry"] = text_raw
        if last_key == "utter_ask_mlops_docker":
            pending["mlops_docker"] = text_raw
        if last_key == "utter_ask_mlops_iac":
            pending["mlops_iac"] = text_raw
        if last_key == "utter_ask_mlops_serving":
            pending["mlops_serving"] = text_raw
        if last_key == "utter_ask_mlops_gpu":
            pending["mlops_gpu"] = text_raw

        # --- Common intent handlers ---
        if intent == "answer_frameworks" or (
            intent == "answer_interview_open" and last_key == "utter_ask_ds_frameworks"
        ):
            pending["ds_frameworks"] = _extract_list_from_text(text_raw)

        if intent in {"provide_skills", "answer_interview_open"}:
            if last_key == "utter_ask_ds_python_level":
                lvl = _norm_python_level(text_lower)
                if lvl is not None:
                    pending["ds_python_level"] = lvl
            elif last_key == "utter_ask_ds_frameworks":
                pending["ds_frameworks"] = _extract_list_from_text(text_raw)
            elif last_key == "utter_ask_de_tools":
                pending["de_tools"] = _extract_list_from_text(text_raw)
            elif last_key == "utter_ask_mlops_tools":
                pending["mlops_tools"] = _extract_list_from_text(text_raw)
            elif last_key == "utter_ask_da_viz":
                pending["da_viz_tools"] = _extract_list_from_text(text_raw)
            elif last_key == "utter_ask_da_domain":
                pending["da_business_domain"] = text_raw
            elif role == "data_scientist":
                lvl = _norm_python_level(text_lower)
                if lvl is not None:
                    pending["ds_python_level"] = lvl
            elif role == "data_analyst":
                pending["da_viz_tools"] = _extract_list_from_text(text_raw)

        if intent == "answer_tools" or (
            intent == "answer_interview_open"
            and last_key in {"utter_ask_de_tools", "utter_ask_mlops_tools"}
        ):
            if role == "data_engineer":
                pending["de_tools"] = _extract_list_from_text(text_raw)
            if role == "mlops_engineer":
                pending["mlops_tools"] = _extract_list_from_text(text_raw)

        if intent == "answer_viz_tools" or (
            intent in {"provide_skills", "answer_interview_open"} and last_key == "utter_ask_da_viz"
        ):
            pending["da_viz_tools"] = _extract_list_from_text(text_raw)

        if intent == "answer_skill_python" or (
            intent == "answer_interview_open" and last_key == "utter_ask_ds_python_level"
        ):
            level = _norm_python_level(text_lower)
            if level is not None:
                pending["ds_python_level"] = level
            exp_years = tracker.get_slot("experience_years")
            if level == "beginner" and exp_years is not None and float(exp_years) < 1.0:
                pending["ds_python_risk"] = True
            elif level is not None:
                pending["ds_python_risk"] = False

        if intent == "answer_sql_level" or (
            last_key in {"utter_ask_da_sql", "utter_ask_de_sql"}
            and intent in {"affirm", "deny", "provide_skills", "answer_sql_level", "answer_interview_open"}
        ):
            if role == "data_engineer":
                pending["de_sql_level"] = _norm_sql_level(text_lower) or "intermediate"
            if role == "data_analyst":
                pending["da_sql_level"] = _norm_sql_level(text_lower) or "intermediate"

        if intent == "answer_cloud_experience" or (
            intent == "answer_interview_open" and last_key == "utter_ask_de_cloud"
        ):
            val = _norm_bool(text_lower)
            if val is not None:
                pending["de_cloud_experience"] = val

        if intent == "answer_cicd_experience" or (
            intent == "answer_interview_open" and last_key == "utter_ask_mlops_cicd"
        ):
            val = _norm_bool(text_lower)
            if val is not None:
                pending["mlops_ci_cd"] = val

        if intent == "answer_monitoring_experience" or (
            intent == "answer_interview_open" and last_key == "utter_ask_mlops_monitoring"
        ):
            val = _norm_bool(text_lower)
            if val is not None:
                pending["mlops_monitoring"] = val

        if intent == "answer_production_experience" or (
            intent == "answer_interview_open" and last_key == "utter_ask_ds_production"
        ):
            val = _norm_bool(text_lower)
            if val is not None:
                pending["ds_has_production"] = val

        if intent == "affirm" and last_key == "utter_ask_ds_production":
            pending["ds_has_production"] = True
        if intent == "deny" and last_key == "utter_ask_ds_production":
            pending["ds_has_production"] = False

        if intent == "answer_ml_understanding" or (
            intent == "answer_interview_open" and last_key == "utter_ask_pm_ml_understanding"
        ):
            if "none" in text_lower or "не разбира" in text_lower:
                pending["pm_ml_understanding"] = "none"
            elif "good" in text_lower or "хорош" in text_lower:
                pending["pm_ml_understanding"] = "good"
            else:
                pending["pm_ml_understanding"] = "basic"

        if intent == "answer_team_size" or (
            intent == "answer_interview_open" and last_key == "utter_ask_pm_team_size"
        ):
            num = _extract_number(text_lower)
            if num is not None:
                pending["pm_team_size"] = num

        if intent == "no_experience":
            _fill_no_experience(pending, last_key, role, text_raw)

        events.extend(_pending_to_events(pending))

        def gv(key: Text) -> Any:
            return _slot_get(tracker, pending, key)

        next_q, extra = _next_question_response(gv)
        events.extend(extra)

        if entering_interview:
            role_labels = {
                "data_scientist": "Data Scientist",
                "data_engineer": "Data Engineer",
                "data_analyst": "Data Analyst",
                "project_manager": "Project Manager",
                "mlops_engineer": "MLOps Engineer",
            }
            role_label = role_labels.get(role, role)
            dispatcher.utter_message(text=f"Теперь несколько вопросов по позиции {role_label}.")

        dispatcher.utter_message(response=next_q)
        events.append(SlotSet("last_question_key", next_q))
        return events


def _role_has_primary_skill_signal(tracker: Tracker, role: Optional[str]) -> bool:
    """Проверка, что по роли есть хотя бы один содержательный ответ (не пустое интервью)."""
    if role == "data_scientist":
        return bool(str(tracker.get_slot("ds_ml_experience") or "").strip())
    if role == "data_engineer":
        if str(tracker.get_slot("de_pipeline_experience") or "").strip():
            return True
        tools = tracker.get_slot("de_tools") or []
        return bool(tools) and tools != ["нет практики"]
    if role == "data_analyst":
        if str(tracker.get_slot("da_business_domain") or "").strip():
            return True
        viz = tracker.get_slot("da_viz_tools") or []
        return bool(viz) and viz != ["нет практики"]
    if role == "project_manager":
        if tracker.get_slot("pm_team_size") is not None:
            return True
        meth = tracker.get_slot("pm_methodology") or []
        return bool(meth) and meth != ["не применял"]
    if role == "mlops_engineer":
        if tracker.get_slot("mlops_ci_cd") is not None:
            return True
        tools = tracker.get_slot("mlops_tools") or []
        return bool(tools) and tools != ["нет практики"]
    return True


class ActionAssessCandidate(Action):
    def name(self) -> Text:
        return "action_assess_candidate"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        score, level, decision, strengths, weaknesses, warnings = _score_candidate(tracker)
        role = tracker.get_slot("desired_role")
        exp = float(tracker.get_slot("experience_years") or 0.0)
        name = tracker.get_slot("candidate_name") or "Кандидат"

        is_suitable = decision != "Reject"
        reason = ""
        if not is_suitable:
            reason = "; ".join(weaknesses[:3]) if weaknesses else "Недостаточный общий score для данной роли."

        # Недостаточно данных по роли — снижаем score, без жёсткого обнуления
        primary_ok = _role_has_primary_skill_signal(tracker, role)
        if not primary_ok:
            score = min(score, 38)
            weaknesses = list(weaknesses or [])
            joined_w = " ".join(weaknesses)
            if "мало ответов для уверенной оценки ключевых навыков" not in joined_w:
                weaknesses.append("мало ответов для уверенной оценки ключевых навыков")
            decision = _hire_decision_from_score(score)
            is_suitable = decision != "Reject"
            if not is_suitable:
                reason = reason or "Недостаточно данных по ключевым навыкам для позитивного решения."

        salary_note = _salary_assessment(tracker, level, score)

        role_labels = {
            "data_scientist": "Data Scientist",
            "data_engineer": "Data Engineer",
            "data_analyst": "Data Analyst",
            "project_manager": "Project Manager",
            "mlops_engineer": "MLOps Engineer",
        }
        role_label = role_labels.get(role or "", role or "Не определена")

        # Decision emoji
        decision_emoji = {
            "Strong Hire": "🟢",
            "Hire": "🟡",
            "Maybe": "🟠",
            "Reject": "🔴",
        }.get(decision, "")

        # Summary is saved to JSON only — not shown to the candidate.
        # Build it anyway so it lands in the payload written by action_save_candidate_data.
        _ = {
            "role": role_label,
            "level": _level_display_ru(level),
            "experience_years": exp,
            "score": score,
            "decision": f"{decision_emoji} {decision}",
            "recommendation": _hire_recommendation_ru(decision),
            "strengths": strengths[:5] if strengths else [],
            "weaknesses": weaknesses[:5] if weaknesses else [],
            "warnings": warnings,
            "salary_note": salary_note,
        }

        events: List[Dict[Text, Any]] = [
            SlotSet("candidate_score", float(score)),
            SlotSet("candidate_level", level),
            SlotSet("hire_decision", decision),
            SlotSet("candidate_strengths", strengths),
            SlotSet("candidate_weaknesses", weaknesses),
            SlotSet("consistency_warnings", warnings),
            SlotSet("is_suitable", is_suitable),
            SlotSet("unsuitable_reason", reason),
            SlotSet("interview_stage", "farewell"),
        ]

        if is_suitable:
            dispatcher.utter_message(response="utter_farewell_suitable")
        else:
            dispatcher.utter_message(response="utter_farewell_not_suitable")

        events.append(FollowupAction("action_save_candidate_data"))
        return events


class ActionHandleOutOfScope(Action):
    def name(self) -> Text:
        return "action_handle_out_of_scope"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        count = int((tracker.get_slot("out_of_scope_count") or 0) + 1)
        key = str(tracker.get_slot("last_question_key") or "utter_ask_experience")
        question = QUESTION_TEXT.get(key, "Продолжим интервью.")

        if count >= 3:
            dispatcher.utter_message(response="utter_farewell_stopped")
            return [
                SlotSet("out_of_scope_count", float(count)),
                SlotSet("interview_stage", "farewell"),
                FollowupAction("action_save_candidate_data"),
            ]

        dispatcher.utter_message(
            response="utter_out_of_scope",
            **{"last_question": question},
        )
        dispatcher.utter_message(response=key)
        return [
            SlotSet("out_of_scope_count", float(count)),
            SlotSet("last_question_key", key),
        ]


class ActionSaveCandidateData(Action):
    def name(self) -> Text:
        return "action_save_candidate_data"

    @staticmethod
    def _build_payload(tracker: Tracker, save_error: str = None) -> Dict[Text, Any]:
        """Collect all slot data into a serialisable dict. Never raises."""
        def _slot(name: str):
            try:
                return tracker.get_slot(name)
            except Exception:
                return None

        role_specific_slots = {
            # DS
            "ds_ml_experience": _slot("ds_ml_experience"),
            "ds_task_types": _slot("ds_task_types"),
            "ds_feature_engineering": _slot("ds_feature_engineering"),
            "ds_validation": _slot("ds_validation"),
            "ds_ab_testing": _slot("ds_ab_testing"),
            "ds_llm_experience": _slot("ds_llm_experience"),
            "ds_inference_opt": _slot("ds_inference_opt"),
            "ds_python_level": _slot("ds_python_level"),
            "ds_frameworks": _slot("ds_frameworks"),
            "ds_has_production": _slot("ds_has_production"),
            "ds_python_risk": _slot("ds_python_risk"),
            # DE
            "de_pipeline_experience": _slot("de_pipeline_experience"),
            "de_data_volumes": _slot("de_data_volumes"),
            "de_batch_streaming": _slot("de_batch_streaming"),
            "de_kafka_spark": _slot("de_kafka_spark"),
            "de_warehouse": _slot("de_warehouse"),
            "de_tools": _slot("de_tools"),
            "de_cloud_experience": _slot("de_cloud_experience"),
            "de_sql_level": _slot("de_sql_level"),
            "de_sql_optimization": _slot("de_sql_optimization"),
            "de_orchestration": _slot("de_orchestration"),
            "de_monitoring": _slot("de_monitoring"),
            # DA
            "da_viz_tools": _slot("da_viz_tools"),
            "da_sql_level": _slot("da_sql_level"),
            "da_business_domain": _slot("da_business_domain"),
            "da_product_metrics": _slot("da_product_metrics"),
            "da_ab_tests": _slot("da_ab_tests"),
            "da_funnel_cohort": _slot("da_funnel_cohort"),
            "da_bi_dashboards": _slot("da_bi_dashboards"),
            "da_stakeholders": _slot("da_stakeholders"),
            "da_product_thinking": _slot("da_product_thinking"),
            # PM
            "pm_team_size": _slot("pm_team_size"),
            "pm_methodology": _slot("pm_methodology"),
            "pm_ml_understanding": _slot("pm_ml_understanding"),
            "pm_risk_management": _slot("pm_risk_management"),
            "pm_budget": _slot("pm_budget"),
            "pm_conflict": _slot("pm_conflict"),
            "pm_delivery": _slot("pm_delivery"),
            "pm_distributed_team": _slot("pm_distributed_team"),
            "pm_ai_ml_projects": _slot("pm_ai_ml_projects"),
            # MLOps
            "mlops_ci_cd": _slot("mlops_ci_cd"),
            "mlops_tools": _slot("mlops_tools"),
            "mlops_monitoring": _slot("mlops_monitoring"),
            "mlops_kubernetes": _slot("mlops_kubernetes"),
            "mlops_model_registry": _slot("mlops_model_registry"),
            "mlops_docker": _slot("mlops_docker"),
            "mlops_iac": _slot("mlops_iac"),
            "mlops_serving": _slot("mlops_serving"),
            "mlops_gpu": _slot("mlops_gpu"),
        }
        payload: Dict[Text, Any] = {
            "candidate_name": _slot("candidate_name"),
            "desired_role": _slot("desired_role"),
            "experience_years": _slot("experience_years"),
            "candidate_level": _slot("candidate_level"),
            "candidate_score": _slot("candidate_score"),
            "hire_decision": _slot("hire_decision"),
            "is_suitable": _slot("is_suitable"),
            "salary_expectation": _slot("salary_expectation"),
            "interview_stage": _slot("interview_stage"),
            "unsuitable_reason": _slot("unsuitable_reason"),
            "candidate_strengths": _slot("candidate_strengths"),
            "candidate_weaknesses": _slot("candidate_weaknesses"),
            "consistency_warnings": _slot("consistency_warnings"),
            "role_specific_slots": role_specific_slots,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if save_error:
            payload["save_error"] = save_error
        return payload

    @staticmethod
    def _write_json(sender_id: str, payload: Dict[Text, Any]) -> str:
        """Write payload to disk; returns the file path. May raise."""
        out_dir = os.path.join(os.getcwd(), "data", "candidates")
        os.makedirs(out_dir, exist_ok=True)
        filename = (
            f"{sender_id}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        filepath = os.path.join(out_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return filepath

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        try:
            payload = self._build_payload(tracker)
            self._write_json(tracker.sender_id, payload)
        except Exception as primary_exc:
            # First attempt failed — try again with a minimal emergency payload
            try:
                emergency_payload = self._build_payload(
                    tracker, save_error=str(primary_exc)
                )
                self._write_json(tracker.sender_id, emergency_payload)
            except Exception:
                # Filesystem completely unavailable — log and move on silently
                import traceback
                traceback.print_exc()

        return [SlotSet("interview_stage", "end")]


class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        stage = tracker.get_slot("interview_stage") or ""
        if stage in ("farewell", "end"):
            return []
        if stage == "collect_salary":
            return [FollowupAction("action_collect_salary")]
        dispatcher.utter_message(response="utter_not_recognized")
        return []


# ---------------------------------------------------------------------------
# Dynamic tracked-utter action factory
# ---------------------------------------------------------------------------

def _make_tracked_utter_action(action_name: str, response_name: str, stage: Optional[str]) -> type:
    def name(self) -> Text:
        return action_name

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(response=response_name)
        out: List[Dict[Text, Any]] = [SlotSet("last_question_key", response_name)]
        if stage:
            out.append(SlotSet("interview_stage", stage))
        return out

    return type(action_name, (Action,), {"name": name, "run": run})


_TRACKED_UTTER_SPECS: List[Tuple[str, str, Optional[str]]] = [
    ("action_say_utter_ask_experience", "utter_ask_experience", "collect_experience"),
    ("action_say_utter_ask_role", "utter_ask_role", "collect_role"),
    ("action_say_utter_low_experience_warning", "utter_low_experience_warning", "collect_experience"),
    # DS
    ("action_say_utter_ask_ds_ml_experience", "utter_ask_ds_ml_experience", "interview_ds"),
    ("action_say_utter_ask_ds_task_types", "utter_ask_ds_task_types", "interview_ds"),
    ("action_say_utter_ask_ds_feature_engineering", "utter_ask_ds_feature_engineering", "interview_ds"),
    ("action_say_utter_ask_ds_validation", "utter_ask_ds_validation", "interview_ds"),
    ("action_say_utter_ask_ds_ab_testing", "utter_ask_ds_ab_testing", "interview_ds"),
    ("action_say_utter_ask_ds_llm", "utter_ask_ds_llm", "interview_ds"),
    ("action_say_utter_ask_ds_inference_opt", "utter_ask_ds_inference_opt", "interview_ds"),
    ("action_say_utter_ask_ds_python_level", "utter_ask_ds_python_level", "interview_ds"),
    ("action_say_utter_ask_ds_frameworks", "utter_ask_ds_frameworks", "interview_ds"),
    ("action_say_utter_ask_ds_production", "utter_ask_ds_production", "interview_ds"),
    # DE
    ("action_say_utter_ask_de_pipeline", "utter_ask_de_pipeline", "interview_de"),
    ("action_say_utter_ask_de_data_volumes", "utter_ask_de_data_volumes", "interview_de"),
    ("action_say_utter_ask_de_batch_streaming", "utter_ask_de_batch_streaming", "interview_de"),
    ("action_say_utter_ask_de_kafka_spark", "utter_ask_de_kafka_spark", "interview_de"),
    ("action_say_utter_ask_de_warehouse", "utter_ask_de_warehouse", "interview_de"),
    ("action_say_utter_ask_de_tools", "utter_ask_de_tools", "interview_de"),
    ("action_say_utter_ask_de_cloud", "utter_ask_de_cloud", "interview_de"),
    ("action_say_utter_ask_de_sql", "utter_ask_de_sql", "interview_de"),
    ("action_say_utter_ask_de_sql_optimization", "utter_ask_de_sql_optimization", "interview_de"),
    ("action_say_utter_ask_de_orchestration", "utter_ask_de_orchestration", "interview_de"),
    ("action_say_utter_ask_de_monitoring", "utter_ask_de_monitoring", "interview_de"),
    # DA
    ("action_say_utter_ask_da_domain", "utter_ask_da_domain", "interview_da"),
    ("action_say_utter_ask_da_product_metrics", "utter_ask_da_product_metrics", "interview_da"),
    ("action_say_utter_ask_da_ab_tests", "utter_ask_da_ab_tests", "interview_da"),
    ("action_say_utter_ask_da_funnel_cohort", "utter_ask_da_funnel_cohort", "interview_da"),
    ("action_say_utter_ask_da_viz", "utter_ask_da_viz", "interview_da"),
    ("action_say_utter_ask_da_sql", "utter_ask_da_sql", "interview_da"),
    ("action_say_utter_ask_da_bi", "utter_ask_da_bi", "interview_da"),
    ("action_say_utter_ask_da_stakeholders", "utter_ask_da_stakeholders", "interview_da"),
    ("action_say_utter_ask_da_product_thinking", "utter_ask_da_product_thinking", "interview_da"),
    # PM
    ("action_say_utter_ask_pm_team_size", "utter_ask_pm_team_size", "interview_pm"),
    ("action_say_utter_ask_pm_methodology", "utter_ask_pm_methodology", "interview_pm"),
    ("action_say_utter_ask_pm_ml_understanding", "utter_ask_pm_ml_understanding", "interview_pm"),
    ("action_say_utter_ask_pm_risk_management", "utter_ask_pm_risk_management", "interview_pm"),
    ("action_say_utter_ask_pm_budget", "utter_ask_pm_budget", "interview_pm"),
    ("action_say_utter_ask_pm_conflict", "utter_ask_pm_conflict", "interview_pm"),
    ("action_say_utter_ask_pm_delivery", "utter_ask_pm_delivery", "interview_pm"),
    ("action_say_utter_ask_pm_distributed_team", "utter_ask_pm_distributed_team", "interview_pm"),
    ("action_say_utter_ask_pm_ai_ml_projects", "utter_ask_pm_ai_ml_projects", "interview_pm"),
    # MLOps
    ("action_say_utter_ask_mlops_cicd", "utter_ask_mlops_cicd", "interview_mlops"),
    ("action_say_utter_ask_mlops_tools", "utter_ask_mlops_tools", "interview_mlops"),
    ("action_say_utter_ask_mlops_monitoring", "utter_ask_mlops_monitoring", "interview_mlops"),
    ("action_say_utter_ask_mlops_kubernetes", "utter_ask_mlops_kubernetes", "interview_mlops"),
    ("action_say_utter_ask_mlops_model_registry", "utter_ask_mlops_model_registry", "interview_mlops"),
    ("action_say_utter_ask_mlops_docker", "utter_ask_mlops_docker", "interview_mlops"),
    ("action_say_utter_ask_mlops_iac", "utter_ask_mlops_iac", "interview_mlops"),
    ("action_say_utter_ask_mlops_serving", "utter_ask_mlops_serving", "interview_mlops"),
    ("action_say_utter_ask_mlops_gpu", "utter_ask_mlops_gpu", "interview_mlops"),
]

_mod = sys.modules[__name__]
for _an, _rn, _st in _TRACKED_UTTER_SPECS:
    setattr(_mod, _an, _make_tracked_utter_action(_an, _rn, _st))