from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from backend.agent.state import AgentState
from backend.llm import get_agent_llm
from datetime import datetime


prompt = ChatPromptTemplate.from_template("You are a friendly travel assistant. Reply to {input}")


def _is_date_question(text: str) -> bool:
    lowered = text.lower()
    zh_hit = ("今天" in text and ("几月几日" in text or "日期" in text or "几号" in text))
    en_hit = ("today" in lowered and ("date" in lowered or "day" in lowered))
    return zh_hit or en_hit


def _today_text_cn() -> str:
    now = datetime.now()
    return f"今天是{now.year}年{now.month}月{now.day}日。"


def chitchat_node(state: AgentState): 


    last_msg = state['messages'][-1].content

    # Deterministic answer for date questions to avoid model hallucination.
    if _is_date_question(last_msg):
        return {'messages': [AIMessage(content=_today_text_cn())]}

    llm = get_agent_llm()

    chain = prompt | llm

    response = chain.invoke({'input': last_msg})
    return {'messages': [response]}