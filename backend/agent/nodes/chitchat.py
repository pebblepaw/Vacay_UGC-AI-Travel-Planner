from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from backend.agent.state import AgentState
from backend.app_config import get_assistant_language_instruction, render_copy
from backend.llm import get_agent_llm
from datetime import datetime


prompt = ChatPromptTemplate.from_template(
    "You are a friendly travel assistant. {language_instruction} Reply to {input}"
)


def _is_date_question(text: str) -> bool:
    lowered = text.lower()
    zh_hit = ("今天" in text and ("几月几日" in text or "日期" in text or "几号" in text))
    en_hit = ("today" in lowered and ("date" in lowered or "day" in lowered))
    return zh_hit or en_hit


def _today_text() -> str:
    now = datetime.now()
    return render_copy("general.today", date=f"{now.year}-{now.month:02d}-{now.day:02d}")


def chitchat_node(state: AgentState): 


    last_msg = state['messages'][-1].content

    # Deterministic answer for date questions to avoid model hallucination.
    if _is_date_question(last_msg):
        return {'messages': [AIMessage(content=_today_text())]}

    llm = get_agent_llm(role="chitchat")

    chain = prompt | llm

    response = chain.invoke(
        {
            'input': last_msg,
            'language_instruction': get_assistant_language_instruction(),
        }
    )
    return {'messages': [response]}
