import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Text, Tuple

from rasa_sdk import Action, Tracker
from rasa_sdk.events import FollowupAction, SlotSet
from rasa_sdk.executor import CollectingDispatcher


QUESTION_TEXT: Dict[str, str] = {
    "utter_ask_name": "Как вас зовут?",
    "utter_ask_experience": "Сколько лет у вас опыта в IT или сфере данных?",
    "utter_ask_role": "Какая позиция вас интересует?",
    "utter_ask_ds_ml_experience": "Расскажите об опыте разработки ML-моделей.",
    "utter_ask_ds_python_level": "Какой у вас уровень Python? (начальный / средний / продвинутый)",
    "utter_ask_ds_frameworks": "Какие ML-фреймворки использовали?",
    "utter_ask_ds_production": "Был ли опыт вывода ML-моделей в production?",
    "utter_ask_de_pipeline": "Опишите опыт с ETL/ELT пайплайнами.",
    "utter_ask_de_tools": "Какие инструменты использовали?",
    "utter_ask_de_cloud": "Есть ли опыт с облачными платформами?",
    "utter_ask_de_sql": "Как оцените свой уровень SQL?",
    "utter_ask_da_domain": "В каких предметных областях работали аналитиком?",
    "utter_ask_da_viz": "Какие инструменты визуализации используете?",
    "utter_ask_da_sql": "Оцените свой уровень SQL: базовый, средний или продвинутый?",
    "utter_ask_pm_team_size": "Какой максимальный размер команды вы координировали?",
    "utter_ask_pm_methodology": "Какие методологии применяли?",
    "utter_ask_pm_ml_understanding": "Как оцените своё понимание ML-проектов и их специфики?",
    "utter_ask_mlops_cicd": "Есть ли опыт CI/CD для ML-проектов?",
    "utter_ask_mlops_tools": "Какие MLOps-инструменты знаете?",
    "utter_ask_mlops_monitoring": "Есть ли опыт мониторинга моделей?",
    "utter_ask_salary": "Какой уровень вознаграждения вас интересует (₽/мес, до вычета налогов)?",
    "utter_low_experience_warning": "Были ли стажировки или учебные проекты?",
}

QUESTION_EXAMPLES: Dict[str, str] = {
    "utter_ask_name": "Меня зовут Иван.",
    "utter_ask_experience": "У меня 3 года опыта.",
    "utter_ask_role": "Data Scientist или кнопкой в списке.",
    "utter_ask_ds_ml_experience": "Делал классификацию оттока в sklearn и CatBoost.",
    "utter_ask_ds_python_level": "Средний уровень Python.",
    "utter_ask_ds_frameworks": "PyTorch, pandas, scikit-learn.",
    "utter_ask_ds_production": "Да, выкатывали через Docker и REST API.",
    "utter_ask_de_pipeline": "ETL в Airflow из Postgres в S3, затем Spark.",
    "utter_ask_de_tools": "Airflow, dbt, Kafka.",
    "utter_ask_de_cloud": "Да, AWS S3 и Glue.",
    "utter_ask_de_sql": "Продвинутый SQL, оконные функции.",
    "utter_ask_da_domain": "E-commerce, метрики конверсии.",
    "utter_ask_da_viz": "Power BI и иногда Plotly.",
    "utter_ask_da_sql": "Средний уровень SQL.",
    "utter_ask_pm_team_size": "Координировал команду из 8 человек.",
    "utter_ask_pm_methodology": "Scrum с двухнедельными спринтами.",
    "utter_ask_pm_ml_understanding": "Базовое понимание цикла ML.",
    "utter_ask_mlops_cicd": "Да, GitHub Actions для обучения и деплоя.",
    "utter_ask_mlops_tools": "MLflow, Kubernetes, Docker.",
    "utter_ask_mlops_monitoring": "Grafana и алерты по дрейфу.",
    "utter_ask_salary": "150000.",
    "utter_low_experience_warning": "Был курс и pet-проект с Kaggle.",
}


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
    m = re.search(r"(\d+(?:[.,]\d+)?)", raw)
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


def _next_question_response(
    gv: Any,
) -> Tuple[str, List[Dict[Text, Any]]]:
    role = gv("desired_role")
    events: List[Dict[Text, Any]] = []

    if role == "data_scientist":
        if not gv("ds_ml_experience"):
            return "utter_ask_ds_ml_experience", events
        if not gv("ds_python_level"):
            return "utter_ask_ds_python_level", events
        if not gv("ds_frameworks"):
            return "utter_ask_ds_frameworks", events
        if gv("ds_has_production") is None:
            return "utter_ask_ds_production", events
    elif role == "data_engineer":
        if not gv("de_pipeline_experience"):
            return "utter_ask_de_pipeline", events
        if not gv("de_tools"):
            return "utter_ask_de_tools", events
        if gv("de_cloud_experience") is None:
            return "utter_ask_de_cloud", events
        if not gv("de_sql_level"):
            return "utter_ask_de_sql", events
    elif role == "data_analyst":
        if not gv("da_business_domain"):
            return "utter_ask_da_domain", events
        if not gv("da_viz_tools"):
            return "utter_ask_da_viz", events
        if not gv("da_sql_level"):
            return "utter_ask_da_sql", events
    elif role == "project_manager":
        if not gv("pm_team_size"):
            return "utter_ask_pm_team_size", events
        if not gv("pm_methodology"):
            return "utter_ask_pm_methodology", events
        if not gv("pm_ml_understanding"):
            return "utter_ask_pm_ml_understanding", events
    elif role == "mlops_engineer":
        if gv("mlops_ci_cd") is None:
            return "utter_ask_mlops_cicd", events
        if not gv("mlops_tools"):
            return "utter_ask_mlops_tools", events
        if gv("mlops_monitoring") is None:
            return "utter_ask_mlops_monitoring", events

    events.append(SlotSet("interview_stage", "collect_salary"))
    return "utter_ask_salary", events


def _pending_to_events(pending: Dict[str, Any]) -> List[Dict[Text, Any]]:
    return [SlotSet(k, v) for k, v in pending.items()]


def _fill_no_experience(pending: Dict[str, Any], last_key: str, role: Optional[str], text_raw: str) -> None:
    note = text_raw or "Нет такого опыта"
    lk = last_key or ""
    if "ds_ml" in lk:
        pending["ds_ml_experience"] = note
    elif "ds_python" in lk:
        pending["ds_python_level"] = "beginner"
    elif "ds_framework" in lk:
        pending["ds_frameworks"] = ["нет практики"]
    elif "ds_production" in lk:
        pending["ds_has_production"] = False
    elif "de_pipeline" in lk:
        pending["de_pipeline_experience"] = note
    elif "de_tools" in lk:
        pending["de_tools"] = ["нет практики"]
    elif "de_cloud" in lk:
        pending["de_cloud_experience"] = False
    elif "de_sql" in lk:
        pending["de_sql_level"] = "beginner"
    elif "da_domain" in lk:
        pending["da_business_domain"] = note
    elif "da_viz" in lk:
        pending["da_viz_tools"] = ["нет практики"]
    elif "da_sql" in lk:
        pending["da_sql_level"] = "beginner"
    elif "pm_team" in lk:
        pending["pm_team_size"] = 0.0
    elif "pm_method" in lk:
        pending["pm_methodology"] = ["не применял"]
    elif "pm_ml" in lk:
        pending["pm_ml_understanding"] = "none"
    elif "mlops_cicd" in lk:
        pending["mlops_ci_cd"] = False
    elif "mlops_tools" in lk:
        pending["mlops_tools"] = ["нет практики"]
    elif "mlops_monitoring" in lk:
        pending["mlops_monitoring"] = False
    elif role == "data_scientist" and not pending.get("ds_ml_experience"):
        pending["ds_ml_experience"] = note
    elif role == "data_engineer" and not pending.get("de_pipeline_experience"):
        pending["de_pipeline_experience"] = note


class ActionGreet(Action):
    def name(self) -> Text:
        return "action_greet"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(response="utter_greet")
        return [
            SlotSet("interview_stage", "greeting"),
            SlotSet("last_question_key", "utter_ask_name"),
        ]


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
        clarify = int(tracker.get_slot("clarify_count") or 0)
        key = str(tracker.get_slot("last_question_key") or "")

        if clarify >= 2:
            dispatcher.utter_message(response="utter_unclear_move_on")
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

        pending: Dict[str, Any] = {}
        events: List[Dict[Text, Any]] = [
            SlotSet("interview_stage", _role_interview_stage(role)),
            SlotSet("clarify_count", 0.0),
            SlotSet("ask_repeat_count", 0.0),
        ]

        if intent in {"provide_project_experience", "answer_ml_experience"}:
            pending["ds_ml_experience"] = text_raw
        if intent == "answer_pipeline_experience":
            pending["de_pipeline_experience"] = text_raw
        if intent == "answer_business_domain":
            pending["da_business_domain"] = text_raw
        if intent == "answer_methodology":
            pending["pm_methodology"] = _extract_list_from_text(text_raw)
        if intent == "answer_frameworks":
            pending["ds_frameworks"] = _extract_list_from_text(text_raw)

        if intent == "provide_skills":
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
            elif role == "data_scientist":
                lvl = _norm_python_level(text_lower)
                if lvl is not None:
                    pending["ds_python_level"] = lvl

        if intent == "answer_tools":
            if role == "data_engineer":
                pending["de_tools"] = _extract_list_from_text(text_raw)
            if role == "mlops_engineer":
                pending["mlops_tools"] = _extract_list_from_text(text_raw)

        if intent == "answer_viz_tools":
            pending["da_viz_tools"] = _extract_list_from_text(text_raw)

        if intent == "answer_skill_python":
            level = _norm_python_level(text_lower)
            if level is not None:
                pending["ds_python_level"] = level
            exp_years = tracker.get_slot("experience_years")
            if level == "beginner" and exp_years is not None and float(exp_years) < 1.0:
                pending["ds_python_risk"] = True
            elif level is not None:
                pending["ds_python_risk"] = False

        if intent == "answer_sql_level":
            if role == "data_engineer":
                pending["de_sql_level"] = _norm_sql_level(text_lower)
            if role == "data_analyst":
                pending["da_sql_level"] = _norm_sql_level(text_lower)

        if intent == "answer_cloud_experience":
            val = _norm_bool(text_lower)
            if val is not None:
                pending["de_cloud_experience"] = val

        if intent == "answer_cicd_experience":
            val = _norm_bool(text_lower)
            if val is not None:
                pending["mlops_ci_cd"] = val

        if intent == "answer_monitoring_experience":
            val = _norm_bool(text_lower)
            if val is not None:
                pending["mlops_monitoring"] = val

        if intent == "answer_production_experience":
            val = _norm_bool(text_lower)
            if val is not None:
                pending["ds_has_production"] = val

        if intent == "affirm" and last_key == "utter_ask_ds_production":
            pending["ds_has_production"] = True
        if intent == "deny" and last_key == "utter_ask_ds_production":
            pending["ds_has_production"] = False

        if intent == "answer_ml_understanding":
            if "none" in text_lower or "не разбира" in text_lower:
                pending["pm_ml_understanding"] = "none"
            elif "good" in text_lower or "хорош" in text_lower:
                pending["pm_ml_understanding"] = "good"
            else:
                pending["pm_ml_understanding"] = "basic"

        if intent == "answer_team_size":
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
        dispatcher.utter_message(response=next_q)
        events.append(SlotSet("last_question_key", next_q))
        return events


class ActionAssessCandidate(Action):
    def name(self) -> Text:
        return "action_assess_candidate"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        role = tracker.get_slot("desired_role")
        exp = float(tracker.get_slot("experience_years") or 0.0)
        is_suitable = True
        reason = ""

        if role in {"data_scientist", "data_engineer", "mlops_engineer"} and exp < 0.5:
            is_suitable = False
            reason = "Недостаточный опыт для выбранной роли."

        if role == "data_scientist":
            if tracker.get_slot("ds_python_level") == "beginner" and tracker.get_slot("ds_has_production") is False:
                is_suitable = False
                reason = "Для DS нужен более сильный Python и/или production-опыт."

        if role == "project_manager":
            team_size = float(tracker.get_slot("pm_team_size") or 0.0)
            if tracker.get_slot("pm_ml_understanding") == "none" and team_size < 3:
                is_suitable = False
                reason = "Для PM недостаточно ML-понимания и опыта руководства командой."

        skill_slots = [
            tracker.get_slot("ds_ml_experience"),
            tracker.get_slot("ds_frameworks"),
            tracker.get_slot("de_pipeline_experience"),
            tracker.get_slot("de_tools"),
            tracker.get_slot("da_viz_tools"),
            tracker.get_slot("da_business_domain"),
            tracker.get_slot("pm_methodology"),
            tracker.get_slot("mlops_tools"),
        ]
        if not any(skill_slots):
            is_suitable = False
            reason = "Не заполнены ключевые навыки."

        events: List[Dict[Text, Any]] = [
            SlotSet("is_suitable", is_suitable),
            SlotSet("unsuitable_reason", reason),
            SlotSet("interview_stage", "not_suitable" if not is_suitable else "assessment"),
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
        return [SlotSet("out_of_scope_count", float(count)), SlotSet("last_question_key", key)]


class ActionSaveCandidateData(Action):
    def name(self) -> Text:
        return "action_save_candidate_data"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        role_specific_slots = {
            "ds_ml_experience": tracker.get_slot("ds_ml_experience"),
            "ds_python_level": tracker.get_slot("ds_python_level"),
            "ds_frameworks": tracker.get_slot("ds_frameworks"),
            "ds_has_production": tracker.get_slot("ds_has_production"),
            "ds_python_risk": tracker.get_slot("ds_python_risk"),
            "de_pipeline_experience": tracker.get_slot("de_pipeline_experience"),
            "de_tools": tracker.get_slot("de_tools"),
            "de_cloud_experience": tracker.get_slot("de_cloud_experience"),
            "de_sql_level": tracker.get_slot("de_sql_level"),
            "da_viz_tools": tracker.get_slot("da_viz_tools"),
            "da_sql_level": tracker.get_slot("da_sql_level"),
            "da_business_domain": tracker.get_slot("da_business_domain"),
            "pm_team_size": tracker.get_slot("pm_team_size"),
            "pm_methodology": tracker.get_slot("pm_methodology"),
            "pm_ml_understanding": tracker.get_slot("pm_ml_understanding"),
            "mlops_ci_cd": tracker.get_slot("mlops_ci_cd"),
            "mlops_tools": tracker.get_slot("mlops_tools"),
            "mlops_monitoring": tracker.get_slot("mlops_monitoring"),
        }
        payload = {
            "candidate_name": tracker.get_slot("candidate_name"),
            "desired_role": tracker.get_slot("desired_role"),
            "experience_years": tracker.get_slot("experience_years"),
            "is_suitable": tracker.get_slot("is_suitable"),
            "salary_expectation": tracker.get_slot("salary_expectation"),
            "interview_stage": tracker.get_slot("interview_stage"),
            "unsuitable_reason": tracker.get_slot("unsuitable_reason"),
            "role_specific_slots": role_specific_slots,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        out_dir = os.path.join(os.getcwd(), "data", "candidates")
        os.makedirs(out_dir, exist_ok=True)
        filename = f"{tracker.sender_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        with open(os.path.join(out_dir, filename), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

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
        dispatcher.utter_message(response="utter_not_recognized")
        return []


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

    return type(
        action_name,
        (Action,),
        {"name": name, "run": run},
    )


_TRACKED_UTTER_SPECS: List[Tuple[str, str, Optional[str]]] = [
    ("action_say_utter_ask_experience", "utter_ask_experience", "collect_experience"),
    ("action_say_utter_ask_role", "utter_ask_role", "collect_role"),
    ("action_say_utter_low_experience_warning", "utter_low_experience_warning", "collect_experience"),
    ("action_say_utter_ask_ds_ml_experience", "utter_ask_ds_ml_experience", "interview_ds"),
    ("action_say_utter_ask_ds_python_level", "utter_ask_ds_python_level", "interview_ds"),
    ("action_say_utter_ask_ds_frameworks", "utter_ask_ds_frameworks", "interview_ds"),
    ("action_say_utter_ask_ds_production", "utter_ask_ds_production", "interview_ds"),
    ("action_say_utter_ask_de_pipeline", "utter_ask_de_pipeline", "interview_de"),
    ("action_say_utter_ask_de_tools", "utter_ask_de_tools", "interview_de"),
    ("action_say_utter_ask_de_cloud", "utter_ask_de_cloud", "interview_de"),
    ("action_say_utter_ask_de_sql", "utter_ask_de_sql", "interview_de"),
    ("action_say_utter_ask_da_domain", "utter_ask_da_domain", "interview_da"),
    ("action_say_utter_ask_da_viz", "utter_ask_da_viz", "interview_da"),
    ("action_say_utter_ask_da_sql", "utter_ask_da_sql", "interview_da"),
    ("action_say_utter_ask_pm_team_size", "utter_ask_pm_team_size", "interview_pm"),
    ("action_say_utter_ask_pm_methodology", "utter_ask_pm_methodology", "interview_pm"),
    ("action_say_utter_ask_pm_ml_understanding", "utter_ask_pm_ml_understanding", "interview_pm"),
    ("action_say_utter_ask_mlops_cicd", "utter_ask_mlops_cicd", "interview_mlops"),
    ("action_say_utter_ask_mlops_tools", "utter_ask_mlops_tools", "interview_mlops"),
    ("action_say_utter_ask_mlops_monitoring", "utter_ask_mlops_monitoring", "interview_mlops"),
]

_mod = sys.modules[__name__]
for _an, _rn, _st in _TRACKED_UTTER_SPECS:
    setattr(_mod, _an, _make_tracked_utter_action(_an, _rn, _st))
